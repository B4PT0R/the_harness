"""Hosted client interface and local browser control."""

from the_framework import Plugin

PLUGIN = Plugin(
    name="hosted_ui",
    server_extension="the_harness.plugins.hosted_ui.server:build_server_extensions",
)

__all__ = ["PLUGIN"]
