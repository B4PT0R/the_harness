"""Readiness is a bounded lifecycle contract, not just an HTTP response."""

import asyncio
import json

import httpx
import pytest
from modict import modict

from the_harness.control import HarnessControl
from the_harness.plugins.hosted_ui.api import HostedUiApi


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("the_harness.control.time.monotonic", lambda: now[0])
    monkeypatch.setattr("the_harness.control.time.sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    return now


def unavailable(status=503):
    response = httpx.Response(status, request=httpx.Request("POST", "http://127.0.0.1/api/v1/ui/open"))
    return httpx.HTTPStatusError("not ready", request=response.request, response=response)


def test_health_waits_for_ok_not_degraded(tmp_path, monkeypatch, clock):
    control = HarnessControl(tmp_path)
    responses = iter([{"status": "degraded"}, {"status": "ok"}])
    monkeypatch.setattr(control, "request", lambda *args, **kwargs: next(responses))
    assert control.wait_until_ready(timeout=1) == {"status": "ok"}
    assert clock[0] == 0.1


def test_degraded_health_times_out(tmp_path, monkeypatch, clock):
    control = HarnessControl(tmp_path)
    monkeypatch.setattr(control, "request", lambda *args, **kwargs: {"status": "degraded"})
    with pytest.raises(RuntimeError, match="server did not become ready"):
        control.wait_until_ready(timeout=0.2)


def test_open_waits_for_browser_without_restarting_services(tmp_path, monkeypatch, clock):
    control = HarnessControl(tmp_path)
    starts, calls = [], []
    monkeypatch.setattr(control, "start", lambda: starts.append(True))

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            raise unavailable()
        return {"status": "opened"}

    monkeypatch.setattr(control, "request", request)
    assert control.open(timeout=1) == {"status": "opened"}
    assert starts == [True]
    assert len(calls) == 2
    assert calls[1][1]["timeout"] < calls[0][1]["timeout"]


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_open_does_not_retry_permanent_errors(tmp_path, monkeypatch, clock, status):
    control = HarnessControl(tmp_path)
    monkeypatch.setattr(control, "start", lambda: None)
    calls = []

    def request(*args, **kwargs):
        calls.append(args)
        raise unavailable(status)

    monkeypatch.setattr(control, "request", request)
    with pytest.raises(httpx.HTTPStatusError):
        control.open(timeout=1)
    assert len(calls) == 1


def test_open_timeout_is_bounded(tmp_path, monkeypatch, clock):
    control = HarnessControl(tmp_path)
    monkeypatch.setattr(control, "start", lambda: None)

    def request(*args, **kwargs):
        raise unavailable()

    monkeypatch.setattr(control, "request", request)
    with pytest.raises(RuntimeError, match="interface did not become ready"):
        control.open(timeout=0.2)
    assert clock[0] == pytest.approx(0.2)


def test_unpublished_ui_never_opens_a_browser_or_issues_a_ticket():
    class Browser:
        def call(self, *args):
            pytest.fail("no browser should open for an unpublished surface")

    api = HostedUiApi(Browser(), browser_token="test")
    call = modict(application=modict(surface_service=modict(active_path=lambda name: None)))
    response = asyncio.run(api.open(call))
    assert response.status_code == 503
    assert "no published release" in json.loads(response.body)["error"]
    assert api.tickets == {}


def test_web_links_use_integrated_browser_and_reject_other_schemes():
    calls = []

    class Browser:
        def call(self, *args, **kwargs):
            calls.append((args, kwargs))

    api = HostedUiApi(Browser(), browser_token="test")
    assert asyncio.run(api.open_external("https://example.org")) == {"status": "opened"}
    assert calls == [(("open_web", "https://example.org"), {"new_tab": True})]
    for url in ("file:///tmp/a", "javascript:alert(1)", "relative/path"):
        assert asyncio.run(api.open_external(url)).status_code == 422
    assert len(calls) == 1
