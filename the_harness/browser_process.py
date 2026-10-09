"""Independent long-lived owner of the Playwright Chromium contexts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
from pathlib import Path

from the_framework.server.clients.browser import DEFAULT_VIEWPORT, BrowserService
from the_framework.server.clients.browser_rpc import BrowserRPCServer, browser_socket_path
from .client_mode import ClientModeStore
from .configuration import AgentConfigStore
from .environment import load_runtime_environment
from .runtime_paths import bootstrap_root, ensure_data_root_config, resolve_data_root


def ensure_graphical_environment(
    environ=None, *, x11_socket_root=Path("/tmp/.X11-unix"), runtime_root=None
):
    """Recover the graphical session variables omitted by some user managers."""
    environ = os.environ if environ is None else environ
    if not environ.get("DISPLAY") and x11_socket_root.is_dir():
        displays = sorted(
            path.name[1:]
            for path in x11_socket_root.iterdir()
            if path.name.startswith("X") and path.name[1:].isdigit()
        )
        if displays:
            environ["DISPLAY"] = f":{displays[0]}"

    if not environ.get("XAUTHORITY"):
        runtime = Path(
            runtime_root
            or environ.get("XDG_RUNTIME_DIR")
            or f"/run/user/{os.getuid()}"
        )
        authority = runtime / "gdm" / "Xauthority"
        if authority.is_file():
            environ["XAUTHORITY"] = str(authority)
    return environ


def browser_config(runtime_root):
    config = AgentConfigStore(Path(runtime_root) / "config.json").load()
    value = config.get("chromium", {})
    return value if isinstance(value, dict) else {}


async def run(runtime_root):
    ensure_graphical_environment()
    machine_root = (
        Path(runtime_root).expanduser().resolve()
        if runtime_root is not None
        else bootstrap_root()
    )
    client = ClientModeStore(machine_root / "client.json").load()
    if client["mode"] == "local":
        data_root = resolve_data_root(runtime_root)
        load_runtime_environment(data_root / "session.json")
        config = browser_config(data_root)
    else:
        config = {}
    service = BrowserService(
        machine_root,
        web_headless=bool(config.get("web_headless", False)),
        ui_headless=bool(config.get("ui_headless", False)),
        ui_app_mode=bool(config.get("ui_app_mode", True)),
        viewport={
            "width": int(config.get("viewport_width", DEFAULT_VIEWPORT["width"])),
            "height": int(config.get("viewport_height", DEFAULT_VIEWPORT["height"])),
        },
        application_ui_origins=(client.get("endpoint"),) if client.get("endpoint") else (),
    )
    rpc = await BrowserRPCServer(browser_socket_path(machine_root), service).start()
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stopped.set)
        except NotImplementedError:
            pass
    print(json.dumps({
        "status": "ready",
        "socket": str(rpc.socket_path),
    }, separators=(",", ":")), flush=True)
    try:
        await stopped.wait()
    finally:
        await rpc.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root")
    args = parser.parse_args()
    if args.runtime_root is None:
        client = ClientModeStore().load()
        if client["mode"] == "local":
            ensure_data_root_config()
    asyncio.run(run(args.runtime_root))


if __name__ == "__main__":
    main()
