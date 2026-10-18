"""Images through the backend-hosted generation tool and local vision inputs."""

from the_framework import Plugin
from .agent import ImagesExtension

PLUGIN = Plugin(name="images", agent_extension=ImagesExtension)

__all__ = ["PLUGIN", "ImagesExtension"]
