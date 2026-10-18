"""Small descriptor-driven client used by launchers and the tray process."""

from __future__ import annotations

import argparse
import json
import subprocess
import time

import httpx

from the_framework.server.runtime.discovery import ServerDescriptorStore

from .client_mode import ClientModeStore
from .runtime_paths import (
    DEFAULT_BOOTSTRAP_ROOT,
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
        machine_root=None,
        *,
        service=DEFAULT_SERVICE,
        tray_service=DEFAULT_TRAY_SERVICE,
        ui_service=DEFAULT_UI_SERVICE,
        browser_service=DEFAULT_BROWSER_SERVICE,
        command_runner=subprocess.run,
        client_factory=httpx.Client,
    ):
        self.machine_root = bootstrap_root(machine_root)
        self.client_modes = ClientModeStore(self.machine_root / "client.json")
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
        units = units or (self.service,)
        if (
            self.machine_root != DEFAULT_BOOTSTRAP_ROOT.expanduser().resolve()
            and set(units) & {
                DEFAULT_SERVICE, DEFAULT_TRAY_SERVICE, DEFAULT_UI_SERVICE, DEFAULT_BROWSER_SERVICE,
            }
        ):
            raise RuntimeError(
                "Custom instances need their own service units; "
                "refusing to control the installed instance"
            )
        return self.command_runner(
            ["systemctl", "--user", action, *units],
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
                health = self.request("GET", "/api/v1/health", timeout=2)
                if health.get("status") == "ok":
                    return health
                last_error = RuntimeError(f"server health: {health.get('status', 'unknown')}")
                time.sleep(0.1)
            except (FileNotFoundError, ValueError, json.JSONDecodeError, httpx.HTTPError) as error:
                last_error = error
                time.sleep(0.1)
        raise RuntimeError("The Harness server did not become ready") from last_error

    def _require_local_ui(self):
        if self.client_modes.load()["mode"] == "remote":
            raise RuntimeError(
                "The Harness remote UI is not installed; use mode local. "
                "The remote configuration is preserved for a future client."
            )

    def start(self):
        self._require_local_ui()
        # The tray requires the server, so this single operation restores the
        # complete user-facing runtime from either the launcher or the tray.
        self.systemctl("start", self.tray_service)
        return self.wait_until_ready()

    def open(self, timeout=30):
        self.start()
        deadline = time.monotonic() + timeout
        last_error = None
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                return self.request("POST", "/api/v1/ui/open", timeout=remaining)
            except httpx.HTTPStatusError as error:
                if error.response.status_code != 503:
                    raise
                last_error = error
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        raise RuntimeError("The Harness interface did not become ready") from last_error

    def restart(self):
        self._require_local_ui()
        try:
            self.request("POST", "/api/v1/server/prepare-restart", timeout=None)
        except (FileNotFoundError, httpx.ConnectError):
            # Recovery must also work when there is no living server to drain.
            pass
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
            return {"status": "unavailable", "reason": "remote_ui_not_installed", **client}
        try:
            return self.request("GET", "/api/v1/health", timeout=2)
        except (FileNotFoundError, ValueError, json.JSONDecodeError, httpx.HTTPError):
            return {"status": "stopped"}

    def data_root(self):
        if self.client_modes.load()["mode"] == "remote":
            return {"data_root": None, "mode": "remote"}
        return {"data_root": str(resolve_data_root(bootstrap=self.machine_root))}

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
    parser.add_argument("--machine-root", "--runtime-root", dest="machine_root")
    parser.add_argument("--endpoint")
    args = parser.parse_args()
    if args.action == "data-root":
        root = (
            configure_data_root(args.path, bootstrap=args.machine_root)
            if args.path else ensure_data_root_config(bootstrap=args.machine_root)
        )
        result = {"data_root": str(root), "restart_required": bool(args.path)}
    elif args.action == "mode":
        if args.path not in {None, "local", "remote"}:
            parser.error("mode accepts local or remote")
        result = HarnessControl(args.machine_root).mode(args.path, args.endpoint)
    else:
        if args.path is not None:
            parser.error("path is only accepted by data-root")
        try:
            result = getattr(HarnessControl(args.machine_root), args.action)()
        except RuntimeError as error:
            parser.exit(1, f"{error}\n")
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
