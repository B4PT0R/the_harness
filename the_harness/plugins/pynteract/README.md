# Harness Pynteract plugin

This vertical slice owns its process, bounded JSON transport, worker adapter,
Python proxy, instructions and documentation. Composition registration and the
local editable `pynteract` dependency are its only non-test integration points.
No Framework changes, server routes, UI code, pickle or generic object serializer.

## Example

`pynteract.execute` accepts `code` and optional `timeout_seconds`:

```python
from collections import Counter

@agent.python.register
def counts(words):
    return Counter(words)

counter = await agent.python.call("counts", words=["a", "b", "a"])
agent.export(dict(counter), name="counts")
```

Or invoke `pynteract.call_python(name="counts", arguments_json='{"words":["c"]}',
save_as="counter")`. Its return value remains a genuine Counter inside the child.
A later cell can use it without serializing/reconstructing it.

Worker tool access uses a separate path:

```python
schemas = await agent.tools("documents")
reply = await agent.call("documents.read_document", document_id="…", offset=0,
                         limit=1000, user_feedback="Je lis le passage utile du document.")
if reply["status"] == "success":
    page = reply["outputs"][0]["value"]
    agent.export(page)
```

`agent.call` returns the **canonical rendered/bounded output**, decoded as JSON
when complete; otherwise `format="text"`. It does not bypass output hooks or promise
access to a worker function's original object. Artifacts/images return canonical
metadata. Worker outputs are persisted once by the normal pipeline, and the proxy
returns their IDs. Proxy RPC is serviced directly while awaiting the outer cell,
not queued behind that cell on the worker, avoiding self-deadlock.

For rich returns, put the function in the Python session (import it and register
it), not in a worker extension. `agent.python.register(function, name="loader")`
and decorator syntax both work. Synchronous and async functions are supported;
intentionally blocking code blocks only the child, subject to its outer timeout.
The initial registry is empty; user-installed libraries are not installed on demand.

File/artifact export reuses the existing publisher:

```python
from pathlib import Path
path = Path("/tmp/pynteract-report.txt")
path.write_text("report", encoding="utf-8")
await agent.artifact("file", {"path": str(path), "title": "Report"},
                     user_feedback="Je présente le rapport produit par Python.")
```

This explicit call publishes immediately through `artifacts.show_artifact`;
failed cells do not undo already completed publication or tool side effects.
`agent.export` freezes its strict JSON projection immediately and returns it in
that cell's result. Custom objects, NaN and infinity are rejected. Native cell
results stay in the namespace, but `display_mode="last"` includes the last
expression's `repr` in stdout. Assign the result to suppress display. Cell
tracebacks appear only in stderr, with no duplicate `error` or `result_type` field.
Transport/entry-point failures still use `error`; `call_python` retains type metadata.

## Long-running cells

`job(code, timeout_seconds=900)` returns immediately with a `job_id`, running in
this extension's persistent worker event loop while Python stays in its separate
process. `check(job_id)` is nonblocking; `wait(job_id, timeout_seconds=10)` waits
up to 60 seconds for completion and returns the same fresh snapshot. Steering or
cancelling **the wait** does not cancel the job or extend its hard deadline.
Jobs continue between conversation turns; no automatic notification/wake is added.

- While running, `stdout` / `stderr` contain rolling **last 12,000 characters**
  per stream, and `output_chars` counts all characters received. Repeated checks
  are idempotent snapshots, not destructive reads or a duplicate full transcript.
- Synchronous Pynteract `stdout_hook` / `stderr_hook` callbacks send incremental
  frames through the existing socket. This also exposes progress from blocking
  Python code (without `await`); newline, explicit flush or Pynteract's buffer
  threshold delivers text. Arbitrary native fd writes are still discarded.
- The sole transport reader aggregates notifications and services RPC through the
  normal worker pipeline. No second reader competes for RPC/results. Output can
  wait behind an in-flight worker RPC; `check` never waits for that RPC to finish.
- Final snapshots replace the live tail with the usual bounded first/last output
  and include exports, `result_status` (`ok`/`error`/`interrupted`), and `namespace_lost`.
  Job status is `running`, `interrupting`, `completed`, `failed`, `timed_out`,
  or `interrupted`. Transport failure, timeout and interruption retain the latest tail.
- Only one job/cell can run in the namespace. `job`, `execute` and `call_python`
  reject a new cell while a job owns it, rather than secretly queueing it.
  Ordinary foreground calls remain serialized as before.
- `interrupt(job_id)` requests soft interruption via SIGUSR1 and
  `Shell.interrupt()`. It returns `interrupting`; check/wait confirms completion.
  An interrupted cell retains the process, object identities and prior mutations
  (`namespace_lost=false`). It is not a rollback. Finished jobs are unchanged.
- Soft interruption follows Python exception/cancellation semantics. Native code
  can delay it, user code can catch it, and in-flight worker RPCs must drain before
  another cell. Cleanup is best effort: asynchronous signal delivery is not a
  transaction and cannot guarantee every user finally block (notably tight
  single-line loops on CPython 3.12). The library installs no global handler;
  this isolated POSIX child owns its SIGUSR1 handler.
- `kill(job_id)` forcibly kills the process group and loses the namespace, without
  user cleanup. `reset` also kills an active job; shutdown/deactivation stop it.
  Files and completed side effects survive.
- Up to 32 job records are retained in this worker (oldest evicted on new start).
  They and all Python objects are lost on worker/server restart. Success retains
  native objects for later cells; no cell is automatically replayed.

The parent-side live tail is bounded, **not the child process's memory usage**:
Pynteract still captures full cell output, and transport buffering can grow during
very verbose synchronous code. Use a local log file for exhaustive long-run logs.

## Lifecycle and limits

- POSIX transport: anonymous socketpair inherited by a new process group. No
  network listener, authentication token, server plugin, or public endpoint.
- Lazy start, one process per loaded extension; one cell at a time. Pynteract
  uses its own namespace, `_`, magics, compiler state and bounded history.
- No startup script is run; normal `Shell.arun`, not the interactive REPL.
- Code 128 KiB; each newline-delimited JSON frame 1 MiB. Each returned output
  stream keeps first/last text totaling 4,000 tokens plus an omission marker via
  `the_framework.utils.tokens.truncate_middle`. Verbose output does not abort
  execution. The Shell captures full output in memory before truncation.
  Native fd stdout/stderr go to `/dev/null`; stdin is unavailable.
- Foreground default deadline 60 seconds; jobs default to 900. Both accept a
  per-call deadline up to 900 seconds, covering startup,
  the cell and worker RPCs. Timeout, foreground cancellation or crash kills the process group,
  reaps the child, reports state loss and lazily starts a new session next call.
  Already performed effects are **not** rolled back; an in-flight synchronous
  worker tool may continue after cancellation. Never auto-replay a cell.
- Cell exceptions preserve earlier mutations. Exports are explicit and may already
  exist on error. Async tasks left running by a cell are cancelled before reply;
  RPCs already sent are drained before the next cell (under the same deadline).
  User threads and detached OS children must be joined/cleaned up by their author.
- `reset`, deactivation, shutdown and server restart lose native in-memory state;
  files survive. No recovery, replay, checkpointing or pickle persistence.
- This is fault isolation, **not a security or memory sandbox**. Arbitrary Python
  has the local account's permissions, can modify process internals, allocate
  memory and spawn detached processes. Output capture is not memory-bounded.
  No Windows transport is claimed yet.

Tests: `uv run pytest -q tests/general/test_pynteract_plugin.py`.
