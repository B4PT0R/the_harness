"""Construct the hosted interface in the application server."""

from the_framework.server.clients.browser_rpc import browser_socket_path
from the_framework.server.clients.browser_rpc import BrowserRPCClient

from .api import HostedUiApi

def build_service(context):
    options = context.plugin("hosted_ui")
    browser = options.get("browser_client_factory", BrowserRPCClient)(
        browser_socket_path(context.require("machine_root"))
    )
    api = HostedUiApi(
        browser,
        browser_token=options["browser_token"],
    )
    return api
