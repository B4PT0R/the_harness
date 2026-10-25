# Persistent Python, isolated from the worker

Use `execute` for Pynteract cells with persistent Python objects and top-level
`await`. This is a separate local process with the account's real permissions,
not a security sandbox. Do not send private data externally without authorization.
Native results stay in that process; they are not automatically printed,
serialized, displayed or added to conversation context. Assign values to names
(or reuse `_`). Inspect a small projection with `agent.export(value, name="result")`.
Only strict JSON values are accepted, without pickle, repr or custom encoders.

Inside a cell, `agent` is a limited proxy, not the worker's Agent:
- `await agent.tools(query=None)` returns active worker tool schemas.
- `await agent.call("namespace.tool", user_feedback="…", **arguments)` runs a
  worker tool through its normal pipeline (history, events, hooks, outputs).
  The return is `{status, message_ids, outputs}`. Each output has `format` and
  `value`: complete rendered JSON is decoded; non-JSON/truncated output is text;
  artifacts/images are canonical JSON descriptions, not native objects or bytes.
  Referenced outputs already exist in conversation; do not present them twice.
  Worker tool failures return `status="failure"`; lookup/protocol failures raise.
  Only active tools resolve. No recursive Pynteract calls. A tool call's permission
  requirements still apply: the proxy does not grant extra authorization.
- `@agent.python.register` (optionally `name="…"`) registers a session-local Python
  function. `await agent.python.call("name", **kwargs)` returns its original Python
  object. `agent.python.list()` lists these functions. They are not worker tools.
  `call_python` can invoke one from outside with JSON kwargs and retain its native
  result under `save_as`; use `execute` to export a subsequent projection.
- `await agent.artifact(kind, payload, user_feedback="…")` delegates explicitly to
  `artifacts.show_artifact`. Write files with Python libraries, pass their local
  paths, and consult the normal artifact catalogue. Nothing is published implicitly.

Cells are serialized. Await/join work before returning; leftover asyncio tasks
are cancelled. Interactive stdin is unavailable. Python stdout/stderr capture is
limited to 32 Ki characters per cell; excessive output aborts the cell. Native
file-descriptor output is discarded. Code is limited to 128 KiB, JSON frames to
1 MiB; use files for large exports. This is not an RSS, disk or OS resource sandbox.

Timeouts (default 60s, max 900s), interruption or process exit destroy the session
process group and its namespace; `namespace_lost` reports transport failures.
The next call starts a fresh session, never silently replays code. Worker-tool
side effects and files are not rolled back; an already-running synchronous worker
tool can continue after cancellation. Check its state before retrying. A normal
cell exception preserves earlier mutations and objects. `reset` explicitly kills
all in-memory state; disabling the plugin or restarting the worker does too.
