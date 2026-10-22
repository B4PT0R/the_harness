"""Product policy and projections for paired remote clients."""

from __future__ import annotations

import json
from collections.abc import Mapping

import modict

from the_framework.server.clients.remote import RemoteClientPolicy


BASE_REMOTE_DESKTOP_API = (
    ("GET", "/api/v1/quota"),
    ("PUT", "/api/v1/quota/policy"),
    ("POST", "/api/v1/quota/consume"),
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/status"),
    ("POST", "/api/v1/agent/compact"),
    ("DELETE", "/api/v1/session"),
    ("DELETE", "/api/v1/memory"),
    ("DELETE", "/api/v1/registry"),
    ("GET", "/api/v1/config"),
    ("PATCH", "/api/v1/config"),
    ("GET", "/api/v1/client-remote"),
    ("POST", "/api/v1/client-remote/pairings"),
)


BASE_REMOTE_POLICY = RemoteClientPolicy(
    default_scopes=("chat",),
    platform_scopes={"desktop": ("desktop", "full_ui"),
                     "android": ("mobile", "session:read", "agent:read", "plugins:read", "agent:write", "realtime:write")},
    capabilities=frozenset({"conversation", "notifications"}),
)


class RemoteDesktopAccess:
    """Startup-fixed HTTP allowlist for a paired desktop or Quest client."""

    def __init__(self):
        self.exact = set()
        self.subtrees = []
        self.frozen = False
        self.add_exact(*BASE_REMOTE_DESKTOP_API)
        self.add_subtree("/api/v1/client-remote/clients", ("DELETE",), include_base=False)
        self.add_subtree("/api/v1/bucket", ("GET",), include_base=False)

    def _ensure_mutable(self):
        if self.frozen:
            raise RuntimeError("remote desktop access is fixed after startup")

    @staticmethod
    def _path(path):
        if not isinstance(path, str) or not path.startswith("/api/v1/"):
            raise ValueError("remote desktop route must be under /api/v1/")
        if "?" in path or "#" in path or "//" in path or any(
            segment in {".", ".."} for segment in path.split("/")
        ):
            raise ValueError("invalid remote desktop route")
        return path.rstrip("/")

    @staticmethod
    def _method(method):
        if not isinstance(method, str) or method.upper() not in {
            "GET", "POST", "PUT", "PATCH", "DELETE",
        }:
            raise ValueError("invalid remote desktop HTTP method")
        return method.upper()

    def add_exact(self, *routes):
        self._ensure_mutable()
        normalized = {(self._method(method), self._path(path)) for method, path in routes}
        if self.exact & normalized:
            raise ValueError("duplicate remote desktop route")
        self.exact.update(normalized)

    def add_subtree(self, path, methods, *, include_base=True):
        self._ensure_mutable()
        prefix = self._path(path)
        normalized = frozenset(self._method(method) for method in methods)
        if not normalized or any(existing[0] == prefix for existing in self.subtrees):
            raise ValueError("duplicate or empty remote desktop route subtree")
        self.subtrees.append((prefix, normalized, include_base))

    def freeze(self):
        self.exact = frozenset(self.exact)
        self.subtrees = tuple(self.subtrees)
        self.frozen = True

    def allowed(self, method, path):
        if not isinstance(path, str) or "//" in path or any(
            segment in {".", ".."} for segment in path.split("/")
        ):
            return False
        method = method.upper()
        if (method, path) in self.exact:
            return True
        return any(
            method in methods
            and (path.startswith(f"{prefix}/") or (include_base and path == prefix))
            for prefix, methods, include_base in self.subtrees
        )


def mobile_api_allowed(method, path):
    """A companion can chat, not administer the host or read configuration."""
    if "//" in path or any(part in {".", ".."} for part in path.split("/")):
        return False
    if method == "GET":
        return path in {"/remote/v1/alerts", "/remote/v1/notifications", "/remote/v1/notifications/wait", "/ui", "/ui/", "/api/v1/quota", "/api/v1/session", "/api/v1/status", "/api/v1/plugins"} or path.startswith(("/ui/assets/", "/api/v1/bucket/")) or path == "/ui/assistant.svg"
    if method == "POST":
        return path in {"/api/v1/quota/consume", "/remote/v1/alerts/receipt", "/api/v1/agent/prompt", "/api/v1/agent/attachments", "/api/v1/agent/interrupt", "/api/v1/agent/compact", "/api/v1/realtime/calls", "/api/v1/realtime/calls/current/ready", "/api/v1/realtime/calls/current/suspend"}
    return method == "DELETE" and path == "/api/v1/realtime/calls/current"


def _wire_value(value):
    if value is modict.MISSING:
        return None
    if isinstance(value, Mapping):
        return {
            key: _wire_value(value[key])
            for key in value
            if value[key] is not modict.MISSING
        }
    if isinstance(value, (list, tuple)):
        return [_wire_value(item) for item in value if item is not modict.MISSING]
    return value


def wire_mapping(value):
    return _wire_value(value) if isinstance(value, Mapping) else {}


class RemoteProjection:
    """Keep the remote wire shape while withholding local files and config."""

    @staticmethod
    def tool_activity(item):
        payload = wire_mapping(item)
        if payload.get("type") != "function_call":
            return None
        try:
            arguments = json.loads(payload.get("arguments") or "{}")
        except (TypeError, json.JSONDecodeError):
            arguments = {}
        feedback = arguments.get("user_feedback") if isinstance(arguments, dict) else None
        return {
            "kind": "tool_activity",
            "id": f"tool-{payload.get('call_id') or payload.get('id')}",
            "feedback": (
                feedback.strip()
                if isinstance(feedback, str) and feedback.strip()
                else f"Outil {payload.get('name') or 'terminé'}"
            ),
            "status": "completed",
        }

    def session_page(self, client_id, page):
        payload = wire_mapping(page)
        turns = []
        for turn in payload.get("turns", []):
            turn_payload = wire_mapping(turn)
            items = []
            for item in turn_payload.get("items", []):
                item_payload = wire_mapping(item)
                if (
                    item_payload.get("type") == "image"
                    or isinstance(item_payload.get("path"), str)
                ):
                    continue  # Never expose host-local files to a remote client.
                elif item_payload.get("type") == "function_call":
                    items.append(self.tool_activity(item))
                else:
                    items.append(item_payload)
            turns.append({**turn_payload, "items": items})
        return {**payload, "turns": turns}

    async def event(self, client_id, event):
        payload = wire_mapping(event.get("payload"))
        if payload.get("type") != "command_event":
            return event
        inner = wire_mapping(payload.get("event"))
        if inner.get("type") == "agent.config.updated":
            return {
                **event,
                "payload": {
                    "type": "assistant_state",
                    "assistant": {},
                },
            }
        if inner.get("type") in {"agent.tool_call.start", "agent.tool_call.end"}:
            tool_call = wire_mapping(inner.get("tool_call"))
            return {
                **event,
                "payload": {
                    "type": "command_event",
                    "event": {
                        "type": inner["type"],
                        "user_feedback": inner.get("user_feedback"),
                        "tool_call": {
                            "call_id": tool_call.get("call_id"),
                            "name": tool_call.get("name"),
                        },
                        "output": wire_mapping(inner.get("output")),
                    },
                },
            }
        if inner.get("type") != "agent.response_item.added":
            return event
        item = wire_mapping(inner.get("item"))
        if (
            item.get("type") != "image"
            and not isinstance(item.get("path"), str)
        ):
            return event
        return {
            **event,
            "payload": {
                **payload,
                "event": {
                    **inner,
                    "item": {
                        key: value for key, value in item.items() if key != "path"
                    },
                },
            },
        }

__all__ = [
    "RemoteProjection",
    "BASE_REMOTE_POLICY",
    "RemoteDesktopAccess",
    "wire_mapping",
]
