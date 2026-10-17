# The Harness

The Harness is a local assistant application for working on your computer with
an AI agent. You can ask it to investigate a problem, work on a codebase, research
a topic, handle files or follow up on a scheduled task. It combines conversation,
tools, durable memory and optional voice in one desktop interface.

The default agent is **Pandora**: a warm, feminine, lightly witty collaborator
who takes the work seriously. Her personality and working instructions are
application defaults that you can adapt in Settings.

## A conversation that continues

The Harness keeps one persistent primary conversation. Text and voice participate
in that same conversation; closing the interface or restarting a worker does not
start a new one. Compaction keeps the active context manageable while retaining
an archive of the conversation. Durable memory is a separate store for information
the agent should retain across its work.

The installed capabilities include a terminal, browser, web search, file
attachments, memory, a structured registry and scheduled tasks. Settings controls
which optional tools are exposed to the agent. The application runs locally;
model inference uses the backend account you authenticate below.

Images, files and application widgets can appear as explicit conversation
artifacts. Tool and command artifacts return with the saved history; provider
artifacts are temporary views for the current turn. Vision inputs alone do not
request display. Custom UIs can supply `artifactRenderers` to `AssistantApp` for
additional kinds; unsupported or failing widgets retain a readable fallback.
All uploaded and published client files share `~/TheHarness/bucket/` (or
`data_root/bucket/` when configured). Images, videos, audio and other files use
this same tree and authenticated `/api/v1/bucket/...` URLs, including for authorized
remote desktop clients. The session stores references and metadata only.

## Start using it

The current installation targets Ubuntu with a systemd user session. You need
Python 3.12 or newer at `/usr/bin/python3`, `uv`, Node.js/npm, and the GTK tray
packages `python3-gi` and `gir1.2-ayatanaappindicator3-0.1`.

This development checkout uses editable sibling dependencies. Before installing,
arrange the repositories as follows, under a path without spaces:

```text
dev/
├── the_harness/
├── the_framework/
└── codex-backend-sdk/
```

From the `the_harness` directory, prepare the Python environment and authenticate
the model backend. The SDK reuses existing usable Codex credentials or opens a
browser login:

```sh
uv sync --locked --extra dev --python /usr/bin/python3
.venv/bin/python -c 'from codex_backend_sdk import OpenAI; OpenAI().authenticate()'
```

Then install the desktop application and open it:

```sh
./scripts/install-services.sh
.venv/bin/python -m the_harness.control open
```

The installer builds the interface, downloads its Chromium runtime, installs the
launcher and tray integration, and enables the user services. The server listens
on `127.0.0.1:48887`; installation does not expose it to the network.

Start with an ordinary request such as “Explore this repository and explain how
it is assembled.” In Settings, select a model available to your account, add any
personal instructions and adjust the optional capabilities. The initial model
is `gpt-5.5`. The interface supports French and English; text and voice share the
agent's personal instructions.

For data locations, service diagnostics, resets and removal, see the
[operations guide](docs/operations.md).

## How it fits with The Framework

[The Framework](../the_framework/README.md) supplies the reusable foundation:
declarative agent and plugin assembly, durable sessions, supervised workers,
authenticated transports and versioned client interfaces. **The Harness is its
canonical complete application**, showing how those pieces support a working
local assistant.

The Harness owns the choices that make this application: Pandora's defaults,
installed capabilities, interface, security policy and desktop integration.
These can evolve, including through work performed by the agent itself, while
preserving the conversation and user data. The Framework provides controlled
build, preview, publication, rollback and restart mechanisms for that evolution.

When a generally useful mechanism is missing, improve the framework rather than
duplicate it in the application. Keep the framework lean and general; product
choices belong here. The [framework composition guide](../the_framework/docs/framework.md)
explains its contracts and APIs.

Local and paired-client prompts share the Framework's `conversation.ingress`
capability and the installed chat service's text/voice barrier. Remote pairing,
permissions, wire projections and persistent command receipts remain separate
application responsibilities. This checkout requires the sibling Framework's
unreleased ingress capability, not just the published 0.2.1 package.

## Find your way through the code

For a first technical read, start with the application declaration, then follow
the agent definition and the server assembly. The main entry points are:

| Where | What you will find |
| --- | --- |
| [Application declaration](the_harness/application.py) | The primary agent, installed plugins and client surface |
| [Agent definition](the_harness/agent_definition.py) and [prompts](the_harness/prompts/) | Pandora's defaults, instructions and session policy |
| [Server assembly](the_harness/app.py) and [runtime composition](the_harness/runtime_composition.py) | How framework services, transport security and application controls fit together |
| [Application plugins](the_harness/plugins/) | Application-specific integrations and policies alongside bundled framework capabilities |
| [Shared interface](ui/README.md) | Reusable React components, client state, theme variables and the multilingual copy bank |
| [Desktop host](desktop/) and [installation scripts](scripts/) | The thin UI entry point and Ubuntu integration |
| [Operations guide](docs/operations.md) | Persistent data, configuration, service management and destructive actions |
| [Backlog](TODO.md) | Known gaps and candidates for later refactoring |

The shared interface is intended for reuse by future mobile and Quest hosts.
Those native applications are not currently bundled.

## Work on the application

Read [AGENTS.md](AGENTS.md) before changing the code. It records the ownership,
persistence and verification rules for humans and agents. In particular, clients
own their interface and media execution, the server owns connections and worker
supervision, and workers own inference and session history.

With the Python environment prepared above, install the frontend dependencies
and run the relevant checks:

```sh
npm ci
uv run pytest -q
npm test
npm run build
```

For UI changes, inspect the rendered result as well as the tests, and use the
candidate build/preview/publication workflow to update the running interface.
For shared framework changes, verify the framework independently before relying
on them here. The [UI guide](ui/README.md) and
[framework composition guide](../the_framework/docs/framework.md) are the next
references once you have found the part you want to change.
