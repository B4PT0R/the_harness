# The Harness

The Harness is a local assistant application for working on your computer with
an AI agent. You can ask it to investigate a problem, work on a codebase, research
a topic, handle files or follow up on a scheduled task. It combines conversation,
tools, durable memory and optional voice in one desktop interface.

The default agent is **Pandora**: a warm, feminine, lightly witty collaborator
who takes the work seriously. Her personality and working instructions are
application defaults that you can adapt in Settings.

## A conversation that continues

The Harness keeps one persistent default conversation. Text and voice participate
in that same conversation; closing the interface or restarting a worker does not
start a new one. Compaction keeps the active context manageable while retaining
an archive of the conversation. Durable memory is a separate store for information
the agent should retain across its work.

An active voice conversation resumes automatically after a supervised server
restart or an interface publication. The old call finishes its spoken turn and
persists its final transcript before replacement; the same browser tab then
reconnects in voice mode. Stopping voice explicitly cancels automatic recovery.

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
Attachment requests accept at most 32 files and 64 MiB of combined contents.
The Framework also stops multipart reception above 65 MiB, including fields and
framing, even without a trustworthy Content-Length. Oversized uploads are rejected
without replacing existing files; partial copies and upload spools are cleaned up.

The optional `images` plugin exposes the backend-hosted `image_generation` tool
for creation and editing, plus `images.inspect_image` for local-file or HTTP(S)
vision/reference inputs. Remote images are downloaded and validated before context
injection; the backend receives base64 from a frozen local file, never the remote
URL. Completed results are validated and frozen under the session's `images/`
directory, then published once as durable image artifacts. Inspection alone does
not display an image. Generation-output handling and presentation belong to this
application plugin; the Framework supplies generic lifecycle hooks and reusable
image preparation.

The `documents` plugin adds local Docling conversion, OCR, paginated reading and
search for PDFs, Office files and scans. It uses an isolated CPU runtime and
private session caches; see [setup, privacy and limits](docs/documents.md).

The optional `tts` plugin uses local CPU Piper synthesis with an isolated runtime
and a French voice. It produces WAV files and durable `audio` artifacts with manual
playback controls and a download link; see [setup and configuration](docs/tts.md).

## Embedded Python

The optional `pynteract` plugin runs persistent Python cells in a separate local
process with the account's real permissions, not a sandbox. It supports native
objects, worker-tool RPC and cancellable jobs. It requires Pynteract 1.2 or later
(the current development lock uses the sibling checkout).

Per cell, stdout/stderr capture each keep a 256 Ki-character prefix plus an overflow
marker. Live job notifications share a 256 KiB wire budget plus small notices;
subsequent output is discarded, not queued indefinitely. Final text has a further
4,000-token head/tail presentation limit. `output_truncated` signals capture/live
loss; `output_chars` counts received text while running and generated characters
when a cell returns normally (including a captured Python exception). Interrupted
jobs retain their received counts. Use files for complete logs. These limits do
not bound user-created objects, custom threads, native memory or disk usage.

## Account quota and resets

The shared desktop and mobile composer’s weekly quota gauge opens the available reset credits and their
expiry dates. Manual redemption requires confirmation. Conversation settings
persist the exhausted-quota policy: hold new turns (default), or redeem the
available reset with the earliest expiry. A turn already running is not cut off.
Held prompts survive worker restarts and autonomous work rechecks its owner’s
admission before resuming.

An independent server loop also redeems credits expiring in strictly less than
one hour, even with no UI open. Decisions and results are journalled in
`data_root/quota.json` before account mutation. An uncertain result is never
blindly retried and blocks further redemption until reconciled. The interface
shows operation receipts; unknown or unavailable quota is explicitly labelled.
Initial backend unavailability permits conversation for local repair, while a
previously observed exhausted quota stays blocked until recovery is observed.

## A private cloud for your clients

An architectural goal is for the app server to double as a small private cloud
server, reachable by your devices through a tailnet subnet. Beyond interacting
with the agent remotely, future plugins can provide small cloud services such
as notifications, shared storage and other persistent services for mobile and
other clients. These services should run independently of the local desktop UI
and an active conversation, with client-visible files using the shared bucket.
This describes the project's direction; individual services remain to be built.

The same server may serve different client surfaces for desktop, mobile, Quest
or other devices. The agent can maintain each surface's source, build, routes,
preview and publication independently, while clients share the server and durable
conversation. Device-specific native clients remain future work.

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

The server and UI build start independently of the desktop session. The browser
and tray start with the graphical session; opening the launcher also starts the
browser if it is stopped. During normal shutdown, systemd lets each owner close
its children before forcibly cleaning up a stuck service. After an unexpected
shutdown, the existing session and browser profile are reused; do not delete
Chromium's profile or its locks as a routine recovery step.

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

Local and paired-client prompts share the host-owned chat service and its
text/voice barrier, assembled by `build()` rather than a plugin.
The remote plugin declares its service and API factories directly; `server.py`
constructs each component from its injected services and BuildContext. `policy.py`
owns product permissions and wire projections. The Framework transport owns
credentials, leases, event delivery and persistent command receipts. The product
API chooses the routes and command semantics, reusing the host's text/voice ingress.
The worker's `Context` prepares model input and performs compaction through
`agent.compact()`. The Session retains canonical data and its atomic history/archive
updates; UI and voice keep their own projections. Ephemeral providers are added to
generation only and are never compacted into the canonical history.

Private specialists, including Jiminy, are resolved after plugin loading from their
current declarations. The worker emits one catalogue for its fleet, including
inactive bindings; AgentSpec does not carry compiled profiles. Launch settings
override initial resource defaults, while saved Session settings remain authoritative.

The bundled `agentic` plugin owns persistent goals and immediate turn controls
(`wait`, `end_turn`). One authorized goal remains open until verified completion
or explicit human cancellation; the agent may suspend it with progress preserved.
Low-priority continuations use the canonical worker, survive server restarts and
stop when suspended or disabled. This does not expand tool permissions. Timed
reminders and persistent response deadlines remain owned by `scheduler`.
Clearing conversation history preserves goals, just like scheduled obligations;
only an explicit complete application reset clears their stored records.

Plugins represent application features. Changing an agent binding during voice
recreates the call from the current canonical conversation, while installed
services and data remain available. The owning client reconnects automatically;
a manual stop wins, and disabling voice never reopens it. Installing or removing
an entire plugin remains a separate change to startup composition.

This checkout requires the sibling Framework's unreleased conversation assembly,
not just the published 0.2.1 package.

## Find your way through the code

For a first technical read, start with the application declaration, then follow
the agent definition and the server assembly. The main entry points are:

| Where | What you will find |
| --- | --- |
| [Application declaration](the_harness/application.py) | The agent catalogue, installed plugins and client surface |
| [Agent definition](the_harness/agent_definition.py) and [prompts](the_harness/prompts/) | Pandora's defaults, instructions and session policy |
| [Server assembly](the_harness/app.py) and [runtime composition](the_harness/runtime_composition.py) | How framework services, transport security and application controls fit together |
| [Application plugins](the_harness/plugins/) | Application-specific integrations and policies alongside bundled framework capabilities |
| [Shared interface](ui/README.md) | Reusable React components, client state, theme variables and the multilingual copy bank |
| [Desktop host](desktop/) and [installation scripts](scripts/) | The thin UI entry point and Ubuntu integration |
| [Operations guide](docs/operations.md) | Persistent data, configuration, service management and destructive actions |
| [Backlog](TODO.md) | Known gaps and candidates for later refactoring |

The shared interface is intended for reuse by future mobile and Quest hosts.
Those native applications are not currently bundled.

The HTTP entry point uses the Framework's shared `LocalServer` lifecycle.
systemd owns server replacement on the configured loopback port, while the
browser daemon independently owns Chromium and its open pages. Restarting the
server preserves the browser cookie and canonical conversation; process-control
tokens rotate. Custom supervisors must reuse the same port across replacements.

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

Python and UI suites distinguish durable contracts in `tests/general/` from
revisable implementation feedback in `tests/agentic/`. The default commands run
both layers. See [test discipline](tests/README.md) for classification and cleanup.

For UI changes, inspect the rendered result as well as the tests, and use the
candidate build/preview/publication workflow to update the running interface.
Deployment controls belong to the agent's `system` plugin, rather than the base
settings interface. The agent inspects the authenticated preview through its
browser tools before publishing; the previous release remains available for rollback.
`system.preview_surface(name="main")` opens a private preview in a separate web
tab without replacing the single principal desktop. It works for other named
surfaces too. Previews show the conversation and allow local drafts/navigation,
but cannot send prompts, start voice, persist settings or claim the desktop
application bridge. Authentication is handled automatically by a one-use link;
preview access survives server restart.
For shared framework changes, verify the framework independently before relying
on them here. The [UI guide](ui/README.md) and
[framework composition guide](../the_framework/docs/framework.md) are the next
references once you have found the part you want to change.

The Framework can host several independent concurrent agent sessions. The Harness
keeps one default user conversation as its product policy. Its canonical session
owns history, configuration, extension state and plugin bindings; process-local
resources supply defaults. Sub-agent activity is shown separately in the chat and
results return to the caller without merging specialist histories.

Chat history uses the Framework's standard `display` projection (user/assistant
messages and artifacts); the `activity` view used by remote clients also includes
function calls. These views need no application wiring. `HarnessSession.reset_session()` owns the selective
conversation reset, using the shared reset lifecycle and voice coordination.

Chat, sub-agent activity and voice captions consume Framework/plugin events.
Spoken answers are labelled **Voice agent**; delegated backend answers appear in
collapsed **Text agent** disclosures, including after reconnect and history replay.
The distinction follows canonical message provenance rather than the current
client's voice toggle.
Developer markers record voice-call starts and ends in the canonical session,
keeping both agents informed of mode changes without adding visible chat bubbles.
Backend wire signals remain inside their adapters; plugins own events specific
to their feature lifecycle. Session items remain the canonical replay source.

Plugins declare their server components in `server_extensions`; `configure(context)`
collects advanced build-time contributions before any service is constructed.
The service factories receive fixed build inputs and named dependencies separately.

The application declares its agent recipes through `agents`. Its default session
owns the active conversation worker and session services; the application owns
only shared services and client surfaces. Session-bound remote transports and
notification delivery close with that session. The HTTP access boundary remains
application-owned, including while a conversation is closed.

Agent recipes do not choose session lifetime. The host creates the durable default
conversation; framework sessions own their storage path and history retention.
The same recipe may therefore serve persistent conversations or temporary tasks.

History retention is saved in the canonical session. Reopening it restores that
behavior; changing a worker or specialist's defaults does not silently change an
existing conversation. The server's storage path stays outside session JSON.

Agent recipes describe construction only. Specialist queue, idle shutdown and
completion/retry requirements belong to their AgentTrigger. Resource factories
receive the session workspace directory, independently of history persistence.
