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
        assert not policy.http_access_allowed(phone, req)
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
    ("DELETE", "/api/v1/session"), ("GET", "/api/v1/config"), ("PATCH", "/api/v1/config"),
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
    for path in ("/api/v1/config", "/api/v1/client-remote/network", "/ui/bootstrap"):
        assert client.get(path, headers=phone).status_code in (401, 403)
    assert client.get("/api/v1/plugins", headers={**phone, "Origin": "https://evil.example"}).status_code == 403
    with client.websocket_connect("/remote/v1/ui-events", headers=phone, subprotocols=["the-harness"]) as socket:
        assert client.delete("/api/v1/client-remote/clients/" + device["id"], headers={"Authorization": "Bearer local"}).status_code == 200
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    assert client.get("/api/v1/plugins", headers=phone).status_code == 401
