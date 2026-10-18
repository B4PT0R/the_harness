import secrets
from pathlib import Path

from the_framework import BuildContext, ServerExtension
from the_framework.server.clients.browser_rpc import BrowserRPCClient

from .application import application
from .security import HarnessSecurityPolicy
from .reset_api import SelectiveResetApi
from .runtime_composition import (
    HarnessSession,
    health_projection,
    APPLICATION_SUBPROTOCOL, EVENT_SUBPROTOCOL,
)


def create_app(
    supervisor=None,
    *,
    session_path=None,
    token=None,
    browser_token=None,
    allowed_origins=(),
    realtime_client_factory=None,
    fleet_factory=None,
    ui_root=None,
    origin=None,
    restart=None,
    browser_client_factory=BrowserRPCClient,
    browser_runtime_root=None,
    client_remote_root=None,
    advertised_remote_endpoint=None,
):
    session_path = Path(supervisor.session_path if supervisor is not None else session_path)
    data_root = session_path.parent
    token = token or secrets.token_urlsafe(32)
    browser_token = browser_token or token
    context = BuildContext(
        data_root=data_root, session_path=session_path, ui_root=ui_root, origin=origin,
        machine_root=Path(browser_runtime_root or data_root),
        plugins={
            "realtime": {"client_factory": realtime_client_factory},
            "hosted_ui": {
                "browser_token": browser_token,
                "browser_client_factory": browser_client_factory,
            },
            "client_remote": {
                "storage_root": client_remote_root,
                "advertised_endpoint": advertised_remote_endpoint,
            },
        },
    )
    security = HarnessSecurityPolicy(
        token=token, browser_token=browser_token,
        remote_clients=lambda: (application.default_session.services.get("client_remote")
                                if application.default_session is not None else None),
        allowed_origins=allowed_origins,
    )
    return application.build(
        "the_harness.application:application", context,
        supervisor=supervisor, security=security,
        session_factory=lambda worker, context: HarnessSession(
            worker, fleet_factory=fleet_factory, restart=restart,
        ),
        health_projection=health_projection,
        event_handshake=security.socket_handshake(supported=(EVENT_SUBPROTOCOL,)),
        application_handshake=security.socket_handshake(supported=(APPLICATION_SUBPROTOCOL,)),
        session_extensions=lambda runtime: (
            ServerExtension(
                name="selective_reset", scope="session", endpoints=(SelectiveResetApi(runtime),),
                requires_services=("runtime",),
            ),
        ),
    )
