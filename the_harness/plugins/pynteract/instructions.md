# Persistent Python, isolated from the worker

Use `execute` for Pynteract cells with persistent Python objects and top-level
`await`. This is a separate local process with the account's real permissions,
not a security sandbox. Do not send private data externally without authorization.
Native results stay in that process (including `_`). The Shell runs in `last`
mode: the last expression’s `repr` is included in stdout, and tracebacks in stderr
without a duplicate error field. Assign results to suppress their display. For a
structured projection, use `agent.export(value, name="result")`: only strict JSON
values are accepted, without pickle or custom encoders.

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

For long runs use `job(code, timeout_seconds=900)`; its `job_id` works with
`check`, `wait`, `interrupt` and `kill`. `check` returns immediately; `wait` waits at most
60s (default 10), ending early for steering without cancelling computation.
Jobs continue between turns but do not schedule a completion wake. Poll at useful
intervals, not in a tight loop. Hooks aggregate stdout/stderr as code runs,
including blocking synchronous code: while running the snapshot holds the last
12,000 characters per stream, with total `output_chars`; final snapshots contain
usual bounded output, exports and `result_status`. Checks are repeatable snapshots,
not destructive reads. Up to 32 records survive in this worker, not a restart.
A job reserves the namespace: another job/execute/call_python is rejected until it
finishes. `interrupt` requests soft interruption and returns `interrupting`; use
check/wait to confirm `interrupted` with `namespace_lost=false`. Prior mutations
and object identities survive. Native calls can delay delivery; code can ignore
it, and user cleanup is best effort under Python signal/cancellation semantics.
`kill` forcibly stops the process group and **loses the namespace**, without user
cleanup. Finished jobs are unchanged. `reset` kills an active job.
Worker RPC uses the same canonical pipeline; output may wait behind a slow RPC.

Foreground cells are serialized. Await/join work before returning; leftover asyncio tasks
are cancelled. Interactive stdin is unavailable. Returned stdout/stderr are each
centrally truncated to first/last text totaling 4,000 tokens (plus an omission
marker), using the Framework helper. Verbose output does not abort the cell; the
Shell captures it in memory before truncation. Native file-descriptor output is
discarded. Code is limited to 128 KiB, JSON frames to 1 MiB; use files for large
exports. This is not an RSS, disk or OS resource sandbox.

Timeouts (foreground default 60s, job default 900s, max 900s), forced kill,
foreground cancellation or process exit destroy the session
process group and its namespace; `namespace_lost` reports transport failures.
The next call starts a fresh session, never silently replays code. Worker-tool
side effects and files are not rolled back; an already-running synchronous worker
tool can continue after cancellation. Check its state before retrying. A normal
cell exception preserves earlier mutations and objects. `reset` explicitly kills
all in-memory state; disabling the plugin or restarting the worker does too.
