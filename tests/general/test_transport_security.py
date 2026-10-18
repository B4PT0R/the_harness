"""HTTP and socket transports enforce the same application security boundary."""

import asyncio
import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from the_framework.server.api.websockets import WebSocketEndpoint, WebSocketRegistry
from the_framework.server.runtime.supervisor import WorkerSupervisor
from the_harness.app import create_app
from the_harness.security import HarnessSecurityPolicy, local_request_allowed


def connection(*, host="127.0.0.1:48887", origin=None, scheme="http", headers=()):
    values = [("host", host), *headers]
    if origin is not None:
        values.append(("origin", origin))
    scope = {"type": "websocket" if scheme in {"ws", "wss"} else "http",
             "scheme": scheme, "path": "/", "query_string": b"",
             "headers": [(key.encode(), value.encode()) for key, value in values]}
    return WebSocket(scope, None, None) if scope["type"] == "websocket" else Request(scope)


@pytest.mark.parametrize("host", [
    "evil.example:48887", "evil@localhost:48887", "localhost:48887/path",
    "localhost:48887?x=1", "localhost:48887#fragment", "localhost:bad",
    "localhost:65536", "[::1", "localhost:48887,evil.example", "",
])
def test_malformed_and_foreign_hosts_fail_closed(host):
    assert not local_request_allowed(connection(host=host))


@pytest.mark.parametrize("scheme,origin", [
    ("http", "http://[::1]:48887"), ("https", "https://[::1]:48887"),
    ("ws", "http://[::1]:48887"), ("wss", "https://[::1]:48887"),
])
def test_http_and_socket_origins_use_the_same_authority(scheme, origin):
    assert local_request_allowed(connection(host="[::1]:48887", scheme=scheme, origin=origin))
    assert not local_request_allowed(connection(host="[::1]:48887", scheme=scheme, origin=origin + "0"))
    assert not local_request_allowed(connection(host="[::1]:48887", scheme=scheme, origin="null"))


@pytest.mark.parametrize("header,value", [("host", "localhost:48887"), ("origin", "https://evil.example")])
def test_ambiguous_host_and_origin_headers_are_rejected(header, value):
    request = connection(origin="http://127.0.0.1:48887", headers=[(header, value)])
    assert not local_request_allowed(request)


@pytest.mark.parametrize("token,browser_token", [("", "browser"), ("local", "")])
def test_empty_credentials_cannot_create_a_policy(token, browser_token):
    with pytest.raises(ValueError, match="session tokens"):
        HarnessSecurityPolicy(token=token, browser_token=browser_token, remote_clients=lambda: None)


def test_socket_credentials_protocols_and_native_origins():
    security = HarnessSecurityPolicy(token="local", browser_token="browser", remote_clients=lambda: None,
                                     allowed_origins=("capacitor://localhost",))
    handshake = security.socket_handshake(supported=("events",))

    def accepted(protocols="events", cookie=None, origin="http://127.0.0.1:48887", **kwargs):
        headers = [("sec-websocket-protocol", protocols)]
        if cookie:
            headers.append(("cookie", "harness_session=" + cookie))
        return handshake(connection(scheme="ws", origin=origin, headers=headers, **kwargs))

    assert accepted(cookie="browser") == {"subprotocol": "events"}
    assert accepted("events, local") == {"subprotocol": "events"}
    assert accepted("events, local", origin=None) == {"subprotocol": "events"}
    assert accepted("events, local", origin="capacitor://localhost") == {"subprotocol": "events"}
    assert accepted(cookie="browser", origin="capacitor://localhost") is None
    assert accepted("events, wrong") is None
    assert accepted("local, events") is None
    assert accepted("unknown, local") is None
    assert accepted("events, local", origin="https://evil.example") is None
    assert accepted("events, local", host="evil.example:48887") is None


@pytest.fixture
def assembled(tmp_path):
    app = create_app(WorkerSupervisor(tmp_path / "session.json"), token="local", browser_token="browser",
                     browser_runtime_root=tmp_path, client_remote_root=tmp_path)
    remote = app.state.application.default_session.extensions["client_remote_api"].service
    with TestClient(app, base_url="http://127.0.0.1:48887") as client:
        yield client, remote


def test_http_pairing_scopes_and_revocation_use_framework_declarations(assembled):
    client, remote = assembled
    local = {"Authorization": "Bearer local"}
    browser = {"Cookie": "harness_session=browser"}
    private = "/api/v1/client-remote"
    assert client.get(private).status_code == 401
    assert client.get(private, headers=local).status_code == 200
    assert client.get(private, headers=browser).status_code == 200
    assert client.get("/ui/", headers={"Authorization": "Bearer wrong"}).status_code == 401
    for credential in (local, browser):
        assert client.get(private, headers={**credential, "Origin": "https://evil.example"}).status_code == 403
        assert client.get(private, headers={**credential, "Host": "evil.example"}).status_code == 403
        assert client.options(private, headers={**credential, "Origin": "capacitor://localhost",
                                               "Access-Control-Request-Method": "GET"}).status_code == 403
    assert client.get("/remote/v1/state").status_code == 401
    assert client.get("/remote/v1/state", headers=local).status_code == 401
    assert client.get("/ui/bootstrap").status_code == 401  # Public route, but no valid ticket.

    # Pairing is a public single-use secret exchange, not a middleware exception
    # granting unauthenticated access to the rest of the remote API.
    pairing = client.post("/api/v1/client-remote/pairings", headers=local, json={}).json()
    claim = {"version": pairing["version"], "pairing_id": pairing["pairing_id"], "secret": pairing["secret"],
             "device_name": "phone", "platform": "android"}
    issued = client.post("/remote/v1/pairings/claim", json=claim)
    assert issued.status_code == 200
    assert client.post("/remote/v1/pairings/claim", json=claim).status_code == 422
    issued = issued.json()
    phone = {"Authorization": "Bearer " + issued["access_token"]}
    assert client.get("/remote/v1/state", headers=phone).json() == {}
    assert client.get(private, headers=phone).status_code == 401

    desktop, token = remote.service.clients.issue("laptop", platform="desktop")
    desktop_headers = {"Authorization": "Bearer " + token}
    assert client.get(private, headers=desktop_headers).status_code == 200
    assert client.get("/ui/", headers=desktop_headers).status_code == 401
    assert client.post("/api/v1/client-remote/pairings", headers=phone, json={}).status_code == 401
    assert client.delete("/api/v1/client-remote/clients/" + desktop["id"], headers=local).status_code == 200
    assert client.get(private, headers=desktop_headers).status_code == 401
    assert client.get("/remote/v1/state", headers=desktop_headers).status_code == 401


def test_websocket_registry_rejects_invalid_local_and_remote_handshakes(assembled):
    _client, remote = assembled
    issued, token = remote.service.clients.issue("phone")
    security = HarnessSecurityPolicy(token="local", browser_token="browser", remote_clients=lambda: None)
    app = FastAPI()

    async def echo(socket, connection):
        await socket.accept(subprotocol=connection["subprotocol"])
        await socket.send_json({"accepted": True})

    registry = WebSocketRegistry(app)
    registry.add(WebSocketEndpoint(path="/local", handler=echo,
                                  handshake=security.socket_handshake(supported=("events",))))
    registry.add(WebSocketEndpoint(path="/remote", handler=echo, handshake=remote.event_handshake))
    registry.install()
    client = TestClient(app, base_url="http://127.0.0.1:48887")
    origin = {"Host": "127.0.0.1:48887", "Origin": "http://127.0.0.1:48887"}
    protocols = ["the-harness-remote-v1", token]
    for path, selected in (("/local", ["events", "local"]), ("/remote", protocols)):
        with client.websocket_connect(path, subprotocols=selected, headers=dict(origin)) as socket:
            assert socket.accepted_subprotocol == selected[0]
            assert socket.receive_json() == {"accepted": True}
        for headers in ({"Origin": "https://evil.example"}, {**origin, "Host": "evil.example"}):
            with pytest.raises(WebSocketDisconnect) as denied:
                with client.websocket_connect(path, subprotocols=selected, headers=dict(headers)):
                    pytest.fail("Untrusted socket was accepted")
            assert denied.value.code == 1008
    for path, selected in (("/local", ["events", "wrong"]), ("/remote", [protocols[0], "wrong"]),
                           ("/remote", [*protocols, "extra"])):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(path, subprotocols=selected, headers=dict(origin)):
                pytest.fail("Invalid credentials were accepted")
    asyncio.run(remote.service.revoke_client(issued["id"]))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/remote", subprotocols=protocols, headers=dict(origin)):
            pytest.fail("Revoked token was accepted")


def test_preview_ticket_crosses_the_http_boundary_without_granting_desktop_authority(tmp_path):
    app = create_app(WorkerSupervisor(tmp_path / 'session.json'), token='control', browser_token='principal',
                     browser_runtime_root=tmp_path, client_remote_root=tmp_path,
                     origin='http://127.0.0.1:48887')
    artifact = tmp_path / 'bundle'
    artifact.mkdir()
    (artifact / 'index.html').write_text('<html><head></head><body>Preview</body></html>')
    app.state.application.surface_service.bootstrap('main', artifact)
    client = TestClient(app, base_url='http://127.0.0.1:48887')
    client.headers['authorization'] = 'Bearer control'
    link = client.post('/api/v1/surfaces/main/preview')
    assert link.status_code == 200, link.text
    client.headers.clear()
    opened = client.get(link.json()['url'])
    assert opened.status_code == 200, opened.text
    assert 'framework-client-role' in opened.text
    assert client.get('/api/v1/surfaces').status_code == 200
    assert client.get('/ui/').status_code in {401, 403}
    for method, path, payload in (
        ('POST', '/api/v1/agent/prompt', {'prompt': 'Must not reach the worker'}),
        ('PATCH', '/api/v1/config', {'model': 'Must not persist'}),
        ('POST', '/api/v1/surfaces/main/publish', {}),
        ('POST', '/api/v1/ui/open', {}),
    ):
        assert client.request(method, path, json=payload).status_code in {401, 403}
    origin = {'origin': 'http://127.0.0.1:48887'}
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('ws://127.0.0.1:48887/api/v1/application', headers=dict(origin), subprotocols=['the-harness-application']):
            pytest.fail('preview acquired the principal bridge')
    with client.websocket_connect('ws://127.0.0.1:48887/api/v1/events', headers=dict(origin), subprotocols=['the-harness']):
        assert app.state.application.default_session.extensions['canonical_transport'].service.primary_event_connection_count == 0
