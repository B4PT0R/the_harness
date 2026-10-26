"""Worker owner and RPC dispatcher; no rich Python objects cross this boundary."""

import asyncio
from contextlib import suppress
from html import unescape
import json
import os
import signal
import socket
import subprocess
import sys
import math
import time
from uuid import uuid4

from the_framework.agent import AgentExtension, tool
from the_framework.agent.models.responses import FunctionCall, ToolOutput

from .protocol import MAX_CODE, MAX_FRAME, encode, receive, send


class PynteractExtension(AgentExtension):
    name = "pynteract"
    description = "Persistent Python objects in a separate process, with explicit JSON and artifact exports."
    instructions_file = "instructions.md"

    def load(self):
        if self.loaded:
            return self
        super().load()
        self._lock = asyncio.Lock()
        self._process = self._reader = self._writer = None
        self._session_id = None
        self._jobs = {}
        self._active_job = None
        return self

    def shutdown(self, *, cancel_job=True):
        job = self._active_job
        if cancel_job and job is not None and not job["task"].done():
            job["task"].get_loop().call_soon_threadsafe(job["task"].cancel)
        process, self._process = self._process, None
        if process is not None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        if self._writer is not None:
            with suppress(RuntimeError):
                self._writer.close()
        self._reader = self._writer = None
        self._session_id = None

    def deactivate(self):
        super().deactivate()
        self.shutdown()
        return self

    async def _start(self):
        if self._process is not None and self._process.poll() is None:
            return
        self.shutdown(cancel_job=False)
        if os.name != "posix":
            raise RuntimeError("This Pynteract process transport currently requires POSIX.")
        parent, child = socket.socketpair()
        try:
            self._process = subprocess.Popen(
                [sys.executable, "-m", "the_harness.plugins.pynteract.session", str(child.fileno())],
                pass_fds=(child.fileno(),), start_new_session=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            parent.setblocking(False)
            self._reader, self._writer = await asyncio.open_connection(sock=parent, limit=MAX_FRAME)
        except BaseException:
            parent.close()
            self.shutdown(cancel_job=False)
            raise
        finally:
            child.close()
        ready = await receive(self._reader)
        if ready.get("type") != "ready":
            raise ValueError("Python session failed to initialize.")
        self._session_id = uuid4().hex

    def _tools(self, query=None):
        return [entry for entry in self.agent.registry("tools").search({"query": query})
                if entry.get("name") != self.name and entry.get("type") in {"function", "namespace"}]

    async def _rpc(self, request):
        if request["method"] == "tools":
            return self._tools(request.get("query"))
        if request["method"] != "call":
            raise ValueError("Unknown worker RPC method.")
        qualified = request["name"].split(".")
        if len(qualified) == 2:
            namespace, name = qualified
        elif len(qualified) == 1:
            namespace, name = None, qualified[0]
        else:
            raise ValueError("Tool name must be namespace.tool or an unambiguous tool name.")
        registry = self.agent.registry("tools")
        resolved = registry.resolve(name, namespace)
        own = registry.get(self.name)
        if own is not None and any(resolved is item for item in own.tools):
            raise ValueError("Recursive Pynteract tool calls are not allowed.")
        feedback = request.get("user_feedback")
        if not isinstance(feedback, str) or not feedback.strip():
            raise ValueError("A non-empty user_feedback is required for every worker tool call.")
        call = FunctionCall(name=name, namespace=namespace, call_id="pynteract_" + uuid4().hex,
                            arguments=json.dumps({**request["arguments"], "user_feedback": feedback}, allow_nan=False))
        self.agent.add_response_item(call)
        output = await self.agent.agentic_loop.run_tool_call(call)
        values = []
        for item in output.output_items or []:
            if isinstance(item, ToolOutput):
                # The pipeline has already rendered and bounded this output.
                # Decode JSON only when complete; preserve non-JSON/truncated text.
                parts = []
                for part in item.content:
                    text = part.text
                    if text.startswith("<tool_output ") and text.endswith("\n</tool_output>"):
                        text = unescape(text.split(">\n", 1)[1].removesuffix("\n</tool_output>"))
                    parts.append(text)
                text = "\n".join(parts)
                try:
                    values.append({"format": "json", "value": json.loads(text)})
                except json.JSONDecodeError:
                    values.append({"format": "text", "value": text})
            else:
                values.append({"format": item.type, "value": json.loads(item.dumps())})
        return {**json.loads(output.output), "outputs": values}

    async def _exchange(self, request, job=None):
        await self._start()
        if job is not None:
            job["session_id"] = self._session_id
        await send(self._writer, request)
        while True:
            reply = await receive(self._reader)
            if reply.get("type") == "started" and job is not None:
                job["ready"] = True
                if job["interrupt_requested"]:
                    self._signal_interrupt()
                continue
            if reply.get("type") == "output" and job is not None:
                stream, text = reply["stream"], reply["text"]
                if stream not in {"stdout", "stderr"} or not isinstance(text, str):
                    raise ValueError("Invalid output notification.")
                job["output_truncated"][stream] |= bool(reply.get("truncated"))
                job["output_chars"][stream] += len(text)
                job[stream] = (job[stream] + text)[-12_000:]
                continue
            if reply.get("type") == "result":
                return reply["value"]
            if reply.get("type") != "rpc":
                raise ValueError("Unexpected Pynteract protocol message.")
            try:
                value = await self._rpc(reply)
                response = {"type": "rpc_result", "value": value}
                encode(response)
            except Exception as error:
                response = {"type": "rpc_result", "error": str(error)[:4096]}
            await send(self._writer, response)

    @staticmethod
    def _validate(request, timeout_seconds):
        if (not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool)
                or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 900):
            raise ValueError("timeout_seconds must be greater than zero and at most 900.")
        encode(request)

    async def _request(self, request, timeout_seconds, job=None):
        self._validate(request, timeout_seconds)
        if self._active_job is not None and self._active_job is not job:
            raise RuntimeError("Python session is busy; check/wait or interrupt the active job first.")
        async with self._lock:
            try:
                result = await asyncio.wait_for(self._exchange(request, job), timeout_seconds)
                return {**result, "session_id": self._session_id, "namespace_lost": False}
            except asyncio.CancelledError:
                self.shutdown(cancel_job=False)
                raise
            except Exception as error:
                previous = self._session_id
                self.shutdown(cancel_job=False)
                return {"status": "error", "error": f"{type(error).__name__}: {error}",
                        "session_id": previous, "namespace_lost": True}

    @tool
    async def execute(self, code: str, timeout_seconds: float = 60):
        """Execute a persistent Pynteract cell, with top-level await and proxy agent.

        Native results stay in the session (including _); stdout includes the last
        result repr, stderr includes tracebacks. JSON exports are explicit. Timeout/crash
        destroys the namespace; next call starts a fresh session. Not a sandbox.
        """
        if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_CODE:
            raise ValueError("code must be a string of at most 128 KiB.")
        return await self._request({"operation": "execute", "code": code}, timeout_seconds)

    @tool
    async def call_python(self, name: str, arguments_json: str, save_as: str,
                          timeout_seconds: float = 60):
        """Call an agent.python.register function in the Python session.

        JSON keyword arguments enter the child process; the native return value
        stays there under save_as. Use execute and agent.export for a projection.
        No worker tool is called by this entry point.
        """
        arguments = json.loads(arguments_json)
        if not isinstance(arguments, dict):
            raise ValueError("arguments_json must contain a JSON object.")
        return await self._request({"operation": "python_call", "name": name,
                                    "arguments": arguments, "save_as": save_as}, timeout_seconds)

    async def _run_job(self, job, request, timeout_seconds):
        try:
            job["result"] = await self._request(request, timeout_seconds, job)
            job["status"] = ("timed_out" if job["result"].get("error", "").startswith("TimeoutError:")
                             else "interrupted" if job["result"]["status"] == "interrupted"
                             else "failed" if job["result"]["status"] == "error" else "completed")
        except asyncio.CancelledError:
            job["status"] = "interrupted"
            job["result"] = {"namespace_lost": True}
        except Exception as error:
            job["status"] = "failed"
            job["result"] = {"error": f"{type(error).__name__}: {error}", "namespace_lost": False}
        finally:
            self._finish_job(job)

    def _finish_job(self, job):
        # Also handles cancellation before the task's first instruction.
        if job["result"] is None:
            job["status"] = "interrupted"
            job["result"] = {"namespace_lost": True}
        job["finished_at"] = job["finished_at"] or time.monotonic()
        if self._active_job is job:
            self._active_job = None

    def _get_job(self, job_id):
        try:
            return self._jobs[job_id]
        except KeyError:
            raise ValueError(f"Unknown or expired Python job: {job_id}") from None

    def _snapshot(self, job):
        result = {"job_id": job["id"], "status": job["status"],
                  "session_id": job["session_id"],
                  "elapsed_seconds": round((job["finished_at"] or time.monotonic()) - job["started_at"], 3),
                  "stdout": job["stdout"], "stderr": job["stderr"],
                  "output_chars": dict(job["output_chars"]),
                  "output_truncated": dict(job["output_truncated"]),
                  "namespace_lost": False}
        if job["result"] is not None:
            final = dict(job["result"])
            result["result_status"] = final.pop("status", None)
            result.update(final)
        return result

    @tool
    async def job(self, code: str, timeout_seconds: float = 900):
        """Start a Python cell without waiting; return job_id for check/wait/interrupt.

        One cell at a time in the persistent namespace. Deadline includes startup
        and worker RPCs (up to 900s). Jobs live in this worker, not across restarts.
        """
        if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_CODE:
            raise ValueError("code must be a string of at most 128 KiB.")
        request = {"operation": "execute", "code": code, "stream": True}
        self._validate(request, timeout_seconds)
        if self._lock.locked() or self._active_job is not None:
            raise RuntimeError("Python session is busy; check/wait or interrupt the active job first.")
        # Reserve the namespace before scheduling; never silently queue another cell.
        while len(self._jobs) >= 32:
            del self._jobs[next(iter(self._jobs))]
        job = {"id": uuid4().hex, "status": "running", "stdout": "", "stderr": "",
               "output_chars": {"stdout": 0, "stderr": 0},
               "output_truncated": {"stdout": False, "stderr": False}, "result": None,
               "session_id": self._session_id, "started_at": time.monotonic(), "finished_at": None,
               "ready": False, "interrupt_requested": False}
        self._active_job = self._jobs[job["id"]] = job
        job["task"] = asyncio.create_task(self._run_job(job, request, timeout_seconds))
        job["task"].add_done_callback(lambda _: self._finish_job(job))
        return {"status": "started", "job_id": job["id"], "timeout_seconds": timeout_seconds}

    @tool
    async def check(self, job_id: str):
        """Read job status and live stdout/stderr tails without waiting.

        Running tails keep the last 12,000 characters per stream; output_chars
        counts received text until completion, then actual generated characters.
        output_truncated flags capture/live overflow. Finished jobs return bounded output/exports.
        Up to 32 job records survive in this worker, never across restart.
        """
        return self._snapshot(self._get_job(job_id))

    @tool
    async def wait(self, job_id: str, timeout_seconds: float = 10):
        """Wait up to 60s for a job, returning fresh output on completion or timeout.

        Steering ends this wait early without stopping the job. The wait window
        never extends the cell's own deadline. Use interrupt to stop computation.
        """
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or not 0 <= timeout_seconds <= 60):
            raise ValueError("wait timeout_seconds must be within 0..60.")
        job = self._get_job(job_id)
        deadline, reason = time.monotonic() + timeout_seconds, "timeout"
        while not job["task"].done():
            activity = self.agent.agentic_loop.wait_for_activity(0)
            if activity != "timeout":
                reason = activity
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.wait({job["task"]}, timeout=min(remaining, .05))
        if job["task"].done():
            reason = "job_completed"
        return {**self._snapshot(job), "wait_reason": reason}

    def _signal_interrupt(self):
        if self._process is not None:
            with suppress(ProcessLookupError):
                os.kill(self._process.pid, signal.SIGUSR1)

    @tool
    async def interrupt(self, job_id: str):
        """Request soft cell interruption, preserving process and namespace.

        Returns immediately; check/wait confirms completion. Cleanup follows Python
        signal/cancellation semantics, best effort. Native code or a worker RPC may
        delay interruption; code can
        ignore it. Use kill only if namespace loss is acceptable. No silent replay.
        """
        job = self._get_job(job_id)
        if not job["task"].done() and not job["interrupt_requested"]:
            job["interrupt_requested"] = True
            job["status"] = "interrupting"
            if job["ready"]:
                self._signal_interrupt()
        return self._snapshot(job)

    @tool
    async def kill(self, job_id: str):
        """Force-stop a Python job/process group, losing the entire namespace.

        Does not run finally blocks. Files and worker-tool side effects survive;
        already finished jobs are unchanged. Never silently replays the cell.
        """
        job = self._get_job(job_id)
        if not job["task"].done():
            self.shutdown(cancel_job=False)
            job["task"].cancel()
            await asyncio.gather(job["task"], return_exceptions=True)
        return self._snapshot(job)

    @tool
    async def reset(self):
        """Destroy the Python session and all in-memory values. Files are not deleted."""
        previous = self._session_id
        if self._active_job is not None:
            await self.kill(self._active_job["id"])
        async with self._lock:
            self.shutdown()
            return {"status": "reset", "previous_session_id": previous, "namespace_lost": True}
