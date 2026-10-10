import argparse
import json
import os
import secrets
import socket
import sys
import threading
from pathlib import Path

import uvicorn

from the_framework.server.runtime.discovery import (
    PersistentSecretStore,
    ServerDescriptorStore,
    ServerLease,
)
from the_framework.server.runtime.supervisor import WorkerSupervisor

from .app import create_app
from .environment import load_runtime_environment
from .runtime_paths import server_paths

RESTART_EXIT_CODE = 75
GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 5


def exit_when_stream_closes(server, stream):
    stream.read()
    server.should_exit = True


def listening_socket(host="127.0.0.1", port=0):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session")
    parser.add_argument("--machine-root")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument(
        "--origin",
        action="append",
        default=["app://the-harness"],
    )
    parser.add_argument("--descriptor")
    parser.add_argument("--ui-root")
    parser.add_argument("--exit-on-parent-stdin-close", action="store_true")
    args = parser.parse_args()

    paths = server_paths(
        session=args.session, machine_root=args.machine_root, descriptor=args.descriptor,
    )
    session_path = paths.session_path
    # Workers inherit the same browser/pairing root, even with an explicit session.
    os.environ["THE_HARNESS_MACHINE_ROOT"] = str(paths.machine_root)
    load_runtime_environment(session_path)
    descriptor = paths.descriptor_path
    store = ServerDescriptorStore(descriptor)
    lease = ServerLease(descriptor.with_name("server.lock"))
    with lease:
        restart_requested = False
        server = None

        async def request_restart(intent):
            nonlocal restart_requested
            restart_requested = True
            server.should_exit = True

        token = secrets.token_urlsafe(32)
        browser_token = PersistentSecretStore(
            descriptor.with_name("ui-session.key")
        ).load_or_create()
        supervisor = WorkerSupervisor(
            session_path,
            application_reference="the_harness.application:application",
            plugin_state_path=session_path.parent / "plugins.json",
        )
        source_ui = Path(__file__).parents[1] / "desktop" / ".surface-build"
        ui_root = (
            args.ui_root
            or os.environ.get("THE_HARNESS_UI_ROOT")

        )
        if ui_root is None and source_ui.is_dir():
            ui_root = source_ui
        advertised_remote_endpoint = None
        app = create_app(
            supervisor,
            token=token,
            browser_token=browser_token,
            allowed_origins=set(args.origin),
            ui_root=ui_root,
            restart=request_restart,
            browser_runtime_root=paths.machine_root,
            client_remote_root=paths.machine_root,
            advertised_remote_endpoint=advertised_remote_endpoint,
        )
        server_socket = listening_socket(port=args.port)
        host, port = server_socket.getsockname()
        payload = store.write(store.payload(host=host, port=port, token=token))
        print(json.dumps({key: payload[key] for key in ("host", "port", "pid")}, separators=(",", ":")), flush=True)
        config = uvicorn.Config(
            app,
            log_level="info",
            access_log=False,
            timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
        )
        server = uvicorn.Server(config)
        if args.exit_on_parent_stdin_close:
            threading.Thread(
                target=exit_when_stream_closes,
                args=(server, sys.stdin.buffer),
                daemon=True,
                name="parent-stdin-monitor",
            ).start()
        try:
            server.run(sockets=[server_socket])
        finally:
            store.remove_if_owned(payload)
        if restart_requested:
            raise SystemExit(RESTART_EXIT_CODE)


if __name__ == "__main__":
    main()
