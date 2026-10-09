"""General-purpose primary agent declaration."""

import asyncio

from the_framework.agent import AgentSpec, Worker
from the_framework.agent.runtime.protocol import PromptRequest

from .prompts import compaction_instructions, install_assistant_instructions
from .turn_timing import TurnTiming


async def measure_turn(agent, command, call_next):
    """Product middleware keeping wall-clock timing out of the core worker."""
    timing = getattr(agent, "turn_timing", None)
    if not isinstance(command, PromptRequest) or timing is None:
        async for event in call_next(command):
            yield event
        return
    timing.begin()
    try:
        async for event in call_next(command):
            yield event
    finally:
        await asyncio.to_thread(timing.finish)


def configure_assistant(agent):
    agent.turn_timing = TurnTiming(agent.session.path)
    agent.configs.compaction.instructions = compaction_instructions(
        agent.configs.compaction.instructions
    )
    install_assistant_instructions(agent)
    return agent


def assistant_resources(session_path):
    from .assistant_runtime import runtime_resources

    return runtime_resources(session_path)


ASSISTANT_AGENT = AgentSpec(
    name="assistant",
    description=(
        "General-purpose local assistant and sole owner of canonical conversation "
        "history."
    ),
    session_mode='durable',
    initializers=(configure_assistant,),
    command_middleware=(measure_turn,),
    projections={
        "display": Worker.conversation_projection,
        "remote": Worker.remote_projection,
    },
    resources=assistant_resources,
)


__all__ = ["ASSISTANT_AGENT"]
