# Harness Pynteract plugin

This vertical slice owns its process, bounded JSON transport, worker adapter,
Python proxy, instructions and documentation. Composition registration and the
pinned `pynteract==1.0.0` dependency are its only non-test integration points.
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
results are never implicitly converted with `str`, `repr` or display protocols.

## Lifecycle and limits

- POSIX transport: anonymous socketpair inherited by a new process group. No
  network listener, authentication token, server plugin, or public endpoint.
- Lazy start, one process per loaded extension; one cell at a time. Pynteract
  uses its own namespace, `_`, magics, compiler state and bounded history.
- No startup script is run; normal `Shell.arun`, not the interactive REPL.
- Code 128 KiB; each newline-delimited JSON frame 1 MiB; Python output 32 Ki
  characters per cell (abort on overflow). Captured diagnostics are also bounded.
  Native fd stdout/stderr go to `/dev/null`; stdin is unavailable.
- Default deadline 60 seconds, configurable per call up to 900, covering startup,
  the cell and worker RPCs. Timeout/cancellation/crash kills the process group,
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
  memory and spawn detached processes. Large single writes can allocate memory
  before the output hook detects overflow. No Windows transport is claimed yet.

Tests: `uv run pytest -q tests/general/test_pynteract_plugin.py`.
