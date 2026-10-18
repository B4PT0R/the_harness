"""Compose private-client transport, product policy and HTTP/WebSocket API."""

from pathlib import Path

from the_framework import ServerExtension
from the_framework.server.clients.remote import RemoteClientPolicy

from ...runtime_composition import (
    REMOTE_APPLICATION_SUBPROTOCOL,
    REMOTE_EVENT_SUBPROTOCOL,
)
from .api import ClientRemoteApi
from .contributions import DESKTOP_ACCESS, POLICY
from .policy import BASE_REMOTE_POLICY, RemoteDesktopAccess, RemoteProjection
from .service import ClientRemoteService


def build_server_extensions(context):
    options = context.plugin("client_remote")
    path = Path(options.get("storage_root") or context.require("machine_root")) / "remote-clients.json"
    advertised_endpoint = options.get("advertised_endpoint")
    if advertised_endpoint is not None:
        advertised_endpoint = ClientRemoteService._validate_endpoint(advertised_endpoint)

    def build_service(runtime):
        policy = RemoteClientPolicy.compose(BASE_REMOTE_POLICY, *context.contributions(POLICY))
        desktop_access = RemoteDesktopAccess()
        for configure in context.contributions(DESKTOP_ACCESS):
            configure(desktop_access)
        service = ClientRemoteService(
            runtime, path, pairing_scheme="theharness",
            application_subprotocol=REMOTE_APPLICATION_SUBPROTOCOL,
            event_subprotocol=REMOTE_EVENT_SUBPROTOCOL,
            policy=policy, desktop_access=desktop_access,
        )
        service.event_payload_adapter = RemoteProjection().event
        runtime.application.register_router(service)
        return service

    def build_api(client_remote, chat):
        return ClientRemoteApi(client_remote, chat.ingress, advertised_endpoint=advertised_endpoint)

    return (
        ServerExtension(name="client_remote", service_factory=build_service),
        ServerExtension(
            name="client_remote_api", service_factory=build_api,
            endpoints="service", websockets="service",
        ),
    )
