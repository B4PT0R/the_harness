"""Harness presentation catalogue, using the Framework's durable artifact transport."""

from the_framework import Plugin
from the_framework.plugins.artifacts import ARTIFACTS
from .agent import HarnessArtifacts

PLUGIN = Plugin({**ARTIFACTS, "agent_extension": HarnessArtifacts})
