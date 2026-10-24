"""Local Piper speech synthesis, isolated from the agent's Python environment."""

from the_framework import Plugin
from .agent import TTSExtension

PLUGIN = Plugin(name="tts", agent_extension=TTSExtension)

__all__ = ["PLUGIN", "TTSExtension"]
