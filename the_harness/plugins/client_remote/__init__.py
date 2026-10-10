"""Pairing, transport and policy for private remote clients."""

from the_framework import Capability, CapabilityRequirement, Plugin

PLUGIN = Plugin(
    name="client_remote",
    server_extension="the_harness.plugins.client_remote.server:build_server_extensions",
    provides_capabilities=(Capability(name="clients.remote", version=1),),
    requires_capabilities=(CapabilityRequirement(name="conversation.ingress", min_version=1),),
)

__all__ = ["PLUGIN"]
