"""User-initiated text-file editing on the local host."""

from pathlib import Path

from the_framework import Plugin, ServerExtension

from .service import LocalFilesService


def build_server_extensions(context):
    return ServerExtension(
        name="local_files",
        service_factory=lambda: LocalFilesService(
            Path(context.require("machine_root")) / "file-editor.json",
        ),
        endpoints="service",
    )


PLUGIN = Plugin(name="local_files", server_extension=build_server_extensions)
