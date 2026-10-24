"""User-triggered audio transcription, independent of realtime voice."""

from the_framework import Plugin, ServerExtension

PLUGIN = Plugin(name="dictation", server_extensions=ServerExtension(
    name="dictation", service_factory="the_harness.plugins.dictation.server:build_service",
))
