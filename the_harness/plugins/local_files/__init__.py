"""User-initiated text-file editing on the local host."""

from the_framework import Plugin, ServerExtension

PLUGIN = Plugin(name="local_files", server_extensions=ServerExtension(
    name="local_files", service_factory="the_harness.plugins.local_files.server:build_service",
))
