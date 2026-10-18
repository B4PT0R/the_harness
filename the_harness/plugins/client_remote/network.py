"""Explicit, machine-local opt-in to private Tailscale Serve access."""

import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from the_framework.server.clients import tailscale
from the_framework.utils.persistence import atomic_text_writer


class PrivateNetwork:
    def __init__(self, root, origin=None):
        self.path = Path(root) / "remote-access.json"
        self.port = urlsplit(origin).port if origin else None
        self.endpoint = None
        self.error = None
        self.settings = self.read(self.path)

    @staticmethod
    def read(path):
        try:
            value = json.loads(Path(path).read_text())
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, ValueError):
            return {}

    @staticmethod
    def private_serve():
        current = tailscale.read_serve_status()
        if not isinstance(current, dict):
            raise RuntimeError("Invalid Tailscale Serve configuration")
        funnel = current.get("AllowFunnel") or {}
        if not isinstance(funnel, dict) or any(funnel.values()):
            raise RuntimeError("Disable Tailscale Funnel first; only private Serve is supported")
        return current

    def start(self):
        if self.settings.get("enabled"):
            try:
                endpoint = tailscale.endpoint_from_status(tailscale.read_status())
                self.endpoint = tailscale.validate_serve_endpoint(endpoint, self.private_serve(), self.port)
            except RuntimeError as error:
                self.error = str(error)

    def status(self):
        result = {"enabled": self.endpoint is not None, "endpoint": self.endpoint,
                  "port": self.port, "available": False, "error": self.error}
        try:
            candidate = tailscale.endpoint_from_status(tailscale.read_status())
            result.update(available=True, suggested_endpoint=candidate)
            tailscale.validate_serve_endpoint(candidate, self.private_serve(), self.port)
            result["serve_ready"] = True
        except RuntimeError as error:
            result.update(serve_ready=False, error=str(error))
        return result

    def set_enabled(self, enabled):
        if enabled:
            if self.port is None:
                raise RuntimeError("The local server port is unavailable")
            endpoint = tailscale.endpoint_from_status(tailscale.read_status())
            current = self.private_serve()
            if current.get("Web"):
                # Never replace another application's reverse proxy.
                tailscale.validate_serve_endpoint(endpoint, current, self.port)
            else:
                try:
                    tailscale.configure_serve(self.port)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                    raise RuntimeError("Unable to configure Tailscale Serve; check Tailscale permissions") from error
            tailscale.validate_serve_endpoint(endpoint, self.private_serve(), self.port)
        else:
            endpoint = None
        settings = {"enabled": enabled, "port": self.port}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with atomic_text_writer(self.path) as stream:
            json.dump(settings, stream)
        self.settings = settings
        self.endpoint = endpoint
        self.error = None
        return self.status()
