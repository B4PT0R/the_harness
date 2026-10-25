"""Child-process entry point: rich values never leave this interpreter implicitly."""

import asyncio
import inspect
import json
import socket
import sys

from pynteract import Shell

from .protocol import MAX_FRAME, MAX_OUTPUT, encode, receive, send


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

    async def _rpc(self, method, **payload):
        async with self._lock:
            self._writer.write(encode({"type": "rpc", "method": method, **payload}))
            try:
                await self._writer.drain()
                reply = await receive(self._reader)
            except asyncio.CancelledError:
                # Once sent, consume this reply before releasing the RPC lock.
                # Otherwise a cancelled cell task leaves it for the next cell.
                # The outer deadline still bounds a worker that never replies.
                await receive(self._reader)
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
    captured = 0

    def output(data, buffer):
        nonlocal captured
        captured += len(data)
        if captured > MAX_OUTPUT:
            raise ValueError("Cell output exceeds 32 Ki characters; write a file instead.")

    def no_input(*args):
        raise RuntimeError("Interactive input is unavailable in a Pynteract session.")

    shell = Shell(namespace={"agent": agent}, display_mode="none", history_size=10,
                  stdout_hook=output, stderr_hook=output, stdin_hook=no_input)
    try:
        while True:
            request = await receive(reader)
            captured = 0
            agent._exports = {}
            existing_tasks = asyncio.all_tasks()
            try:
                if request["operation"] == "execute":
                    response = await shell.arun(request["code"])
                    error = response.exception
                    result = {"status": "error" if error else "ok",
                              "stdout": (response.stdout or "")[:MAX_OUTPUT],
                              "stderr": (response.stderr or "")[:MAX_OUTPUT],
                              "result_type": type(response.result).__name__,
                              "exports": agent._exports}
                    if error:
                        result["error"] = str(getattr(error, "enriched_traceback_string", None)
                                              or f"{type(error).__name__}: {error}")[:MAX_OUTPUT]
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
            except Exception as error:
                result = {"status": "error", "error": f"{type(error).__name__}: {error}"[:MAX_OUTPUT],
                          "exports": agent._exports}
            finally:
                # Cells must join their async work. Do not let late RPCs steal the
                # next cell's response or capture output into an expired context.
                pending = asyncio.all_tasks() - existing_tasks
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
            try:
                await send(writer, {"type": "result", "value": result})
            except ValueError as error:
                await send(writer, {"type": "result", "value": {"status": "error", "error": str(error)}})
    finally:
        shell.close()
        writer.close()
        await writer.wait_closed()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1])))
