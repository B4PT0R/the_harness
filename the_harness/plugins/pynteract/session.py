"""Child-process entry point: rich values never leave this interpreter implicitly."""

import asyncio
import inspect
import json
import socket
import signal
import sys

from pynteract import ExecutionInterrupted, Shell
from the_framework.utils.tokens import truncate_middle

from .protocol import (MAX_FRAME, MAX_OUTPUT_TOKENS, MAX_CAPTURE_CHARS,
                       MAX_STREAM_BYTES, encode, receive, send)


class OutputRelay:
    """Bound cumulative wire output, including JSON overhead, per cell.

    Sync Python cannot await drain on its own event loop. Rather than enqueue
    unlimited notifications, stop live delivery at a fixed budget and signal it
    once per stream. RPC/results still drain normally. No background writer task
    or unbounded thread queue is needed.
    """

    def __init__(self, writer):
        self.writer = writer
        self.reset(False)

    def reset(self, enabled):
        self.enabled = enabled
        self.remaining = MAX_STREAM_BYTES
        self.truncated = {"stdout": False, "stderr": False}

    def output(self, stream):
        def capture(text, _buffer):
            if not self.enabled or self.truncated[stream]:
                return
            for offset in range(0, len(text), 8192):
                frame = encode({"type": "output", "stream": stream,
                                "text": text[offset:offset + 8192]})
                if len(frame) > self.remaining:
                    self.truncated[stream] = True
                    self.writer.write(encode({
                        "type": "output", "stream": stream, "truncated": True,
                        "text": "\n[live output truncated: transport budget reached]\n"}))
                    break
                self.remaining -= len(frame)
                self.writer.write(frame)
        return capture


class PythonTools:
    """Session-local Python functions, deliberately not worker tools."""

    def __init__(self):
        self._functions = {}

    def register(self, function=None, *, name=None):
        def add(func):
            key = name or func.__name__
            if key in self._functions:
                raise ValueError(f"Python tool already registered: {key}")
            self._functions[key] = func
            return func
        return add(function) if function is not None else add

    def list(self):
        return [{"name": name, "signature": str(inspect.signature(func)),
                 "description": inspect.getdoc(func) or ""}
                for name, func in self._functions.items()]

    async def call(self, name, **arguments):
        result = self._functions[name](**arguments)
        return await result if inspect.isawaitable(result) else result


class AgentProxy:
    def __init__(self, reader, writer):
        self.python = PythonTools()
        self._reader, self._writer = reader, writer
        self._lock = asyncio.Lock()
        self._exports = {}
        self._pending_replies = set()

    async def _rpc(self, method, **payload):
        async with self._lock:
            self._writer.write(encode({"type": "rpc", "method": method, **payload}))
            async def read_reply():
                await self._writer.drain()
                return await receive(self._reader)

            pending = asyncio.create_task(read_reply())
            self._pending_replies.add(pending)
            pending.add_done_callback(self._pending_replies.discard)
            try:
                reply = await asyncio.shield(pending)
            except asyncio.CancelledError:
                # Once sent, consume this reply before releasing the RPC lock.
                # Otherwise a cancelled cell task leaves it for the next cell.
                # The outer deadline still bounds a worker that never replies.
                await pending
                raise
            if reply.get("type") != "rpc_result":
                raise RuntimeError("Unexpected worker RPC response.")
            if "error" in reply:
                raise RuntimeError(reply["error"])
            return reply["value"]

    async def tools(self, query=None):
        """Discover active worker tool schemas (not Python-local functions)."""
        return await self._rpc("tools", query=query)

    async def call(self, name, *, user_feedback, **arguments):
        """Call namespace.tool through the worker's normal pipeline."""
        return await self._rpc("call", name=name, arguments=arguments, user_feedback=user_feedback)

    def export(self, value, *, name="result"):
        """Freeze an explicit JSON projection, without repr or custom encoders."""
        exports = {**self._exports, name: value}
        frozen = json.loads(encode({"exports": exports}))
        self._exports = frozen["exports"]

    async def artifact(self, kind, payload, *, user_feedback):
        """Publish via artifacts.show_artifact; not an implicit display hook."""
        return await self.call("artifacts.show_artifact", kind=kind, payload=payload,
                               user_feedback=user_feedback)


async def main(fd):
    reader, writer = await asyncio.open_connection(sock=socket.socket(fileno=fd), limit=MAX_FRAME)
    agent = AgentProxy(reader, writer)

    def no_input(*args):
        raise RuntimeError("Interactive input is unavailable in a Pynteract session.")

    relay = OutputRelay(writer)

    def started(code):
        if relay.enabled:
            writer.write(encode({"type": "started"}))
        return code

    shell = Shell(namespace={"agent": agent}, display_mode="last", history_size=10,
                  capture_limit=MAX_CAPTURE_CHARS, hook_buffer=False,
                  pre_run_hook=started, stdin_hook=no_input,
                  stdout_hook=relay.output("stdout"), stderr_hook=relay.output("stderr"))
    # A Python signal handler runs in the interpreter's owning thread even when
    # synchronous user code blocks its event loop. Idle delivery is a no-op.
    previous_handler = signal.signal(signal.SIGUSR1, lambda *_: shell.interrupt())
    try:
        await send(writer, {"type": "ready"})
        while True:
            request = await receive(reader)
            relay.reset(request.get("stream", False))
            agent._exports = {}
            existing_tasks = asyncio.all_tasks()
            try:
                if request["operation"] == "execute":
                    response = await shell.arun(request["code"])
                    result = {"status": "error" if response.exception else "ok",
                              "stdout": truncate_middle(response.stdout, max_tokens=MAX_OUTPUT_TOKENS),
                              "stderr": truncate_middle(response.stderr, max_tokens=MAX_OUTPUT_TOKENS),
                              "output_chars": {name: stats["written_chars"]
                                               for name, stats in response.output_stats.items()},
                              "output_truncated": {name: stats["truncated"] or relay.truncated[name]
                                                   for name, stats in response.output_stats.items()},
                              "exports": agent._exports}
                elif request["operation"] == "python_call":
                    target = request["save_as"]
                    if not target.isidentifier() or target.startswith("_") or target == "agent":
                        raise ValueError("save_as must be a public Python identifier other than agent.")
                    value = await agent.python.call(request["name"], **request["arguments"])
                    shell.namespace[target] = value
                    result = {"status": "ok", "saved_as": target,
                              "result_type": type(value).__name__, "exports": agent._exports}
                else:
                    raise ValueError("Unknown session operation.")
            except ExecutionInterrupted:
                result = {"status": "interrupted", "exports": agent._exports}
            except Exception as error:
                result = {"status": "error", "error": truncate_middle(f"{type(error).__name__}: {error}",
                                                   max_tokens=MAX_OUTPUT_TOKENS),
                          "exports": agent._exports}
            finally:
                # Cells must join their async work. Do not let late RPCs steal the
                # next cell's response or capture output into an expired context.
                # Protocol readers must drain their reply, not be cancelled
                # alongside the user tasks waiting on them.
                pending = asyncio.all_tasks() - existing_tasks - agent._pending_replies
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
            try:
                await send(writer, {"type": "result", "value": result})
            except ValueError as error:
                await send(writer, {"type": "result", "value": {"status": "error", "error": str(error)}})
    finally:
        signal.signal(signal.SIGUSR1, previous_handler)
        shell.close()
        writer.close()
        await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1])))
