"""Hold model-generating commands in place until account quota recovers."""

import asyncio
import json

from the_framework.agent.runtime.bridge import ApplicationError
from the_framework.agent.runtime.protocol import CompactRequest, PromptRequest


async def wait_for_quota(agent, command, call_next):
    if isinstance(command, (PromptRequest, CompactRequest)):
        async def status(value):
            command.status = value
            await asyncio.to_thread(
                agent.session.set_command, command.id, value,
                deferred=json.loads(json.dumps(command)) if value == "waiting" else None)

        blocked = False
        while command.status != "interrupted":
            # Waiting is not an inference turn: it cannot receive steering.
            if command.status != "waiting":
                await status("waiting")
            try:
                decision = await agent.bridge.call("quota", "admission", timeout_ms=40_000)
                blocked = decision.get("allowed") is not True
            except ApplicationError:
                # Unknown initial quota must not make local repair impossible.
                # Once exhausted, a bridge outage must not release the hold.
                pass
            if command.status == "interrupted":
                return
            if not blocked:
                await status("active")
                break
            await asyncio.sleep(1)
        else:
            return
    async for event in call_next(command):
        yield event
