"""Authenticated account endpoints; redemption always uses a simulated SDK."""

from starlette.testclient import TestClient
from the_harness import app as server
from tests.agentic.test_quota import Backend


def test_account_routes_validate_and_deduplicate(tmp_path, monkeypatch):
    backend = Backend()
    backend.credit(expires=86400)
    monkeypatch.setattr("the_harness.quota.sdk_client", lambda: backend)
    app = server.create_app(session_path=tmp_path / "session.json", token="local",
                            browser_token="browser", browser_runtime_root=tmp_path,
                            client_remote_root=tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:48887") as client:
        headers = {"Authorization": "Bearer local"}
        assert client.get("/api/v1/quota").status_code in {401, 403}
        response = client.get("/api/v1/quota", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["exhausted_policy"] == "block"
        response = client.put("/api/v1/quota/policy", headers=headers,
                              json={"exhausted_policy": "consume_earliest"})
        assert response.status_code == 200, response.text
        assert response.json()["exhausted_policy"] == "consume_earliest"
        assert client.put("/api/v1/quota/policy", headers=headers,
                          json={"exhausted_policy": "invalid"}).status_code in {400, 422}
        assert client.post("/api/v1/quota/consume", json={"credit_id": "a"}).status_code in {401, 403}
        for _ in range(2):
            response = client.post("/api/v1/quota/consume", headers=headers, json={"credit_id": "a"})
            assert response.status_code == 200, response.text
            assert response.json()["operation"]["status"] == "confirmed"
        assert len(backend.calls) == 1


def test_existing_mobile_pairing_can_manage_quota_but_not_network(tmp_path, monkeypatch):
    backend = Backend()
    backend.credit(expires=86400)
    monkeypatch.setattr("the_harness.quota.sdk_client", lambda: backend)
    app = server.create_app(session_path=tmp_path / "session.json", token="local",
                            browser_token="browser", browser_runtime_root=tmp_path,
                            client_remote_root=tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:48887") as client:
        remote = app.state.application.default_session.extensions["client_remote_api"].service.service
        remote.network.endpoint = "https://computer.example.ts.net"
        device, token = remote.clients.issue("phone", platform="android")
        # Existing pairings carry no quota-specific scope; no re-pairing required.
        assert "quota:write" not in device["scopes"]
        phone = {"Host": "computer.example.ts.net", "Origin": remote.network.endpoint,
                 "Cookie": "harness_mobile=" + token}
        assert client.get("/api/v1/quota", headers=phone).status_code == 200
        assert client.get("/api/v1/config", headers=phone).status_code == 200
        assert client.get("/api/v1/client-remote/network", headers=phone).status_code in {401, 403}
        assert client.put("/api/v1/quota/policy", headers=phone,
                          json={"exhausted_policy": "consume_earliest"}).status_code == 200
        assert client.post("/api/v1/quota/consume", headers={**phone, "Origin": "https://evil.example"},
                           json={"credit_id": "a"}).status_code == 403
        assert client.post("/api/v1/quota/consume", headers=phone,
                           json={"credit_id": "missing"}).status_code == 409
        for _ in range(2):
            response = client.post("/api/v1/quota/consume", headers=phone, json={"credit_id": "a"})
            assert response.status_code == 200, response.text
            assert response.json()["operation"]["status"] == "confirmed"
        assert len(backend.calls) == 1
        remote.clients.revoke(device["id"])
        assert client.get("/api/v1/quota", headers=phone).status_code == 401
        assert client.post("/api/v1/quota/consume", headers=phone,
                           json={"credit_id": "a"}).status_code == 401
