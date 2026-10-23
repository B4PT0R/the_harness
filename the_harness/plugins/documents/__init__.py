"""Local document conversion and bounded reading through Docling."""

from the_framework import Plugin
from .agent import DocumentsExtension

PLUGIN = Plugin(name="documents", agent_extension=DocumentsExtension)

__all__ = ["PLUGIN", "DocumentsExtension"]
