import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock


class TurnTiming:
    """Persist completed turn boundaries without adding them to conversation history."""

    def __init__(self, path=None, *, now=None):
        self.path = Path(path) if path is not None else None
        self._now = now or (lambda: datetime.now(timezone.utc).astimezone())
        self._lock = RLock()
        self._active_started_at = None
        self._previous = self._load()

    @staticmethod
    def _parse(value):
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed

    def _load(self):
        if self.path is None:
            return None
        try:
            payload = json.loads(self.path.read_text())
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        started_at = self._parse(payload.get("started_at"))
        ended_at = self._parse(payload.get("ended_at"))
        if started_at is None or ended_at is None or ended_at < started_at:
            return None
        return {"started_at": started_at, "ended_at": ended_at}

    def _save(self, payload):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
                json.dump(payload, handle, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def begin(self):
        with self._lock:
            self._active_started_at = self._now()
            return self.context()

    def finish(self):
        with self._lock:
            if self._active_started_at is None:
                return None
            ended_at = self._now()
            if ended_at < self._active_started_at:
                ended_at = self._active_started_at
            self._previous = {
                "started_at": self._active_started_at,
                "ended_at": ended_at,
            }
            self._active_started_at = None
            payload = {
                "started_at": self._previous["started_at"].isoformat(),
                "ended_at": self._previous["ended_at"].isoformat(),
            }
            self._save(payload)
            return payload

    def context(self):
        with self._lock:
            if self._active_started_at is None:
                return None
            current = self._active_started_at
            previous = self._previous
            result = {"current_turn_started_at": current.isoformat()}
            if previous is None:
                result["previous_turn"] = None
                return result
            duration = max(
                0.0,
                (previous["ended_at"] - previous["started_at"]).total_seconds(),
            )
            elapsed = max(0.0, (current - previous["ended_at"]).total_seconds())
            result["previous_turn"] = {
                "started_at": previous["started_at"].isoformat(),
                "ended_at": previous["ended_at"].isoformat(),
                "duration_seconds": round(duration, 3),
                "elapsed_since_end_seconds": round(elapsed, 3),
            }
            return result
