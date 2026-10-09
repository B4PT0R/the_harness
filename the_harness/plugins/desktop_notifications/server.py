"""Server runtime and routes owned by desktop notifications."""

from pathlib import Path

from the_framework import ServerExtension

from ..client_remote.contributions import DESKTOP_ACCESS, NOTIFICATION_LISTENER
from .service import DesktopNotificationApi, DesktopNotificationService


def build_server_extensions(context):
    context.contribute(
        DESKTOP_ACCESS,
        lambda access: access.add_exact(
            ("GET", "/api/v1/notifications/desktop"),
            ("PUT", "/api/v1/notifications/desktop"),
        ),
    )
    service = DesktopNotificationService(
        Path(context.require("machine_root")) / "desktop-notifications.json",
        context.require("harness").application,
    )
    context.contribute(NOTIFICATION_LISTENER, service.notify)
    return ServerExtension(
        name="desktop_notifications",
        service=service,
        endpoints=(DesktopNotificationApi(service),),
        requires_services=("runtime",),
    )
