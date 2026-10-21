"""Account policy contracts; all backend calls are simulated, including redemption."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from codex_backend_sdk._models import RateLimitResetCredit

from the_harness.quota import QuotaService


class Backend:
    def __init__(self):
        self.now = 1_800_000_000.0
        self.percent = 20
        self.rows = []
        self.calls = []
        self.fail_read = False
        self.fail_post = False
        self.codex = SimpleNamespace(usage=self.usage, rate_limit_reset_credits=self)

    def account_info(self):
        return {"account_id": "simulated-account"}

    def close(self):
        pass

    def usage(self):
        if self.fail_read:
            raise RuntimeError("private backend detail must not escape")
        return {"rate_limit": {"secondary_window": {"used_percent": self.percent,
                                                  "limit_window_seconds": 604800,
                                                  "reset_at": int(self.now + 4000)}}}

    def credit(self, id="a", expires=1800):
        row = RateLimitResetCredit(id=id, reset_type="codex_rate_limits", status="available",
                                   granted_at="2026-01-01T00:00:00Z",
                                   expires_at=None if expires is None else datetime.fromtimestamp(self.now + expires, timezone.utc).isoformat())
        self.rows.append(row)
        return row

    def list(self):
        return SimpleNamespace(credits=self.rows)

    def consume(self, *, redeem_request_id, credit_id):
        self.calls.append((redeem_request_id, credit_id))
        if self.fail_post:
            raise TimeoutError("ambiguous response")
        next(row for row in self.rows if row.id == credit_id).status = "consumed"
        return SimpleNamespace(code="reset", windows_reset=2)


def service(tmp_path, backend):
    return QuotaService(tmp_path / "quota.json", client_factory=lambda: backend,
                        clock=lambda: backend.now, poll_interval=60)


@pytest.mark.parametrize("expires,expected", [(3599, 1), (3600, 0), (3601, 0), (0, 0), (-10, 0), (None, 0)])
def test_expiry_is_strictly_within_one_hour(tmp_path, expires, expected):
    async def run():
        backend = Backend()
        backend.credit(expires=expires)
        quota = service(tmp_path, backend)
        await quota.maintain()
        assert len(backend.calls) == expected
        if expected:
            receipt = quota.snapshot()["operations"]["a"]
            assert receipt["status"] == "confirmed"
            assert receipt["reason"] == "expiring"
    asyncio.run(run())


def test_exhaustion_default_blocks_without_spending_and_recovers(tmp_path):
    async def run():
        backend = Backend()
        backend.percent = 100
        backend.credit(expires=86400)
        quota = service(tmp_path, backend)
        await quota.maintain()
        assert not (await quota.admission())["allowed"]
        assert not backend.calls
        backend.percent = 0
        backend.now += 31
        assert (await quota.admission())["allowed"]
    asyncio.run(run())


def test_auto_exhaustion_selects_earliest_expiry_and_waits_for_fresh_usage(tmp_path):
    async def run():
        backend = Backend()
        backend.percent = 100
        backend.credit("never", None)
        backend.credit("later", 80000)
        backend.credit("soon", 70000)
        quota = service(tmp_path, backend)
        await quota.policy("consume_earliest")
        await quota.maintain()
        assert backend.calls[0][1] == "soon"
        backend.now += 120
        await quota.maintain()
        assert len(backend.calls) == 1  # stale 100% cannot burn another credit
        backend.percent = 0
        await quota.maintain()
        backend.percent = 100
        await quota.maintain()
        assert backend.calls[1][1] == "later"
    asyncio.run(run())


def test_absent_credits_and_backend_error_are_explicit_and_never_spend(tmp_path):
    async def run():
        backend = Backend()
        backend.percent = 100
        quota = service(tmp_path, backend)
        await quota.policy("consume_earliest")
        await quota.maintain()
        backend.fail_read = True
        backend.now += 31
        decision = await quota.admission()
        assert not decision["allowed"]  # don't unblock on stale exhausted data
        assert decision["error"] == "quota_backend_unavailable"
        assert not backend.calls
    asyncio.run(run())


def test_concurrent_manual_and_automatic_consumers_share_one_receipt(tmp_path):
    async def run():
        backend = Backend()
        backend.credit()
        quota = service(tmp_path, backend)
        results = await asyncio.gather(quota.consume("a"), quota.consume("a"), quota.maintain())
        assert len(backend.calls) == 1
        assert results[0]["operation"]["request_id"] == results[1]["operation"]["request_id"]
        saved = quota.store.load()
        assert saved["operations"]["a"]["request_id"] == backend.calls[0][0]
    asyncio.run(run())


def test_intent_is_durable_before_post_and_uncertain_result_never_retried(tmp_path):
    async def run():
        backend = Backend()
        backend.credit()
        backend.credit("b")
        backend.fail_post = True
        quota = service(tmp_path, backend)
        original = backend.consume
        def consume(**payload):
            saved = quota.store.load()["operations"][payload["credit_id"]]
            assert saved["status"] == "pending"
            assert saved["request_id"] == payload["redeem_request_id"]
            return original(**payload)
        backend.consume = consume
        with pytest.raises(TimeoutError):
            await quota.consume("a")
        assert quota.state["operations"]["a"]["status"] == "unknown"
        # Restart loads the same receipt. The polling task cannot retry it.
        restored = service(tmp_path, backend)
        await restored.start()
        await asyncio.sleep(0.02)
        await restored.stop()
        assert restored.uncertain()
        await restored.maintain()
        with pytest.raises(RuntimeError, match="uncertain"):
            await restored.consume("b")
        assert len(backend.calls) == 1
        backend.rows[0].status = "consumed"
        await restored.refresh(force=True)
        assert not restored.uncertain()
    asyncio.run(run())


def test_corrupt_persistence_is_not_replaced_or_used_for_redemption(tmp_path):
    async def run():
        backend = Backend()
        backend.credit()
        path = tmp_path / "quota.json"
        path.write_text("corrupt private state")
        quota = service(tmp_path, backend)
        await quota.start()
        await asyncio.sleep(0.02)
        await quota.stop()
        assert quota.snapshot()["error"] == "quota_state_unreadable"
        assert path.read_text() == "corrupt private state"
        assert not backend.calls
    asyncio.run(run())


def test_policy_persists_and_account_change_cannot_spend(tmp_path):
    async def run():
        backend = Backend()
        quota = service(tmp_path, backend)
        await quota.policy("consume_earliest")
        await quota.refresh()
        restored = service(tmp_path, backend)
        await restored.start()
        await asyncio.sleep(0.02)
        await restored.stop()
        assert restored.state["exhausted_policy"] == "consume_earliest"
        backend.credit()
        backend.account_info = lambda: {"account_id": "other-account"}
        assert (await restored.refresh(force=True))["error"] == "quota_account_changed"
        with pytest.raises(RuntimeError, match="account_changed"):
            await restored.consume("a")
        assert not backend.calls
    asyncio.run(run())


def test_cancelled_post_is_drained_and_receipt_remains_uncertain(tmp_path):
    async def run():
        import threading
        backend = Backend()
        backend.credit()
        entered, released = threading.Event(), threading.Event()
        original = backend.consume
        def consume(**payload):
            entered.set()
            released.wait(2)
            return original(**payload)
        backend.consume = consume
        quota = service(tmp_path, backend)
        task = asyncio.create_task(quota.consume("a"))
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0.01)
        assert quota.lock.locked()
        assert not task.done()
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert quota.state["operations"]["a"]["status"] == "unknown"
        await quota.refresh(force=True)
        assert quota.state["operations"]["a"]["status"] == "confirmed"
        assert len(backend.calls) == 1
    asyncio.run(run())


def test_reconciled_reset_does_not_spend_another_on_stale_exhaustion(tmp_path):
    async def run():
        backend = Backend()
        backend.percent = 100
        backend.credit("a", 80000)
        backend.credit("b", 90000)
        quota = service(tmp_path, backend)
        await quota.policy("consume_earliest")
        backend.fail_post = True
        with pytest.raises(TimeoutError):
            await quota.maintain()
        backend.rows[0].status = "consumed"
        backend.fail_post = False
        backend.now += 120
        await quota.maintain()
        assert quota.state["operations"]["a"]["status"] == "confirmed"
        assert quota.state["awaiting_recovery"]
        assert len(backend.calls) == 1
    asyncio.run(run())
