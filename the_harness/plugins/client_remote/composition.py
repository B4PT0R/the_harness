"""Construct the private remote-client feature from product dependencies."""

from pathlib import Path

from the_framework.server.clients.remote import PROTOCOL_VERSION
from the_framework.server.clients.remote import RemoteClientPolicy

from ...runtime_composition import (
    REMOTE_APPLICATION_SUBPROTOCOL,
    REMOTE_EVENT_SUBPROTOCOL,
)
from .api import ClientRemoteApi
from .contributions import DESKTOP_ACCESS, NOTIFICATION_LISTENER, POLICY
from .policy import BASE_REMOTE_POLICY, RemoteDesktopAccess, RemoteProjection
from .service import ClientRemoteService


class RemoteClientAssembly:
    """Startup declarations shared with security before the transport exists."""

    def __init__(
        self, harness, machine_root, *, context,
        storage_root=None, advertised_endpoint=None,
    ):
        self.harness = harness
        self.context = context
        self.path = Path(storage_root or machine_root) / "remote-clients.json"
        self.advertised_endpoint = advertised_endpoint
        self.policy = BASE_REMOTE_POLICY
        self.desktop_access = RemoteDesktopAccess()
        self.projection = RemoteProjection(harness)
        self.message_notification_listener = None
        self.service = None

    def add_policy(self, contribution):
        if self.service is not None:
            raise RuntimeError("remote client policy is fixed after construction")
        self.policy = RemoteClientPolicy.compose(self.policy, contribution)

    def authenticate(self, token):
        return self.service.authenticate(token) if self.service is not None else None

    def desktop_api_allowed(self, method, path):
        return self.desktop_access.allowed(method, path)

    def build_service(self, runtime):
        if self.service is not None:
            raise RuntimeError("remote client service was already constructed")
        for contribution in self.context.contributions(POLICY):
            self.add_policy(contribution)
        for configure in self.context.contributions(DESKTOP_ACCESS):
            configure(self.desktop_access)
        listeners = self.context.contributions(NOTIFICATION_LISTENER)
        if len(listeners) > 1:
            raise ValueError("multiple remote notification listeners")
        if listeners:
            self.message_notification_listener = listeners[0]
        service = ClientRemoteService(
            runtime, self.path,
            pairing_scheme="theharness",
            application_subprotocol=REMOTE_APPLICATION_SUBPROTOCOL,
            event_subprotocol=REMOTE_EVENT_SUBPROTOCOL,
            policy=self.policy,
            desktop_access=self.desktop_access,
            message_notification_listener=self.message_notification_listener,
        )
        if self.advertised_endpoint is not None:
            self.advertised_endpoint = service._validate_endpoint(
                self.advertised_endpoint,
            )
        service.event_payload_adapter = self.projection.event
        service.application_payload_adapter = self.projection.application_payload
        runtime.application.register_router(service)
        self.service = service
        return service


def build_api(
    harness, service, realtime, realtime_state, projection, *, advertised_endpoint=None,
):
    """Construct HTTP and WebSocket declarations for the installed transport."""

    async def on_revoke(client_id):
        if realtime_state is not None and realtime_state.remote_owner == client_id:
            await realtime.stop()
            realtime_state.clear_remote()

    api = ClientRemoteApi(
        service,
        harness,
        protocol_version=PROTOCOL_VERSION,
        advertised_endpoint=advertised_endpoint,
        session_projection=projection.session_page,
        assistant_projection=projection.assistant,
        realtime=realtime.controller if realtime is not None else None,
        on_revoke=on_revoke,
        event_subprotocols=(
            REMOTE_EVENT_SUBPROTOCOL,
        ),
        application_subprotocols=(
            REMOTE_APPLICATION_SUBPROTOCOL,
                ),
    )
    return api
