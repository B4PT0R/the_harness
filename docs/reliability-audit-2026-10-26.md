# Reliability audit — 26 October 2026

Scope: verify the supplied GitHub audit against the local Framework/Harness/
Pynteract stack, correct P0–P2 in coherent batches, and diagnose P3 without a
structural rewrite. Changes are local commits, not a deployment. Modict's
concurrent changes were inspected and consumed, not modified.

## Corrections and evidence

| Area | Local change | Verification |
| --- | --- | --- |
| Public dependency mismatch | Framework `29bcc31`, Harness `b871909`; SDK 0.5.9 release separately authorized and published | Initial isolated public installation and 25 Python-plugin tests; SDK 312 offline tests. Later output changes require the still-local Pynteract 1.2.0 candidate. |
| Persistence commit semantics | Framework `bf96d93` | Serialization, file fsync and replace errors preserve the previous snapshot. `os.replace` commits; subsequent directory-sync OS errors are logged without reverting memory. Session mutations and mapping/registry stores exercised with fault injection. |
| Event-stream producer ownership | Framework `bf96d93` | Normal completion, producer error, consumer cancellation and explicit early closure. Producer task cancelled and awaited; cleanup errors observed rather than lost. |
| Modict contract alignment | Framework `06c04f8`, Harness `e5e183d`; consume Modict `ce8a1c9` | `default_required`, inherited `MISSING`, explicit overrides and wire-schema exceptions tested. No changes made to Modict. |
| Python output resources | Pynteract `dd9e92e`, Harness `823eac3` | Per-stream capture, noncumulative hook delivery, bounded queued transport, truncation flags/counts and live tails. Large writes, many small writes, slow consumers and interruption covered; Pynteract 332 passed / 4 skipped. |
| Attachment ingress | Framework `843465f`, Harness `07be46d` | Configurable 64 MiB default, actual streamed bytes checked before multipart parsing, 1 MiB framing allowance, shared copy quota, 32 files. Controlled rejection, parser/form cleanup, transactional rollback and no overwrite. URLencoded validation compatibility retained. Framework final suite: 1,168 passed / 4 skipped. |
| Installed integration | Harness `fe2b3b9` | Four fresh wheels, clean venv, released SDK 0.5.9, dependency check and imports asserted inside site-packages. Bootstrapped starter and copied tests outside source trees: 45 Framework + 45 Harness passed, no skips. Includes actual worker startup/recreation, authentication, persistence, specialists, Python RPC/output/interruption, receipts and reset rollback. |

Reproduce the installed-candidate gate with:

```sh
python3 scripts/check-wheel-integration.py
```

See `tests/README.md` for execution requirements and distinction between durable
contracts and implementation feedback. The gate is suitable for a CI runner
with the four sibling candidates checked out; no hosted workflow run is claimed.

Final verification on the resulting sources:

- Framework Python: **1,168 passed / 4 skipped**, including the configured browser
  checks; expected Starlette TestClient deprecation warning only. Log:
  `/tmp/harness-audit-uploads-framework-verified.log`.
- Harness Python: **453 passed / 2 skipped** in 312.84 seconds, including browser,
  startup and mobile-access contracts. Only opt-in real Piper/Docling tests skipped.
  Log: `/tmp/harness-audit-final-harness.log`.
- JavaScript: **103 Harness + 40 Framework starter passed**, no skips. Logs:
  `/tmp/harness-audit-final-{harness,framework}-js.log`.
- Installed-wheel gate: **90 passed / 0 skipped**. Log:
  `/tmp/harness-audit-wheel-integration.log`; wheels/venv/JUnit reports retained in
  `/tmp/hw-qpihtwxc`.
- Previously intermittent mobile revocation test: **10/10 additional isolated
  runs passed** with short `/tmp/hmr-final-*` roots, each starting its own test
  application. The complete current suite also passed. This does **not** establish
  the cause or prove the old WebSocket cleanup cancellation can never recur;
  no production fix was invented and no assertion/threshold was weakened.

Startup/recreation and revocation are therefore passing in the current controlled
setup. Long Unix-socket-path failures are separately avoided by the short gate
workspace, not attributed to application behavior. No real phone or installed
service was involved in the revocation repetitions.

## Limits that remain intentional

- Directory fsync failure after replacement means the new snapshot is committed
  and memory stays coherent, but crash/power-loss durability may be degraded.
  Logging this does not turn the failed synchronization into a success.
- Cancelling an asyncio waiter cannot forcibly stop arbitrary synchronous code
  running in a thread. Stream cleanup detaches callbacks; use explicit async
  iterator closure (`aclosing`) when a consumer exits early.
- Output budgets bound captured/queued output, not arbitrary Python allocations,
  native libraries, user-created objects or total process RSS. Pynteract remains
  a real-permissions execution process, not a resource/security sandbox. Standalone
  library defaults remain unlimited unless a caller chooses capture limits.
- Upload quotas apply to the application ingress stream and file copy; they do
  not promise a bound on all HTTP-server/OS buffering or aggregate concurrent
  clients. `max_upload_bytes=None` is an explicit opt-out.
- Tests use isolated data, fake credentials and controlled transports. They do
  not prove the currently running application has loaded edited source, mobile
  deep-sleep delivery, native alarm receipt or real backend inference.

## Release and activation boundary

SDK 0.5.9 was published with explicit permission. No other package publication,
Git push, installed-service restart, remote exposure or mobile action was done.

The final candidate stack is **not yet established as publicly installable**:

1. Modict's local contract changes currently retain version 0.4.20. A wheel built
   here can differ from released bytes with the same version number. Coordinate
   a distinct release/version and dependency minimum before claiming public
   compatibility; do not overwrite a published version.
2. Pynteract 1.2.0 is an unposted local candidate, now required by the Harness's
   bounded-capture integration. Publishing needs renewed authorization.
3. Framework/Harness changes are also local. Rerun the public-index-only gate
   after the required releases, without sibling sources or candidate wheels.
4. Activating runtime changes and validating reconnection in the user's live
   conversation requires an explicitly authorized supervised restart. Passing
   subprocess tests is not live activation.

## P3 — diagnosis only

The architectural observation remains relevant, but file size/import depth alone
is not a reproduced regression:

- `the_framework/server/composition/application.py` is 1,290 lines at `843465f`.
  It contains declarations (`BuildContext`, `ServerExtension`, `Plugin`,
  `Application`), compilation/dependency resolution, global/session lifecycle
  and ASGI assembly. Those responsibilities are distinguishable, although they
  remain colocated. A later concrete change can extract one cohesive phase;
  a new manager layer or wholesale rewrite is not justified by this audit.
- The short composition API is already exported from `the_framework` and
  `the_framework.server`. Harness still consumes deeper runtime/protocol,
  browser-RPC, security and transport modules. Deep imports are not automatically
  private, but their supported contract should be explicit. Start by documenting
  the interfaces actually consumed, not by re-exporting every internal helper
  or maintaining speculative compatibility adapters.
- Modict still concentrates substantial model/type behavior in
  `modict/core/src/_modict.py` and
  `modict/typechecker/src/_typechecker.py` (2,332 and 2,025 lines respectively at
  the inspected checkout). This supports a maintainability concern, not a claim
  of a new fault. Future simplification belongs in Modict with its own tests and
  coordinated consumer changes; no such refactor was attempted here.

The useful next boundary is public contracts with focused regression tests,
followed by small responsibility extractions when real changes require them.
