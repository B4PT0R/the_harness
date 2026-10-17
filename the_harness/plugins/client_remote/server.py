"""Installed server runtime for private remote-client pairing and transport."""

from the_framework import ServerExtension

from .composition import RemoteClientAssembly, build_api


def build_server_extensions(context):
    options = context.plugin("client_remote")
    assembly = RemoteClientAssembly(
        context.require("machine_root"),
        context=context,
        storage_root=options.get("storage_root"),
        advertised_endpoint=options.get("advertised_endpoint"),
    )

    def build_client_remote_api(client_remote, chat):
        return build_api(
            chat.runtime, client_remote, chat.ingress, assembly.projection,
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
