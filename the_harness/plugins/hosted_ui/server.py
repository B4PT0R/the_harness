"""Construct the hosted interface in the application server."""

from pathlib import Path

from the_framework.server.clients.browser_rpc import browser_socket_path

from .api import HostedUiApi

def build_server_extensions(context):
    supervisor = context.require("supervisor")
    browser_root = context.require("browser_runtime_root")
    browser = context.require("browser_client_factory")(
        browser_socket_path(browser_root or Path(supervisor.session_path).parent)
    )
    api = HostedUiApi(
        browser,
        browser_token=context.require("browser_token"),
    )
    return api
