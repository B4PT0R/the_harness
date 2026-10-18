"""Desktop notification capability for the local host."""

from the_framework import CapabilityRequirement, Plugin, ServerExtension

PLUGIN = Plugin(
    name="desktop_notifications",
    server_extensions=ServerExtension(
        name="desktop_notifications",
        service_factory="the_harness.plugins.desktop_notifications.server:build_notifications",
    ),
    configure="the_harness.plugins.desktop_notifications.server:configure",
    optional_capabilities=(CapabilityRequirement(name="clients.remote", min_version=1),),
)

__all__ = ["PLUGIN"]
