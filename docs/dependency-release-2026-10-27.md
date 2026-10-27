# Dependency release — 2026-10-27

Authorized by Baptiste: « mettre à jour les dependances pousser et publier ».
No application server restart, client-surface publication or OS change was performed.

## Released state

| Project | Version / commit | Delivery |
| --- | --- | --- |
| Modict | 0.5.0 / `176d5e7` | PyPI wheel + sdist; main + annotated `v0.5.0` pushed |
| Pynteract | 1.2.0 / `7ddfa67` | PyPI wheel + sdist; main + annotated `v1.2.0` pushed |
| Framework | 0.3.0 / `44427c9` | PyPI `b4pt0r-the-framework`, wheel + sdist; main + annotated `v0.3.0` pushed |
| Harness | 0.1.0 / `5f70561` | Main pushed; dependency alignment and installation documentation |
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
package rename was attempted. This application's delivery remains Git.

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
