"""Small descriptor-driven client used by launchers and the tray process."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import httpx

from the_framework.server.runtime.discovery import ServerDescriptorStore

from the_framework.server.clients.browser_rpc import BrowserRPCClient, browser_socket_path
from .client_mode import ClientModeStore
from .runtime_paths import (
    bootstrap_root,
    configure_data_root,
    ensure_data_root_config,
    resolve_data_root,
)

DEFAULT_SERVICE = "the-harness.service"
DEFAULT_TRAY_SERVICE = "the-harness-tray.service"
DEFAULT_UI_SERVICE = "the-harness-ui.service"
DEFAULT_BROWSER_SERVICE = "the-harness-browser.service"


class HarnessControl:
    def __init__(
        self,
        runtime_root=None,
        *,
        service=DEFAULT_SERVICE,
        tray_service=DEFAULT_TRAY_SERVICE,
        ui_service=DEFAULT_UI_SERVICE,
        browser_service=DEFAULT_BROWSER_SERVICE,
        command_runner=subprocess.run,
        client_factory=httpx.Client,
    ):
        self.explicit_runtime_root = runtime_root
        self.machine_root = (
            Path(runtime_root).expanduser().resolve()
            if runtime_root is not None
            else bootstrap_root()
        )
        self.client_modes = ClientModeStore(self.machine_root / "client.json")
        self.runtime_root = None
        self.descriptor = ServerDescriptorStore(
            self.machine_root / "runtime" / "server.json"
        )
        self.service = service
        self.tray_service = tray_service
        self.ui_service = ui_service
        self.browser_service = browser_service
        self.command_runner = command_runner
        self.client_factory = client_factory

    def systemctl(self, action, *units, check=True):
        return self.command_runner(
            ["systemctl", "--user", action, *(units or (self.service,))],
            check=check,
            text=True,
            capture_output=True,
        )

    def request(self, method, path, *, json_payload=None, timeout=10):
        descriptor = self.descriptor.read()
        url = f"http://{descriptor['host']}:{descriptor['port']}{path}"
        with self.client_factory(
            headers={"Authorization": f"Bearer {descriptor['token']}"},
            timeout=timeout,
        ) as client:
            response = client.request(method, url, json=json_payload)
            response.raise_for_status()
            return response.json() if response.content else None

    def wait_until_ready(self, timeout=20):
        deadline = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < deadline:
            try:
                return self.request("GET", "/api/v1/health", timeout=2)
            except (FileNotFoundError, ValueError, json.JSONDecodeError, httpx.HTTPError) as error:
                last_error = error
                time.sleep(0.1)
        raise RuntimeError("The Harness server did not become ready") from last_error

    def start(self):
        if self.client_modes.load()["mode"] == "remote":
            self.systemctl("start", self.browser_service)
            return {"status": "ready", "mode": "remote"}
        # The tray requires the server, so this single operation restores the
        # complete user-facing runtime from either the launcher or the tray.
        self.systemctl("start", self.tray_service)
        return self.wait_until_ready()

    def open(self):
        client = self.client_modes.load()
        self.start()
        if client["mode"] == "remote":
            url = f"{client['endpoint']}/remote-ui/"
            browser = BrowserRPCClient(browser_socket_path(self.machine_root))
            browser.call("open_application_ui", url)
            return {"status": "opened", "mode": "remote", "url": url}
        return self.request("POST", "/api/v1/ui/open")

    def restart(self):
        if self.client_modes.load()["mode"] == "remote":
            self.systemctl("restart", self.browser_service)
            return self.open()
        # Keep the Chromium-owned Harness UI alive while the backend rolls.
        # Its HTTP and WebSocket transports reconnect to the fixed loopback
        # endpoint once the server is ready. Restarting the browser here would
        # destroy the visible window and all ephemeral frontend state; opening
        # the UI again would also force an unnecessary navigation.
        self.systemctl("restart", self.service)
        return self.wait_until_ready()

    def stop(self):
        return self.systemctl(
            "stop",
            self.tray_service,
            self.ui_service,
            self.browser_service,
            self.service,
            check=False,
        )

    def status(self):
        client = self.client_modes.load()
        if client["mode"] == "remote":
            return {"status": "configured", **client}
        try:
            return self.request("GET", "/api/v1/health", timeout=2)
        except (FileNotFoundError, ValueError, json.JSONDecodeError, httpx.HTTPError):
            return {"status": "stopped"}

    def data_root(self):
        if self.client_modes.load()["mode"] == "remote":
            return {"data_root": None, "mode": "remote"}
        return {"data_root": str(resolve_data_root(self.explicit_runtime_root))}

    def mode(self, value=None, endpoint=None):
        if value is None:
            return self.client_modes.load()
        return self.client_modes.save(value, endpoint)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=["open", "start", "stop", "restart", "status", "data-root", "mode"],
        nargs="?",
        default="open",
    )
    parser.add_argument("path", nargs="?")
    parser.add_argument("--runtime-root")
    parser.add_argument("--endpoint")
    args = parser.parse_args()
    if args.action == "data-root":
        root = configure_data_root(args.path) if args.path else ensure_data_root_config()
        result = {"data_root": str(root), "restart_required": bool(args.path)}
    elif args.action == "mode":
        if args.path not in {None, "local", "remote"}:
            parser.error("mode accepts local or remote")
        result = HarnessControl(args.runtime_root).mode(args.path, args.endpoint)
    else:
        if args.path is not None:
            parser.error("path is only accepted by data-root")
        result = getattr(HarnessControl(args.runtime_root), args.action)()
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
