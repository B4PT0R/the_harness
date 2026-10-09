"""Small machine-local configuration for the bimodal Chromium client."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .runtime_paths import bootstrap_root


def normalize_remote_endpoint(value):
    parsed = urlparse(str(value).strip())
    loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("remote endpoint must be an HTTP(S) origin")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("remote endpoint must not contain credentials, query, or fragment")
    if parsed.scheme != "https" and not loopback:
        raise ValueError("non-loopback remote endpoints require HTTPS")
    path = parsed.path.rstrip("/")
    if path:
        raise ValueError("remote endpoint must not contain a path")
    return f"{parsed.scheme}://{parsed.netloc}"


class ClientModeStore:
    def __init__(self, path=None):
        self.path = Path(path or bootstrap_root() / "client.json")

    def load(self):
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"version": 1, "mode": "local"}
        if payload.get("version") != 1 or payload.get("mode") not in {"local", "remote"}:
            raise ValueError("invalid desktop client configuration")
        if payload["mode"] == "remote":
            payload["endpoint"] = normalize_remote_endpoint(payload.get("endpoint"))
        return payload

    def save(self, mode, endpoint=None):
        if mode not in {"local", "remote"}:
            raise ValueError("desktop mode must be local or remote")
        payload = {"version": 1, "mode": mode}
        if mode == "remote":
            payload["endpoint"] = normalize_remote_endpoint(endpoint)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(self.path)
        return payload
