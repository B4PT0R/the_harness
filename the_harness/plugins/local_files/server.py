"""Build the local host's file editor preferences and HTTP surface."""

from pathlib import Path

from .service import LocalFilesService


def build_service(context):
    return LocalFilesService(Path(context.require("machine_root")) / "file-editor.json")
