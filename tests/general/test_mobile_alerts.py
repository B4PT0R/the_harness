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
