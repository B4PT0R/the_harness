from the_framework.plugins.memory import MEMORY
from the_framework.plugins.memory import MemoryConfig
from the_framework import Plugin
from .agent import MemoryExtension

PLUGIN = Plugin({**MEMORY, "agent_extension": MemoryExtension})

__all__ = ["MemoryConfig", "MemoryExtension", "PLUGIN"]
