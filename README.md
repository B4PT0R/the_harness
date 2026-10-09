# The Harness

A local general-purpose agent for conversation, research, development and work
on your computer. The default agent is Pandora: warm, feminine, lightly witty
and focused on effective work, with user-configurable preferences. Python owns
the durable conversation and tools; a React
interface provides chat, file attachments, plugin settings and optional voice.
The shared UI uses anthracite surfaces and an electric-blue accent, with safe Markdown,
code and math rendering. Personal instructions can be edited in Settings and
are shared by the text and voice agent. The initial model is `gpt-5.5`; choose
another model in Settings if your backend account exposes a different catalogue.

## Retained capabilities

- Persistent conversation, supervised worker, compaction and recovery.
- Bash, browser, web search, memory, registry, scheduler and system controls.
- File attachments, realtime voice, desktop notifications and explicit client pairing APIs.
- Authenticated loopback HTTP/WebSocket interface and editable client surface.

## Install on Ubuntu

Requires `uv`, Node.js/npm, and the GTK tray dependencies (`python3-gi` and
`gir1.2-ayatanaappindicator3-0.1`). Run:

```sh
./scripts/install-services.sh
```

The installer uses `/usr/bin/python3`, builds the interface, installs Playwright
Chromium, and enables the four user services. It does not publish the server
through Tailscale. The server binds only to `127.0.0.1:48887`.

Data defaults to `~/TheHarness`; bootstrap, browser profile and local
secrets live under `~/.the_harness_assistant`. The previous companion's data in
`~/TheSuccubus` and `~/.the_harness` are intentionally separate and never imported.
The current instance was created empty in `~/TheHarness`. The provisional
`~/TheHarnessAssistant` directory was subsequently removed, without importing
its conversation, memory, attachments or configuration.
Configure backend authentication through the supported `codex-backend-sdk`
authentication flow. No former application credentials are copied.

```sh
.venv/bin/python -m the_harness.control open
.venv/bin/python -m the_harness.control status
./scripts/uninstall-services.sh
```

Uninstallation removes services and the launcher while retaining user data.
After a system Python major upgrade, recreate the venv with `uv sync --python
/usr/bin/python3 --extra dev`; do not reuse a venv built for a different Python.

## Canonical framework application

`ui/` contains the reusable `@the-harness/ui` workspace: visual components,
client state, CSS theme tokens and the French/English copy bank. `desktop/` is a
thin host entry point and build. See `ui/README.md` for composition and theming.

`application.py` declares capabilities. `agent_definition.py` and `prompts/`
provide identity and working policy. `assistant_runtime.py` supplies local
persistence; the frontend and desktop installation remain application-owned.
`CHAT` and `REALTIME` are bundled framework plugins; memory and registry
contribute live voice context without a product-specific controller.

Application-specific desktop lifecycle and security remain here. Framework
changes should solve a reusable composition problem and be verified by the
small independent starter as well as this application. The local framework
checkout contains the current joint-development changes; they are not published.

## Development

`scripts/build-icons.py` generates the shared vector mark and raster variants:
the desktop launcher uses `assets/assistant.png`, the tray uses its transparent
small-format variant, and the web UI uses the same SVG. The 512 px asset is also
available for future mobile/Quest packaging; native clients are not bundled here.

The framework and SDK use the existing editable sibling checkouts declared in
`pyproject.toml`. `uv sync --extra dev` installs the development dependencies.

```sh
uv run pytest -q
npm test
npm run build
```

This repository is an independent neutral snapshot. The original source and Git
history are archived at `~/dev/the_succubus`; this repository has no Git remote.
