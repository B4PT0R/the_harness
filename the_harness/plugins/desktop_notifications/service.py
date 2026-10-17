"""Host desktop notifications emitted while the local UI is closed."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path

from the_framework.server import endpoint

logger = logging.getLogger(__name__)


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class LinuxDesktopNotificationSender:
    """Small non-blocking adapter around the freedesktop notification client."""

    def __init__(self, executable: str | None = None):
        self.executable = executable or shutil.which("notify-send")

    @property
    def available(self) -> bool:
        return self.executable is not None

    async def __call__(self, *, title: str, body: str) -> bool:
        if self.executable is None:
            return False
        process = await asyncio.create_subprocess_exec(
            self.executable,
            "--app-name=The Harness",
            "--urgency=normal",
            "--category=im.received",
            title,
            body,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            return await asyncio.wait_for(process.wait(), timeout=5) == 0
        except TimeoutError:
            process.kill()
            await process.wait()
            return False


class DesktopNotificationService:
    def __init__(self, path, transport, *, sender=None):
        self.path = Path(path)
        self.transport = transport
        self.sender = sender or LinuxDesktopNotificationSender()
        self.enabled = True
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("settings must be a JSON object")
        except FileNotFoundError:
            return
        except (OSError, TypeError, ValueError) as error:
            logger.warning("desktop notification settings could not be read: %s", error)
            return
        self.enabled = payload.get("enabled") is not False

    @endpoint(
        "get", "/api/v1/notifications/desktop",
        response={"type": "object"},
        authorization={"scope": "settings:read"},
    )
    def status(self):
        """Return host desktop notification preferences and availability."""
        return self.snapshot()

    def snapshot(self) -> dict:
        return {
            "enabled": self.enabled,
            "available": bool(getattr(self.sender, "available", True)),
            "delivery": "host_desktop",
        }

    @endpoint(
        "put", "/api/v1/notifications/desktop",
        request={
            "type": "object",
            "properties": {"enabled": {"type": "boolean"}},
            "required": ["enabled"],
            "additionalProperties": False,
        },
        response={"type": "object"},
        authorization={"scope": "settings:write"},
    )
    def update(self, enabled: bool) -> dict:
        """Persist host desktop notification preferences."""
        self.enabled = enabled
        _atomic_json(self.path, {"version": 1, "enabled": enabled})
        return self.snapshot()

    async def notify(self, _message_id: str) -> None:
        # The local UI consumes canonical events, not the capability bridge.
        # Paired clients have a separate transport and cannot suppress host notices.
        # Connectivity is intentionally not a claim about focus or visibility.
        if not self.enabled or self.transport.primary_event_connection_count:
            return
        try:
            await self.sender(
                title="The Harness",
                body="Ton assistant t’a envoyé un message",
            )
        except Exception as error:  # noqa: BLE001 - desktop integration is optional
            logger.warning("desktop notification delivery failed: %s", error)
