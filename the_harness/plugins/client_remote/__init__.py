"""Pairing, transport and policy for private remote clients."""

from the_framework import Capability, CapabilityRequirement, Plugin, ServerExtension

PLUGIN = Plugin(
    name="client_remote",
    server_extensions=(
        ServerExtension(
            name="client_remote", scope="session", service_factory="the_harness.plugins.client_remote.server:build_service",
        ),
        ServerExtension(
            name="client_remote_api", scope="session", service_factory="the_harness.plugins.client_remote.server:build_api",
        ),
    ),
    optional_capabilities=(CapabilityRequirement(name="scheduler.timing", min_version=1),),
    provides_capabilities=(Capability(name="clients.remote", version=1),),
)

__all__ = ["PLUGIN"]
