import asyncio
from types import SimpleNamespace

import pytest
from the_framework.plugins.scheduler.service import SchedulerService
from the_framework.plugins.scheduler.waits import date, stamp
from the_framework.server.api.endpoints import HttpError, Principal
from the_harness.plugins.client_remote.api import ClientRemoteApi
from the_harness.plugins.client_remote.policy import mobile_api_allowed

NOW = date("2026-10-20T10:00:00+02:00")


def call(scopes=("mobile",), client_id="phone"):
    return SimpleNamespace(principal=Principal(id="remote:phone", attributes={"client": {"id": client_id, "scopes": scopes}}))


def test_native_routes_are_narrowly_allowed():
    assert mobile_api_allowed("GET", "/remote/v1/alerts")
    assert mobile_api_allowed("POST", "/remote/v1/alerts/receipt")
    assert mobile_api_allowed("GET", "/remote/v1/notifications/wait")
    assert not mobile_api_allowed("POST", "/remote/v1/alerts")
    assert not mobile_api_allowed("GET", "/remote/v1/alerts/receipt")
    assert not mobile_api_allowed("POST", "/remote/v1/alerts/../commands")
    assert not mobile_api_allowed("GET", "/api/v1/config")


def test_device_identity_and_wait_context_stay_server_side(tmp_path, monkeypatch):
    async def run():
        monkeypatch.setattr("the_framework.plugins.scheduler.service.utc_now", lambda: NOW)
        scheduler = SchedulerService(tmp_path / "scheduler.json", None)
        await scheduler.wait_call("create", {"wait_id": "one", "wait": {
            "name": "Ask", "context": "Private policy context", "timeout_seconds": 60, "response_kind": "ack",
            "alert": {"at": stamp(NOW), "title": "Check", "kind": "message"}}})
        api = ClientRemoteApi(SimpleNamespace(runtime=None), None, scheduler=scheduler)
        for denied in (call(scopes=("chat",)), SimpleNamespace(principal=Principal(id="local-bearer"))):
            with pytest.raises(HttpError):
                await api.alerts(denied)
        schedule = await api.alerts(call())
        assert len(schedule["alerts"]) == 1 and "Private policy context" not in str(schedule)
        for event in ("armed", "fired"):
            assert (await api.alert_receipt(call(), "one", event))["status"] == "waiting"
        assert (await api.alert_receipt(call(), "one", "acknowledged"))["status"] == "acknowledged"
        assert scheduler.waits.get("one")["receipts"]["phone"]["acknowledged"]
        assert list(scheduler.waits.get("one")["receipts"]) == ["phone"]
        with pytest.raises(HttpError) as unknown:
            await api.alert_receipt(call(), "not-found", "armed")
        assert unknown.value.status_code == 422
        assert (await api.alerts(call()))["alerts"][0]["cancelled"]
    asyncio.run(run())


def test_private_notification_handshake_is_native_mobile_only(tmp_path):
    from the_framework.server.clients.remote import ClientRemoteService
    from the_harness.plugins.client_remote.api import NOTIFICATION_SUBPROTOCOL
    from the_harness.plugins.client_remote.policy import BASE_REMOTE_POLICY
    remote = ClientRemoteService(SimpleNamespace(), tmp_path / "clients.json", policy=BASE_REMOTE_POLICY)
    api = ClientRemoteApi(remote, None)
    api._request_allowed = lambda socket: True
    remote.authenticate = lambda token: {"id": "phone", "scopes": ("mobile",)} if token == "secret" else None
    def socket(protocols, **query):
        return SimpleNamespace(headers={"sec-websocket-protocol": protocols}, query_params=query)
    good = NOTIFICATION_SUBPROTOCOL + ", secret"
    assert api.notification_handshake(socket(good))["after"] is None
    assert api.notification_handshake(socket(good, after="4"))["after"] == 4
    for bad in (socket(NOTIFICATION_SUBPROTOCOL), socket(NOTIFICATION_SUBPROTOCOL + ", wrong"),
                socket(good, after="-1"), socket(good, after="bad")):
        assert api.notification_handshake(bad) is None
    remote.authenticate = lambda token: {"id": "desktop", "scopes": ("desktop",)}
    assert api.notification_handshake(socket(good)) is None
    assert mobile_api_allowed("GET", "/remote/v1/notifications")
    assert not mobile_api_allowed("POST", "/remote/v1/notifications")
    api._request_allowed = lambda socket: False
    assert api.notification_handshake(socket(good)) is None


def test_private_stream_replays_and_unregisters_on_disconnect_and_revocation(tmp_path):
    from starlette.websockets import WebSocketDisconnect
    from the_framework.server.clients.remote import ClientRemoteService
    from the_harness.plugins.client_remote.api import NOTIFICATION_SUBPROTOCOL

    async def run():
        remote = ClientRemoteService(SimpleNamespace(), tmp_path / "clients.json")
        api = ClientRemoteApi(remote, None)
        class Socket:
            def __init__(self):
                self.sent = asyncio.Queue()
                self.incoming = asyncio.Queue()
            async def accept(self, *, subprotocol):
                assert subprotocol == NOTIFICATION_SUBPROTOCOL
            async def send_json(self, payload):
                await self.sent.put(payload)
            async def receive(self):
                return await self.incoming.get()
            async def close(self, **kwargs):
                self.closed = kwargs
                await self.incoming.put({"type": "websocket.disconnect"})
        paired, _ = remote.clients.issue("lab")
        connection = {"client": paired, "after": None, "server_instance_id": None,
                      "subprotocol": NOTIFICATION_SUBPROTOCOL}
        first = Socket()
        serving = asyncio.create_task(api.serve_notifications(first, connection))
        initial = await first.sent.get()
        assert initial["status"] == "reset"
        remote._schedule_notifications("message")
        batch = await first.sent.get()
        assert batch["events"][0]["message_id"] == "message"
        await first.close(code=1000)
        await serving
        assert not remote.event_connections
        second = Socket()
        serving = asyncio.create_task(api.serve_notifications(second, {
            **connection, "after": initial["cursor"], "server_instance_id": initial["server_instance_id"]}))
        assert (await second.sent.get())["events"] == batch["events"]
        # Revocation uses the shared client socket registry, not a separate lifetime.
        await remote.revoke_client(paired["id"])
        await serving
        assert second.closed["code"] == 1008 and not remote.event_connections
        await remote.stop()
    asyncio.run(asyncio.wait_for(run(), 5))
