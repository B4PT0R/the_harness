# The Harness — local general-purpose assistant

The Harness is a local-first agent application for computer work: conversation,
research, programming, files, browser use, memory, voice and scheduled tasks.
It is an experimental personal application for power users, not a mass-market
product. Keep identity and personality configurable.

The default agent is Pandora: a warm, feminine, lightly witty collaborator who
remains precise and highly effective. This application default is shared by text
and voice and can be adapted through explicit user preferences.

Use the reusable `the_framework` package for agent and server primitives.
Application identity, prompts, plugins and UI remain owned by this repository.
Preserve one durable primary conversation, explicit plugin composition, process
supervision, authentication and atomic persistence. Keep tools cancellable and
long-running work outside the server event loop.

No remote exposure is enabled by the installer. Permissions follow user intent;
ask before destructive, external or consequential actions not already authorized.

Keep visual quality deliberate; inspect the rendered interface after UI changes.
Run `uv run pytest -q`, `npm test` and `npm run build` for relevant changes.
Create coherent local commits after verified batches; do not push without consent.

## Product intent and continuity

The user and agent should be able to reshape the application they are currently
using through conversation: UI changes, new plugins and backend adaptations.
For example, a weather request can lead to both a backend capability and a
well-placed widget. Aim for a short, fluid feedback loop from request to working
result, without requiring the user to leave the conversation.

The minimal contract is a simple, fluid chat with one durable primary
conversation and clear activity feedback: thinking, tool calls, results and
failures. Realtime voice is another way to participate in that conversation and
direct the application's evolution, reducing the need to read and type.

Make loss of conversational continuity very unlikely, including during application
changes and supervised server restarts. This is a strong engineering priority,
not an absolute guarantee against every failure. Keep interruption brief, preserve
session state and support reconnection and resumption.

Keep the conversational core small, reliable and recoverable. Prefer backend
extensions in plugins that can be enabled or disabled. A broken plugin should be
isolated or disabled with an understandable notice, leaving a path to conversation
and repair. Retain a known-good UI version and a practical rollback path when a
frontend update fails. These are design requirements; verify their implementation
rather than assuming that plugin composition alone provides failure isolation.

## Framework and application boundary

The Framework provides reusable agent/server primitives and application lifecycle
support, including plugin hosting and durable sessions. In normal end-user use,
it should be a dependable dependency that the agent rarely needs to modify.
The Harness, or another application derived from it, is the code the user and
agent routinely shape together. Application identity, prompts, UI and product
composition belong there.

During our development of these two projects, the current Framework architecture
is open to substantial revision. It is a working first iteration, not a fixed
endpoint: simplify or replace experimental mechanisms when concrete evidence
supports a clearer design. Update the Framework, starter and Harness together
when an API changes, remove obsolete forms and keep the current behavior working.
Disposable test data does not require migration or compatibility layers.
Test reusable changes in the Framework before adapting this application.

The working Framework/Harness pair is the reference for evaluating improvements.
The Harness is its canonical complete consumer and has grown beyond the minimal
Framework starter. The longer-term direction is for the Harness to become the
basis of the starter we offer. This does not authorize merging product code into
framework primitives: keep the starter usable without product imports.

## Current priority: a coherent, approachable Framework

Prioritize simplifying the Framework's composition vocabulary over incidental
feature work, such as optimizing browser visibility switching. Its plugin system
already supports complete vertical slices; first examine how those capabilities
are named, exposed and assembled before introducing new abstractions.

Reduce unnecessary verbosity, redundant layers, rarely useful options and
unfinished experimental scaffolding while retaining important functionality.
Compaction means less conceptual and maintenance burden, not merely fewer lines
or denser code. Control the proliferation of classes and primitives. Choose clear,
consistent names for classes, functions and parameters, with distinct
responsibilities and predictable composition rules. A newcomer, human or AI,
should not need the project's development history to understand the public API.

Make simple tasks simple, with sensible defaults and obvious parameters. Reveal
advanced capabilities progressively, when needed, rather than requiring users to
learn them before assembling a basic application. Keep extension points flexible
for uses we have not anticipated, without trying to model every hypothetical use.
Judge clarity across API names, defaults, examples, options and extension paths;
there is no single numerical simplicity target.

Do not grow framework abstractions merely to shorten this application's source.
Consume ordinary bundled plugins instead of rebuilding their server wiring.
Consider established tools and libraries when they can materially simplify our
implementation. Baptiste primarily works in Python and has a solid understanding
of React; proactively flag relevant existing solutions or better directions.
Verify their fit and explain benefits and dependency/operational costs. Recommend
adoption when it improves clarity, reliability or maintenance, not just because a
library exists.

## Browser and deployment model

Local-first describes where the app server and agent run, not an exclusively
local UI. A personal machine can remain on as a private server for mobile or
other remote clients, for example through explicitly configured Tailscale access.
Keep server ownership, durable conversation and connected clients conceptually
separate. Remote access is optional and is not enabled by the installer.

The app server should also be usable as a small private cloud server reachable
through a tailnet subnet. This is an architectural goal beyond remote access to
the agent: future plugins can host small cloud services for connected clients,
such as notifications, shared storage and other persistent client services.
Keep these services owned by the server and reusable across local, mobile and
other remote clients. They must be able to operate without a local desktop UI
or an active conversation; use the shared bucket for client-visible file storage.
This is a direction for future capabilities, not a claim that those services are
already implemented.

The bundled Chromium browser, controlled through Playwright and a tools plugin,
has three roles: display the local desktop UI, let the agent inspect and verify
that UI through screenshots and DOM snapshots, and provide web browsing whose
actions the user can see in a shared visible browser. Visual appearance and
functional behavior both matter in the agent's modification/inspection loop.

The agent may browse headlessly for its own work. When the user asks to see the
navigation, it must be possible to continue in a visible browser. A smooth direct
switch preserving state is welcome when practical, but exact transfer of the
headless session is not a requirement; opening a visible session and continuing
there is acceptable.

## Working approach

During this experimental phase, prefer one clear current contract shared by the
Framework, starter and Harness. Adapt all consumers together when paths, schemas
or APIs change, and remove the old forms. Current test files and sessions are
disposable: do not accumulate migration code or compatibility aliases unless
Baptiste explicitly asks to preserve existing data. When needed, use standalone,
one-shot scripts under `migrations/`, removable after execution; never embed
migration logic in application startup or runtime code. Keep normal conversation
continuity and restart/reconnect behavior working under the current contract.

Favor proportional safeguards for an experimental, user-controlled application.
Preserve authentication, persistence, recovery and user intent without adding
mass-market product machinery by default. Broad customization does not imply
permission for destructive or consequential actions unrelated to the request.

Use the running Harness to check that framework simplification preserves real
application behavior. Keep visual quality deliberate and inspect the rendered UI
after UI changes. Run the relevant checks listed above for code changes; a
prose-only instructions update does not require the application test suites.

The Framework supports independent concurrent sessions; the Harness retains one
default user conversation. Agent configuration, extension state and bindings live
in that canonical session, not in parallel application settings stores.

Events belong to the component that owns their behavior. The worker core declares
only events needed for its generic operation. Events used only within a plugin's
feature lifecycle must be declared and emitted by that plugin. Public consumers
receive typed Framework/plugin events; backend wire events remain inside their
respective adapters and must be explicitly converted or filtered.

The global `Application` owns this server and is built through `application.build`.
The ASGI adapter's state.application is that same object; ApplicationHost is removed.
Its lifespan reserves/releases Application.current(), including failure/cancellation.
Imports in workers remain inert. `context.application` supplies the owner while
constructing services; the live global lookup is available only during startup,
request handling and shutdown. A running application cannot rebuild itself.

HarnessSession(SessionRuntime) owns one conversation's services/routes and points
to that Application. Extra sessions do not clone Application. `state.session`
selects their explicit controller; no global mutable current-session pointer.
The class receives its scoped service registry from the framework, so its custom
constructor no longer needs a separately injected services mapping. The capability
channels remain agent.bridge/runtime.bridge; runtime.application is the actual app.
