"""Desktop notification capability for the local host."""

from the_framework import CapabilityRequirement, Plugin

PLUGIN = Plugin(
    name="desktop_notifications",
    server_extension="the_harness.plugins.desktop_notifications.server:build_server_extensions",
    optional_capabilities=(CapabilityRequirement(name="clients.remote", min_version=1),),
)

__all__ = ["PLUGIN"]
