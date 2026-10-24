"""Private opt-in, native-cookie isolation and mobile route confinement."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from the_harness.plugins.client_remote.network import PrivateNetwork
from the_harness.plugins.client_remote.policy import BASE_REMOTE_POLICY, mobile_api_allowed
from the_harness.security import HarnessSecurityPolicy, private_request_allowed
from tests.general.test_transport_security import connection, assembled
from starlette.websockets import WebSocketDisconnect

ENDPOINT = "https://computer.example.ts.net"


@pytest.mark.parametrize("host,origin,allowed", [
    ("computer.example.ts.net", None, True),
    ("computer.example.ts.net", ENDPOINT, True),
    ("computer.example.ts.net", "https://evil.example", False),
    ("other.example.ts.net", None, False),
    ("computer.example.ts.net:444", ENDPOINT, False),
    ("computer.example.ts.net.evil.test", None, False),
])
def test_exact_private_origin(host, origin, allowed):
    assert private_request_allowed(connection(host=host, origin=origin), ENDPOINT) is allowed
    assert not private_request_allowed(connection(host=host, origin=origin), None)


def test_mobile_cookie_never_grants_local_or_desktop_credentials():
    clients = {"phone": {"id": "phone", "scopes": BASE_REMOTE_POLICY.scopes_for("android")},
               "desktop": {"id": "desktop", "scopes": ["full_ui"]}}
    service = SimpleNamespace(network=SimpleNamespace(endpoint=ENDPOINT), authenticate=clients.get)
    policy = HarnessSecurityPolicy(token="local", browser_token="browser", remote_clients=lambda: service)
    async def run():
        def request(cookie):
            return connection(host="computer.example.ts.net", headers=[("cookie", cookie)])
        for cookie in ("harness_session=browser", "harness_mobile=desktop", "harness_mobile=local"):
            assert await policy.authenticate(request(cookie)) is None
        phone = await policy.authenticate(request("harness_mobile=phone"))
        assert phone.id == "remote:phone" and "*" not in phone.scopes
        req = request("harness_mobile=phone"); req.scope.update(method="GET", path="/api/v1/config")
        assert policy.http_access_allowed(phone, req)
        req = request("harness_mobile=phone"); req.scope.update(method="GET", path="/ui/")
        assert policy.http_access_allowed(phone, req)
        assert await policy.authenticate(connection(host="computer.example.ts.net", headers=[("authorization", "Bearer local")])) is None
    asyncio.run(run())


@pytest.mark.parametrize("method,path", [
    ("GET", "/ui/"), ("GET", "/ui/assets/app.js"), ("GET", "/api/v1/session"),
    ("GET", "/api/v1/bucket/image.png"), ("POST", "/api/v1/agent/prompt"),
    ("POST", "/api/v1/agent/attachments"), ("POST", "/api/v1/realtime/calls"),
])
def test_mobile_conversation_routes(method, path):
    assert mobile_api_allowed(method, path)


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/v1/client-remote/pairings"), ("PUT", "/api/v1/client-remote/network"),
    ("POST", "/api/v1/local-files/open"), ("POST", "/api/v1/server/restart"),
    ("GET", "/ui/bootstrap"), ("GET", "/ui/assets/../../secret"),
    ("GET", "/api/v1/bucket/../session.json"), ("POST", "/api/v1/bucket/file"),
])
def test_mobile_cannot_administer_or_read_host(method, path):
    assert not mobile_api_allowed(method, path)


def configure_tailscale(monkeypatch, *, serve=None):
    from the_harness.plugins.client_remote import network
    calls = []
    current = serve or {}
    monkeypatch.setattr(network.tailscale, "read_status", lambda: {"BackendState": "Running", "Self": {"Online": True, "DNSName": "computer.example.ts.net."}})
    monkeypatch.setattr(network.tailscale, "read_serve_status", lambda: current)
    def enable(port):
        calls.append(port)
        current.update(Web={"computer.example.ts.net:443": {"Handlers": {"/": {"Proxy": f"http://127.0.0.1:{port}"}}}})
        return ENDPOINT
    monkeypatch.setattr(network.tailscale, "configure_serve", enable)
    return calls


def test_no_network_effect_until_explicit_enable_and_persistent_disable(tmp_path, monkeypatch):
    calls = configure_tailscale(monkeypatch)
    network = PrivateNetwork(tmp_path, "http://127.0.0.1:48887")
    network.start(); network.status()
    assert not calls and network.endpoint is None and not network.path.exists()
    assert network.set_enabled(True)["enabled"]
    assert calls == [48887] and network.endpoint == ENDPOINT
    restarted = PrivateNetwork(tmp_path, "http://127.0.0.1:48887"); restarted.start()
    assert restarted.endpoint == ENDPOINT and calls == [48887]
    assert not network.set_enabled(False)["enabled"]
    assert json.loads(network.path.read_text()) == {"enabled": False, "port": 48887}
    disabled = PrivateNetwork(tmp_path, "http://127.0.0.1:48887"); disabled.start()
    assert disabled.endpoint is None and calls == [48887]


def test_never_overwrite_another_proxy_or_accept_funnel(tmp_path, monkeypatch):
    existing = {"Web": {"computer.example.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:9999"}}}}}
    calls = configure_tailscale(monkeypatch, serve=existing)
    network = PrivateNetwork(tmp_path, "http://127.0.0.1:48887")
    with pytest.raises(RuntimeError): network.set_enabled(True)
    assert calls == [] and network.endpoint is None
    existing["AllowFunnel"] = {"computer.example.ts.net:443": True}
    with pytest.raises(RuntimeError, match="Funnel"): network.set_enabled(True)


def test_restart_refuses_funnel(tmp_path, monkeypatch):
    configure_tailscale(monkeypatch, serve={"AllowFunnel": {"computer.example.ts.net:443": True}})
    (tmp_path / "remote-access.json").write_text('{"enabled":true,"port":48887}')
    network = PrivateNetwork(tmp_path, "http://127.0.0.1:48887")
    network.start()
    assert network.endpoint is None and "Funnel" in network.error



def test_private_cookie_routes_and_live_revocation(assembled):
    client, remote = assembled
    service = remote.service
    service.network.endpoint = ENDPOINT  # Test-only: no system network configuration.
    device, token = service.clients.issue("phone", platform="android")
    phone = {"Host": "computer.example.ts.net", "Origin": ENDPOINT, "Cookie": "harness_mobile=" + token}
    assert client.get("/api/v1/plugins", headers=phone).status_code == 200
    assert client.get("/api/v1/config", headers=phone).status_code == 200
    for path in ("/api/v1/client-remote/network", "/ui/bootstrap"):
        assert client.get(path, headers=phone).status_code in (401, 403)
    assert client.get("/api/v1/plugins", headers={**phone, "Origin": "https://evil.example"}).status_code == 403
    with client.websocket_connect("/remote/v1/ui-events", headers=phone, subprotocols=["the-harness"]) as socket:
        assert client.delete("/api/v1/client-remote/clients/" + device["id"], headers={"Authorization": "Bearer local"}).status_code == 200
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    assert client.get("/api/v1/plugins", headers=phone).status_code == 401


def test_network_preview_can_read_but_not_configure(tmp_path, monkeypatch):
    from the_framework.server.api.endpoints import HttpError, Principal
    from the_harness.plugins.client_remote.api import ClientRemoteApi

    configure_tailscale(monkeypatch)
    network = PrivateNetwork(tmp_path, "http://127.0.0.1:48887")
    api = ClientRemoteApi(SimpleNamespace(runtime=None, network=network), None)
    preview = SimpleNamespace(principal=Principal(
        id="surface-preview", scopes=frozenset({"*:read"}),
        attributes={"client_role": "preview"}))
    assert asyncio.run(api.network_status(preview))["enabled"] is False
    with pytest.raises(HttpError):
        asyncio.run(api.configure_network(preview, True))
    assert not network.path.exists()


@pytest.mark.parametrize("platform", ["android", "desktop"])
def test_paired_clients_share_settings_but_never_local_administration(assembled, platform):
    client, remote = assembled
    remote.service.network.endpoint = ENDPOINT
    device, token = remote.service.clients.issue("device", platform=platform)
    headers = {"Host": "computer.example.ts.net", "Origin": ENDPOINT,
               "Authorization": "Bearer " + token}
    local = {"Authorization": "Bearer local"}
    context = "/api/v1/client-remote/context"
    assert client.get(context, headers=headers).json() == {"local_ui": False}
    assert client.get(context, headers=local).json() == {"local_ui": True}
    assert client.get(context).status_code == 401
    config = "/api/v1/config"
    assert client.get(config, headers=headers).status_code == 200
    updated = client.patch(config, headers=headers, json={"instructions": "Shared fixture settings"})
    assert updated.status_code == 200, updated.text
    assert client.get(config, headers=local).json()["config"]["instructions"] == "Shared fixture settings"
    quota = client.put("/api/v1/quota/policy", headers=headers, json={"exhausted_policy": "block"})
    assert quota.status_code == 200, quota.text
    # A nonexistent plugin proves routing + scope checks passed without changing bindings.
    binding = client.put("/api/v1/plugins/nonexistent/binding", headers=headers, json={"enabled": True})
    assert binding.status_code == 404
    for method, path, body in [
        ("GET", "/api/v1/client-remote/network", None),
        ("PUT", "/api/v1/client-remote/network", {"enabled": True}),
        ("POST", "/api/v1/client-remote/pairings", {}),
        ("DELETE", "/api/v1/client-remote/clients/" + device["id"], None),
        ("GET", "/api/v1/local-files/settings", None),
        ("POST", "/api/v1/local-files/open", {"path": "/tmp/private"}),
        ("POST", "/api/v1/server/restart", {}),
    ]:
        assert client.request(method, path, headers=headers, json=body).status_code in (401, 403)
    assert remote.service.clients.authenticate(token) is not None


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/config"), ("PATCH", "/api/v1/config"),
    ("GET", "/api/v1/client-remote/context"), ("PUT", "/api/v1/quota/policy"),
    ("PUT", "/api/v1/plugins/memory/binding"),
    ("DELETE", "/api/v1/session"), ("DELETE", "/api/v1/memory"), ("DELETE", "/api/v1/registry"),
])
def test_shared_settings_allowlist(method, path):
    from the_harness.plugins.client_remote.policy import RemoteDesktopAccess
    assert mobile_api_allowed(method, path)
    assert RemoteDesktopAccess().allowed(method, path)


@pytest.mark.parametrize("path", [
    "/api/v1/plugins/../binding", "/api/v1/plugins//binding",
    "/api/v1/plugins/memory/runtime", "/api/v1/plugins/memory/binding/extra",
])
def test_shared_settings_do_not_admit_other_plugin_operations(path):
    from the_harness.plugins.client_remote.policy import RemoteDesktopAccess
    assert not mobile_api_allowed("PUT", path)
    assert not RemoteDesktopAccess().allowed("PUT", path)
