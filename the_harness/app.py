import secrets
from pathlib import Path

from the_framework import ApplicationSpec, BuildContext, ServerExtension
from the_framework.server import CanonicalAgentApi, ApplicationHealthApi, application_server_extensions
from the_framework.server.clients.browser_rpc import BrowserRPCClient

from .application import application
from .http_boundary import access_boundary
from .security import HarnessSecurityPolicy
from .reset_api import MemoryResetApi
from .runtime_composition import (
    Harness,
    health_projection,
    local_socket_handshake,
    APPLICATION_SUBPROTOCOL, EVENT_SUBPROTOCOL,
)


def create_app(
    supervisor,
    token=None,
    browser_token=None,
    allowed_origins=(),
    realtime_client_factory=None,
    remote_control_client_factory=None,
    fleet_factory=None,
    ui_root=None,
    restart=None,
    browser_client_factory=BrowserRPCClient,
    browser_runtime_root=None,
    client_remote_root=None,
    advertised_remote_endpoint=None,
    embedding_client_factory=None,
):
    data_root = Path(supervisor.session_path).parent
    token = token or secrets.token_urlsafe(32)
    browser_token = browser_token or token
    app = None

    def realtime_service():
        if app is None:
            raise RuntimeError("realtime service is not available before application build")
        api = app.state.application.services.get("realtime")
        return api.controller if api is not None else None

    harness = Harness(
        supervisor,
        fleet_factory=fleet_factory,
        restart=restart,
        realtime_service=realtime_service,
    )
    machine_root = Path(browser_runtime_root or Path(supervisor.session_path).parent)
    build_context = BuildContext(
        data_root=data_root, supervisor=supervisor, harness=harness,
        plugin_state_path=data_root / "plugins.json", surface_root=data_root / "surfaces",
        surface_notify=harness.surface_notify, surface_progress=harness.surface_progress,
        system_restart=harness.restart_server if restart is not None else None,
        embedding_client_factory=embedding_client_factory,
        browser_token=browser_token, browser_client_factory=browser_client_factory,
        browser_runtime_root=browser_runtime_root, machine_root=machine_root,
        remote_control_client_factory=remote_control_client_factory,
        realtime_client_factory=realtime_client_factory,
        client_remote_root=client_remote_root, advertised_remote_endpoint=advertised_remote_endpoint,
    )

    def remote_clients():
        return build_context.get("remote_clients")

    if ui_root is not None:
        build_context.provide("ui_root", ui_root)

    application_spec = ApplicationSpec({
        **application,
        "security": HarnessSecurityPolicy(token=token, browser_token=browser_token, remote_clients=remote_clients),
        "server_extensions": (
            ServerExtension(
                name="memory_reset", endpoints=(MemoryResetApi(harness),),
                requires_services=("runtime",),
            ),
            *application_server_extensions(
                harness,
                agent_api=CanonicalAgentApi(harness, session_projection="display", reset_handler=harness.reset_session),
                health_api=ApplicationHealthApi(health_projection, runtime=harness),
                event_handshake=local_socket_handshake(
                    token=token, browser_token=browser_token,
                    allowed_origins=allowed_origins,
                    supported=(EVENT_SUBPROTOCOL,),
                ),
                application_handshake=local_socket_handshake(
                    token=token, browser_token=browser_token,
                    allowed_origins=allowed_origins,
                    supported=(APPLICATION_SUBPROTOCOL,),
                ),
            ),
            access_boundary(
                token=token,
                browser_token=browser_token,
                remote_clients=remote_clients,
            ),
        ),
    })
    app = application_spec.build(build_context)
    return app
