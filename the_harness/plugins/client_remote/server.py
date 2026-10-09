"""Installed server runtime for private remote-client pairing and transport."""

from the_framework import ServerExtension

from .composition import RemoteClientAssembly, build_api


def build_server_extensions(context):
    assembly = context.provide(
        "remote_clients",
        RemoteClientAssembly(
            context.require("harness"),
            context.require("machine_root"),
            context=context,
            storage_root=context.get("client_remote_root"),
            advertised_endpoint=context.get("advertised_remote_endpoint"),
        ),
    )

    def build_client_remote_api(client_remote, realtime=None):
        return build_api(
            context.require("harness"), client_remote, realtime,
            None, assembly.projection,
            advertised_endpoint=assembly.advertised_endpoint,
        )

    return (
        ServerExtension(
            name="client_remote",
            service_factory=assembly.build_service,
        ),
        ServerExtension(
            name="client_remote_api",
            service_factory=build_client_remote_api,
            endpoints="service",
            websockets="service",
        ),
    )
