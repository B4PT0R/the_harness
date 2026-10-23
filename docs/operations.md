# Operating The Harness

This guide covers the Ubuntu desktop installation. For first setup and an
overview of the application, start with the [README](../README.md).

## Open, inspect and restart

The launcher and tray open the interface. From the repository directory, the
control client provides the same entry point and reports the running services:

```sh
.venv/bin/python -m the_harness.control open
.venv/bin/python -m the_harness.control status
```

Closing the interface leaves the services running. To stop the application or
restart its backend explicitly:

```sh
.venv/bin/python -m the_harness.control stop
.venv/bin/python -m the_harness.control start
.venv/bin/python -m the_harness.control restart
```

A backend restart retains the persistent conversation, but can interrupt active
work. Check the status before restarting during an agent task or voice call.

The installation consists of four systemd user units: `the-harness.service`
owns the server and workers, `the-harness-browser.service` owns the browser,
`the-harness-ui.service` prepares the interface, and `the-harness-tray.service`
provides the tray. The UI unit is a oneshot build service, so an `active (exited)`
state is normal. The server waits for the UI build job before adopting the initial
artifact; an existing published release remains authoritative. A failed build does
not prevent a headless server or an existing release from starting. The control
client waits for healthy backend status and briefly retries interface opening while
the browser becomes available. A backend restart does not restart the browser.
Graceful shutdown removes the private discovery descriptor.

After an unexpected shutdown, start the launcher normally. The server and asset
builder can recover before a graphical session exists; the browser and tray belong
to the graphical session instead. The launcher explicitly starts a stopped browser
without replacing a running one. Systemd first signals the owning server/browser
process during normal shutdown, allowing it to close its children; it kills any
remaining processes only after the shutdown deadline (45 seconds for the browser).

Chromium startup is bounded to 20 seconds, followed by resource cleanup on failure;
a failed launch can be retried without deleting the profile. Chromium itself handles
stale profile locks. Do not routinely remove `Singleton*` files or rewrite profile
preferences to claim a clean exit: an active profile may belong to another process.
If opening the UI hangs again, capture the browser service logs and process stacks
before restarting it. A SIGKILL test covers loss of both isolated service trees,
recovery of the canonical conversation, stale discovery/socket files, authentication
and a draft actually written to the browser's local storage. This tests process-loss
recovery, not physical storage failure or loss of writes that were never committed.

For startup diagnostics:

```sh
systemctl --user status the-harness.service
journalctl --user -u the-harness.service -n 100
```

## Data and configuration

The default data directory is `~/TheHarness`. It contains the conversation and
archive, agent configuration, extension state and plugin bindings together in
`session.json`, plus the memory database, auxiliary sessions and other feature
storage. There are no separate agent `config.json`, `state.json` or `plugins.json`
stores in this directory. Bootstrap configuration, local
access secrets and the browser profile live under `~/.the_harness_assistant`.
Backend authentication is managed separately by `codex-backend-sdk`; see its
[authentication documentation](../../codex-backend-sdk/README.md#authentication-and-lifecycle).

`THE_HARNESS_MACHINE_ROOT` selects the machine-local instance root; the server,
browser and control commands also accept `--machine-root`. A custom machine root
defaults its data directory to `<machine-root>/data`. Its bootstrap configuration
can select another data directory without moving secrets, browser state or runtime
discovery. Services load `.env` from the selected machine root. An explicit server
`--session` uses its parent as an isolated machine root unless `--machine-root`
overrides it. The installed systemd units belong to the default instance;
custom instances need their own units and cannot control the installed ones.

Use Settings for the model, personal instructions and optional tool bindings.
Personal instructions apply to both text and voice. A loaded plugin's service
can remain available when its tools are disabled for the agent.

To inspect the configured data directory:

```sh
.venv/bin/python -m the_harness.control data-root
```

`data-root PATH` changes the configured directory and requires a backend restart.
It does not move existing data. Back up the data and bootstrap directories before
performing a manual migration. An instance does not import another instance's
conversation, memory or files automatically.

## Reset session, memory or registry

Settings contains a **Danger zone** with a confirmation for each action:

| Action | Erases | Preserves |
| --- | --- | --- |
| Reset session | Primary conversation, archive and auxiliary sessions | Durable memory, registry, files, configuration and scheduled tasks |
| Reset memory | Durable memory database and its curator session | Primary conversation, archive, registry, files, configuration and scheduled tasks |
| Reset registry | Persistent registry | Primary conversation, archive, durable memory, files, configuration and scheduled tasks |

These actions interrupt ongoing agent and voice activity. Resetting memory or registry leaves
the current conversation available to the agent; it does not erase information
from that conversation. File attachments are not removed by these resets.

For integrations, the authenticated endpoints are `DELETE /api/v1/session`,
`DELETE /api/v1/memory` and `DELETE /api/v1/registry`. The application selects their scope; the framework
coordinates service suspension, worker restart and restoration if startup fails.

## Update the running application

The server serves a published interface release. `npm run build` prepares an
artifact but does not by itself replace an already published release. Use the
framework's candidate build, preview, publish and rollback workflow described
under [versioned client surfaces](../../the_framework/docs/framework.md#versioned-client-surfaces).
Backend source changes require a supervised restart.

After a major system Python upgrade, recreate the virtual environment for the
new interpreter before restarting:

```sh
uv sync --python /usr/bin/python3 --extra dev
```

## Remove the desktop installation

```sh
./scripts/uninstall-services.sh
```

Uninstallation removes the services and launcher while retaining user data.
Deleting the data directories is a separate destructive operation.
