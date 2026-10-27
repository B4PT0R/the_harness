# Dependency release — 2026-10-27

Authorized by Baptiste: « mettre à jour les dependances pousser et publier ».
No application server restart, client-surface publication or OS change was performed.

## Released state

| Project | Version / commit | Delivery |
| --- | --- | --- |
| Modict | 0.5.0 / `176d5e7` | PyPI wheel + sdist; main + annotated `v0.5.0` pushed |
| Pynteract | 1.2.0 / `7ddfa67` | PyPI wheel + sdist; main + annotated `v1.2.0` pushed |
| Framework | 0.3.0 / `44427c9` | PyPI `b4pt0r-the-framework`, wheel + sdist; main + annotated `v0.3.0` pushed |
| Harness | 0.1.0 / `f95c9f3` | PyPI `b4pt0r-the-harness`, wheel + sdist; main + annotated `v0.1.0` pushed |
| Backend SDK | 0.5.9 | Existing PyPI release reused; no new release |

Modict 0.5.0 removes `require_all` in favor of `default_required`, with explicit
field overrides. Framework 0.3.0 includes the accumulated public composition API
changes documented in its changelog. The minor-version changes are intentional,
not patch releases of the old contracts.

Framework now requires `modict>=0.5.0,<0.6` and `codex-backend-sdk>=0.5.9`.
Harness requires Framework `>=0.3.0,<0.4`, Modict `>=0.5.0,<0.6`, Pynteract
`>=1.2.0,<2` and SDK `>=0.5.9`. Both tracked uv locks were regenerated, and the
Framework/Harness development environments synchronized without restarting the
application. Other dependency versions were not indiscriminately upgraded.

The PyPI name `the-harness` belongs to a different project/account (`SihanXU`,
placeholder 0.0.0 at inspection), not this repository. No upload or implicit
rename was attempted in the first batch. Baptiste then explicitly authorized the
name `b4pt0r-the-harness`; its first publication is recorded below.

## Verification

| Check | Result |
| --- | --- |
| Modict full Python suite | 651 passed |
| Pynteract full Python suite, RuntimeWarning as error | 332 passed, 4 skipped |
| Framework full Python suite | 1,168 passed, 4 skipped |
| Harness full Python suite | 461 passed, 2 skipped |
| Starter JavaScript tests / build | 40 passed / successful |
| Harness JavaScript tests / build | 103 passed / successful |
| Pynteract built-wheel embedding / CLI smoke | Successful |
| Local four-wheel integration | 45 Framework + 45 Harness tests passed |
| Public PyPI + pinned Harness Git integration | 45 Framework + 45 Harness tests passed |

All three published wheels and sdists passed a current isolated Twine metadata
check. The previously installed Twine could not read metadata 2.5; the validator
was updated only in an isolated uv tool environment, not by weakening package
metadata. Wheel and sdist contents were checked for obvious private-file paths.
SHA-256 values from the version-specific PyPI JSON endpoints matched the six
local release artifacts. Remote main hashes were independently checked with
`git ls-remote`, not just inferred from local tracking branches.

The Framework venv initially still had public Modict 0.4.19; syncing the new lock
resolved collection errors. One bootstrap test had a hard-coded Framework 0.2.1
expectation. It now checks that the generated manifest pins the actual installed
distribution version; the entire Framework suite subsequently passed. A third-party
Starlette/AnyIO deprecation warning and a Harness bundle-size warning remain;
neither was suppressed to obtain a pass.

### Public-only installation evidence

Fresh Python 3.12 venv: `/tmp/hp-9nek_hqk/venv`. Installation ran outside checkouts,
with no local wheel arguments, no editable sources and no uv cache:

```sh
uv --no-config pip install --python VENV/bin/python --no-cache --no-sources \
  --default-index https://pypi.org/simple \
  modict==0.5.0 pynteract==1.2.0 b4pt0r-the-framework==0.3.0 \
  'the-harness @ git+https://github.com/B4PT0R/the_harness.git@5f70561d1ed3c462f02bd0f7ad92f1022f82f2c0' \
  codex-backend-sdk==0.5.9 pytest pytest-asyncio 'httpx2>=2.0.0'
```

`--no-sources` is necessary for uv to ignore the Git project's development-only
sibling paths. The initial attempt without it followed those paths and failed;
this was a verification setup issue, not a successful public installation.
A subsequent immediate attempt encountered an index propagation delay; the
final isolated attempt above completed successfully.

`uv pip check` validated all 55 installed distributions. Imports of all five
packages resolved under this venv's `site-packages`. The four index packages
had no `direct_url.json`; Harness metadata confirmed the full Git commit above,
without editable mode. The installed Framework bootstrapped an editable starter
outside all repositories, and the 90 integration tests then passed. Test files
were copied from the verified repositories; production imports were installed
packages, never sibling source trees.

This verifies the Python dependency stack and the selected offline persistence,
worker and Python-plugin contracts, not a fresh full desktop installation or
live model/backend/mobile behavior. Any worker restarts exercised by tests were
temporary test processes, not the active application server.

## Retained local state and evidence

The pre-existing maintenance changes to `the_harness/environment.py` and
`tests/general/test_environment.py` were preserved and excluded from release
commits/pushes. The full Harness source suite included these local changes;
the public integration used the exact pushed commit without them.

Builds and temporary public-verification script: `/tmp/release-20261027/`.
Logs: `/tmp/release-20261027-*-tests.log`,
`/tmp/release-20261027-framework-tests-final.log`,
`/tmp/release-20261027-{starter,harness}-js.log`,
`/tmp/release-20261027-wheel-integration.log`,
`/tmp/release-20261027-public-integration.log`.
Temporary workspaces/logs are retained evidence, not required runtime state.

This release completes the public-delivery follow-up to
[the reliability audit](reliability-audit-2026-10-26.md); its previous local-only
publication boundary is historical, not the current released state.

## Follow-up: first Harness PyPI release

Baptiste authorized: « on peut le mettre sous le nom b4pt0r-the-harness (comme
pour le framework) ». The name returned HTTP 404 before publication. The existing
0.1.0 version was retained; commit `f95c9f3` and annotated tag `v0.1.0` were pushed.
Both distributions are now published as **`b4pt0r-the-harness==0.1.0`**. Imports
remain `the_harness`, and desktop services/protocol names are unchanged.

The wheel now includes prompts, icons and interface sources under
`the_harness/_project`, with shared resource-path resolution for source checkouts
and installed wheels. A `the-harness` control entry point is installed. The README
separates Python installation from the Linux desktop installer: Node/npm, Chromium,
OS libraries and user services are not installed or started by pip.

Release inputs were copied from tracked HEAD plus only the release changes into
`/tmp/harness-release-RqjUZE/source`. The unrelated maintenance edits remained
outside both artifacts and commits; the wheel's `environment.py` was compared
byte-for-byte with the original HEAD. Wheel (159 files) and sdist (229 files)
passed Twine and resource/private-path checks. The wheel was built from the sdist.
An initial resource check caught misplaced npm manifests; this was corrected and
both artifacts rebuilt before publication.

Verification of this exact clean candidate:

- Python suite: **457 passed, 2 skipped**, including four new packaging/path tests.
  This excludes eight uncommitted maintenance tests from the earlier 461-test
  local run, then adds the four new release tests.
- Installed-wheel CLI, distribution version, surface paths and tray icon: passed.
- `npm ci`, all **103 JavaScript tests**, and interface build from the installed
  wheel's own resource directory: passed. Existing chunk-size warning remains.
- Candidate-wheel plus public dependencies: **45 + 45 integration tests passed**.
- Wheel and sdist SHA-256 match the version-specific PyPI JSON response.
- Entirely public installation in `/tmp/hpi-5w2ex8za/venv`: **55 compatible
  distributions**, imports under site-packages, and **45 + 45 integration tests
  passed**, with starter bootstrap outside the checkouts. No Git or local wheels
  were used for this final gate.

The public verifier uses `uv --no-config pip install --no-cache --no-sources
--default-index https://pypi.org/simple` with explicit versions:
`b4pt0r-the-harness==0.1.0`, `b4pt0r-the-framework==0.3.0`, `modict==0.5.0`,
`pynteract==1.2.0` and `codex-backend-sdk==0.5.9`, plus test dependencies.
An inherited application `PYTHONPATH` was detected during the first wheel smoke;
that smoke and the clean source suite were rerun with PYTHONPATH/PYTHONHOME and
VIRTUAL_ENV removed. Only the isolated successful runs are counted above.

Artifacts, PyPI JSON, scripts and logs remain in `/tmp/harness-release-RqjUZE/`.
No active application server restart, desktop installation or surface publication
was performed; tests restarted only their own temporary workers. Live backend,
mobile delivery and a fresh full desktop installation are not claimed as tested.
