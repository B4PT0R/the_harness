# The Harness tests

Classify tests by the guarantee they protect and its intended lifetime:

- `general/`: deliberately durable behavior and stable API/application contracts.
  Assert observable guarantees rather than incidental implementation details.
- `agentic/`: empirical feedback for ongoing agent-driven work, experiments and
  evolving implementation choices. These checks may be revised or removed.
- `fixtures/`: shared doubles, browser setup and subprocess helpers, without
  collected tests. Test modules must not import other test modules.

Conversation recovery, artifacts and their replay, provider ephemerality,
security, desktop readiness, client modes and UI interactions belong in `general`.
Current prompt wording, the product plugin catalogue, systemd wiring and
React render-count measurements belong in `agentic`.

A unit, integration, browser or live test can belong to either layer. Authorship
is irrelevant. Keeping a contract here does not forbid an intentional redesign:
update the relevant consumers and contract together when that design changes.

During each related batch, review agentic checks for obsolete assumptions,
redundancy and coupling to implementation details. Remove those that no longer
provide useful feedback. Promote a check to `general/` when its guarantee is
intentionally adopted; never delete a durable guarantee just to hide a regression.

Run the complete Python suite from the repository root:

```sh
uv run pytest -q
```

To select a layer, append `tests/general` or `tests/agentic`. Both are collected
by the default command; no special pytest marker is needed.

## Execution requirements (independent of general/agentic)

| Check | Requirements and boundary |
| --- | --- |
| Offline Python contracts | Python dependencies; some spawn isolated workers and loopback servers. No real backend inference or account-credit redemption. The autouse quota fixture rejects live SDK creation. |
| Browser contracts | Node dependencies plus the Chromium revision matching the environment's Playwright. Fixtures skip when unavailable. `PLAYWRIGHT_BROWSERS_PATH` selects an existing cache; do not assume sibling repositories share a revision. |
| Native desktop lifecycle | Explicit `PLAYWRIGHT_BROWSERS_PATH`; relevant Framework window-close/download checks also require Xvfb/xdotool. These start disposable processes, not installed user services. |
| Piper/Docling integration | Explicit `HARNESS_TTS_LIVE=1` / `HARNESS_DOCUMENTS_LIVE=1` and already installed runtime/models. Normal test runs do not install or download them. |
| Framework backend/voice live | Explicit `STARTER_LIVE_TESTS=1`; real credentials, network and account quota. Not part of offline verification. |
| Installed services and devices | Separate authorized manual acceptance: supervised restart, reconnect, remote/mobile delivery and sound. Passing isolated tests does not establish activation or human receipt. |

JavaScript tests use the same split under `ui/tests/`.
Run `npm test` from the repository root.
Node discovers both layers, including newly added agentic tests.

## Installed-wheel integration gate

From a workspace containing sibling `modict`, `pynteract`, `the_framework` and
`the_harness` checkouts:

```sh
python3 scripts/check-wheel-integration.py
```

This local/CI entry point requires `uv`, Python 3.12 and package-index access for
build/runtime/test dependencies. It builds all four candidates, creates a fresh
virtualenv, installs those wheels with the released `codex-backend-sdk==0.5.9`,
runs `uv pip check` and asserts package imports resolve inside that virtualenv.
It bootstraps the packaged starter outside the checkouts, then copies and runs
selected durable tests outside their source trees:

- atomic persistence and session commit/recovery;
- authenticated worker startup, configuration and history across server recreation;
- primary/private worker composition;
- Python plugin RPC, execution, bounded output, cancellation and recovery;
- persistent remote prompt receipts and selective-reset rollback.

No editable dependency, live backend request, installed-service restart, browser,
mobile action or publication is involved. The short `/tmp/hw-*` workspace avoids
Unix socket path-length artifacts. Wheels, virtualenv, temporary data and JUnit
reports are retained there on success or failure; the caller can archive the
reports in CI and remove the workspace afterwards. Builds/installations may use
the network, so this gate tests offline *behavior*, not an air-gapped installer.
It complements, rather than replaces, the complete source and browser suites.

A passing gate validates the current checkout combination, **not** availability
of those changes on PyPI or a hosted CI run. In particular the local Modict
contract may share a version number with different published bytes, and Pynteract
1.2.0 remains a local candidate until separately authorized and released. A
public-install gate must be rerun after the required releases; do not advertise
an installable public stack based only on this candidate gate.
