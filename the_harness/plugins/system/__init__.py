"""System context enriched with the application's existing account quota."""

from inspect import getfile
from pathlib import Path

from the_framework import Plugin
from the_framework.agent.extensions.providers import provider
from the_framework.plugins.system import SYSTEM, SystemExtension as GenericSystemExtension


class SystemExtension(GenericSystemExtension):
    instructions_file = Path(getfile(GenericSystemExtension)).with_name("instructions.md")

    @provider(channels=("text",))
    async def account_quota(self):
        """Weekly account usage percentage (consumed, not remaining).

        Timestamps are Unix seconds. A null weekly window is unknown, not zero usage.
        Only ready data is fresh; stale/unavailable readings carry uncertainty.
        """
        try:
            return await self.agent.bridge.call("quota", "context", timeout_ms=5_000)
        except Exception:
            return {"status": "unavailable", "error": "quota_bridge_unavailable"}


PLUGIN = Plugin({**SYSTEM, "agent_extension": SystemExtension, "agent_binding_required": True})
