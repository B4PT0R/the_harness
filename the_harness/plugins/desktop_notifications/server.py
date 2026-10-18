"""Server runtime and routes owned by desktop notifications."""

from pathlib import Path

from the_framework import ServerExtension

from ..client_remote.contributions import DESKTOP_ACCESS
from .service import DesktopNotificationService


def build_server_extensions(context):
    context.contribute(
        DESKTOP_ACCESS,
        lambda access: access.add_exact(
            ("GET", "/api/v1/notifications/desktop"),
            ("PUT", "/api/v1/notifications/desktop"),
        ),
    )

    return ServerExtension(
        name="desktop_notifications",
        service_factory=build_notifications,
    )


def build_notifications(context, canonical_transport, client_remote=None):
    service = DesktopNotificationService(
        Path(context.require("machine_root")) / "desktop-notifications.json",
        canonical_transport,
    )
    if client_remote is not None:
        client_remote.message_notification_listener = service.notify
    return service
