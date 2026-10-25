"""Persistent, process-isolated Python sessions owned by the Harness."""

from the_framework import Plugin
from .agent import PynteractExtension

PLUGIN = Plugin(name="pynteract", agent_extension=PynteractExtension)

__all__ = ["PLUGIN", "PynteractExtension"]
