"""Local Piper speech synthesis, isolated from the agent's Python environment."""

from the_framework import Plugin, ServerExtension
from .agent import TTSExtension

PLUGIN = Plugin(name="tts", agent_extension=TTSExtension, server_extensions=ServerExtension(
    name="tts", scope="session", service_factory="the_harness.plugins.tts.server:build_service",
))

__all__ = ["PLUGIN", "TTSExtension"]
