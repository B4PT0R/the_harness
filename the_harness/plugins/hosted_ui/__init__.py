"""Hosted client interface and local browser control."""

from the_framework import Plugin, ServerExtension

PLUGIN = Plugin(
    name="hosted_ui",
    server_extension=ServerExtension(
        name="hosted_ui", service_factory="the_harness.plugins.hosted_ui.server:build_service",
    ),
)

__all__ = ["PLUGIN"]
