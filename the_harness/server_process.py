"""Application composition for the shared local-server lifecycle."""

import argparse
import asyncio
import json
import os
import sys

from the_framework.server.runtime.local import LocalServer

from .app import create_app
from .environment import load_runtime_environment
from .runtime_paths import server_paths


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
    load_runtime_environment(session_path.parent)
    descriptor = paths.descriptor_path
    with LocalServer(descriptor, port=args.port) as process:
        app = create_app(
            session_path=session_path,
            token=process.token,
            origin=process.origin,
            browser_token=process.browser_token,
            allowed_origins=set(args.origin),
            ui_root=args.ui_root or os.environ.get("THE_HARNESS_UI_ROOT"),
            restart=process.request_restart,
            browser_runtime_root=paths.machine_root,
            client_remote_root=paths.machine_root,
        )
        print(json.dumps({key: process.descriptor[key] for key in ("host", "port", "pid")}, separators=(",", ":")), flush=True)
        raise SystemExit(asyncio.run(process.serve(
            app, parent_stream=sys.stdin.buffer if args.exit_on_parent_stdin_close else None,
        )))


if __name__ == "__main__":
    main()
