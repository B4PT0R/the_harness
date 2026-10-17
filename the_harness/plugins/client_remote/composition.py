"""Construct the private remote-client feature from product dependencies."""

from pathlib import Path

from the_framework.server.clients.remote import PROTOCOL_VERSION
from the_framework.server.clients.remote import RemoteClientPolicy

from ...runtime_composition import (
    REMOTE_APPLICATION_SUBPROTOCOL,
    REMOTE_EVENT_SUBPROTOCOL,
)
from .api import ClientRemoteApi
from .contributions import DESKTOP_ACCESS, POLICY
from .policy import BASE_REMOTE_POLICY, RemoteDesktopAccess, RemoteProjection
from .service import ClientRemoteService


class RemoteClientAssembly:
    """Plugin-owned construction of the private-client transport and policy."""

    def __init__(
        self, machine_root, *, context,
        storage_root=None, advertised_endpoint=None,
    ):
        self.context = context
        self.path = Path(storage_root or machine_root) / "remote-clients.json"
        self.advertised_endpoint = advertised_endpoint
        self.policy = BASE_REMOTE_POLICY
        self.desktop_access = RemoteDesktopAccess()
        self.projection = RemoteProjection()
        self.service = None

    def add_policy(self, contribution):
        if self.service is not None:
            raise RuntimeError("remote client policy is fixed after construction")
        self.policy = RemoteClientPolicy.compose(self.policy, contribution)

    def build_service(self, runtime):
        if self.service is not None:
            raise RuntimeError("remote client service was already constructed")
        for contribution in self.context.contributions(POLICY):
            self.add_policy(contribution)
        for configure in self.context.contributions(DESKTOP_ACCESS):
            configure(self.desktop_access)
        service = ClientRemoteService(
            runtime, self.path,
            pairing_scheme="theharness",
            application_subprotocol=REMOTE_APPLICATION_SUBPROTOCOL,
            event_subprotocol=REMOTE_EVENT_SUBPROTOCOL,
            policy=self.policy,
            desktop_access=self.desktop_access,
        )
        if self.advertised_endpoint is not None:
            self.advertised_endpoint = service._validate_endpoint(
                self.advertised_endpoint,
            )
        service.event_payload_adapter = self.projection.event
        runtime.application.register_router(service)
        self.service = service
        return service


def build_api(runtime, service, ingress, projection, *, advertised_endpoint=None):
    """Construct HTTP and WebSocket declarations for the installed transport."""
    return ClientRemoteApi(
        service,
        runtime,
        protocol_version=PROTOCOL_VERSION,
        advertised_endpoint=advertised_endpoint,
        session_projection=projection.session_page,
        ingress=ingress,
        event_subprotocols=(REMOTE_EVENT_SUBPROTOCOL,),
        application_subprotocols=(REMOTE_APPLICATION_SUBPROTOCOL,),
    )
