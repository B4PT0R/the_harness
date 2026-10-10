"""Canonical product runtime and local transport policy."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

from the_framework.server.runtime.application import ApplicationRuntime

from the_framework.server import FileResetTransaction

from .runtime_reset import RESET_ENTRIES, SESSION_RESET_ENTRIES, MEMORY_RESET_ENTRIES


EVENT_SUBPROTOCOL = "the-harness"
APPLICATION_SUBPROTOCOL = "the-harness-application"
REMOTE_EVENT_SUBPROTOCOL = "the-harness-remote-v1"
REMOTE_APPLICATION_SUBPROTOCOL = "the-harness-application-v1"



class Harness(ApplicationRuntime):
    """The Harness service composition atop the generic application runtime."""

    def __init__(self, supervisor, *, fleet_factory=None, restart=None, realtime_service=None):
        self.restart = restart
        self.realtime_service = realtime_service or (lambda: None)
        super().__init__(
            supervisor,
            fleet_factory=fleet_factory,
            application_subprotocol=APPLICATION_SUBPROTOCOL,
            activity_labels={
                "idle": "Disponible",
                "accepted": "Commande acceptée",
                "agent.turn.start": "Préparation du tour",
                "agent.step.start": "Mise à jour du contexte",
                "agent.compaction.start": "Compaction du contexte",
                "agent.generation.start": "Réponse du modèle",
                "agent.tool_calls.start": "Préparation des outils",
                "agent.step.end": "Finalisation du step",
                "agent.turn.end": "Finalisation du tour",
                "tool": "Exécution de {name}",
                "tool_result": "Résultat de l’outil reçu",
                "response": "Réponse du modèle",
            },
            reset_transaction_factory=lambda path: FileResetTransaction(path.parent, RESET_ENTRIES),
        )


    async def restart_server(self, intent):
        if self.restart is None:
            raise RuntimeError("server restart is not configured")
        if intent.get("resume_route") == "realtime_delegation":
            realtime = self.realtime_service()
            if realtime is not None:
                await realtime.wait_for_voice_turn_completion()
        result = self.restart(intent)
        if inspect.isawaitable(result):
            await result

    async def surface_notify(self, payload):
        realtime = self.realtime_service()
        if realtime is not None and realtime.active and realtime.realtime_response_active:
            await realtime.wait_for_voice_turn_completion(activation_timeout=0)
        await self.publish({
            **payload,
            "surface_event": payload.get("type"),
            "type": "interface_refresh_requested",
            "requested_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        })

    async def surface_progress(self, payload):
        await self.publish({"type": "surface_build_progress", **payload})

    async def reset_session(self):
        ready = await self.reset_runtime_state(
            transaction_factory=lambda path: FileResetTransaction(path.parent, SESSION_RESET_ENTRIES),
        )
        await self.publish({"type": "interface_refresh_requested"})
        return {
            "status": "reset",
            "session_id": ready.session_id,
            "cleared": ["conversation", "archive", "auxiliaries"],
            "preserved": ["memory", "registry", "config", "environment", "scheduler", "files"],
        }

    async def reset_memory(self):
        ready = await self.reset_runtime_state(
            transaction_factory=lambda path: FileResetTransaction(path.parent, MEMORY_RESET_ENTRIES),
        )
        return {
            "status": "reset", "session_id": ready.session_id,
            "cleared": ["memory"],
            "preserved": ["conversation", "archive", "registry", "config", "files"],
        }


def health_projection(base):
    """Retain the installed clients' health shape over framework diagnostics."""
    payload = dict(base)
    services = payload.pop("services")
    for name, service in services.items():
        if name != "runtime" and name not in payload and "details" in service:
            payload[name] = service["details"]
    return payload



__all__ = [
    "APPLICATION_SUBPROTOCOL",
    "EVENT_SUBPROTOCOL",
    "Harness",
    "REMOTE_APPLICATION_SUBPROTOCOL",
    "REMOTE_EVENT_SUBPROTOCOL",
    "health_projection",
]
