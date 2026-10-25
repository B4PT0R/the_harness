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
        return self

    def shutdown(self):
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
        self.shutdown()
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
            self.shutdown()
            raise
        finally:
            child.close()
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

    async def _exchange(self, request):
        await self._start()
        await send(self._writer, request)
        while True:
            reply = await receive(self._reader)
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

    async def _request(self, request, timeout_seconds):
        if (not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool)
                or not 0 < timeout_seconds <= 900):
            raise ValueError("timeout_seconds must be greater than zero and at most 900.")
        encode(request)
        async with self._lock:
            try:
                result = await asyncio.wait_for(self._exchange(request), timeout_seconds)
                return {**result, "session_id": self._session_id, "namespace_lost": False}
            except asyncio.CancelledError:
                self.shutdown()
                raise
            except Exception as error:
                previous = self._session_id
                self.shutdown()
                return {"status": "error", "error": f"{type(error).__name__}: {error}",
                        "session_id": previous, "namespace_lost": True}

    @tool
    async def execute(self, code: str, timeout_seconds: float = 60):
        """Execute a persistent Pynteract cell, with top-level await and proxy agent.

        Native results stay in the session (including _); only stdout/stderr,
        type, errors and agent.export JSON projections return. Timeout/crash
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

    @tool
    async def reset(self):
        """Destroy the Python session and all in-memory values. Files are not deleted."""
        async with self._lock:
            previous = self._session_id
            self.shutdown()
            return {"status": "reset", "previous_session_id": previous, "namespace_lost": True}
