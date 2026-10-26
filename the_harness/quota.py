"""Account-owned quota policy and explicitly journalled reset redemption.

All SDK I/O is serialized off the event loop. An uncertain POST is never retried,
not even after restart; only an observed redeemed credit reconciles its receipt.
"""

import asyncio
import time
from copy import deepcopy
from datetime import datetime
from uuid import uuid4

from the_framework.agent.models.usage import usage_window
from the_framework.server import endpoint
from the_framework.server.api.endpoints import HttpError
from the_framework.utils.persistence import MappingStore


def timestamp(value):
    if not value:
        return None
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("credit expiry must include a timezone")
    return date.timestamp()


def sdk_client():
    from codex_backend_sdk import OpenAI

    # The transport must not retry mutations behind the redemption journal.
    return OpenAI(timeout=15, max_retries=0).authenticate(interactive=False)


class QuotaService:
    def __init__(self, path, *, client_factory=None, clock=time.time, poll_interval=60):
        self.store = MappingStore(path)
        self.client_factory, self.clock = client_factory or sdk_client, clock
        self.poll_interval = poll_interval
        self.state = {"exhausted_policy": "block", "operations": {}}
        self.lock = asyncio.Lock()
        self.task = None
        self.client = None
        self.windows = {"quota_5h": None, "quota_7d": None}
        self.credits = []
        self.updated_at = None
        self.error = None
        self.persistence_error = None

    async def start(self):
        if self.task is not None:
            return
        try:
            saved = await asyncio.to_thread(self.store.load)
            if saved:
                if saved.get("exhausted_policy") not in {"block", "consume_earliest"} or not isinstance(saved.get("operations"), dict):
                    raise ValueError("invalid quota policy document")
                for operation in saved["operations"].values():
                    if (not isinstance(operation, dict)
                            or operation.get("status") not in {"pending", "unknown", "confirmed", "rejected"}
                            or not isinstance(operation.get("request_id"), str)
                            or not isinstance(operation.get("started_at"), (float, int))):
                        raise ValueError("invalid reset receipt")
                self.state = saved
        except Exception:
            self.persistence_error = "quota_state_unreadable"
        self.task = asyncio.create_task(self._run(), name="account-quota")

    async def stop(self):
        if self.task is not None:
            # Wait for a possible SDK mutation to settle before shutting down.
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        async with self.lock:
            if self.client is not None:
                await asyncio.to_thread(self.client.close)
                self.client = None

    def health(self):
        return {"status": "degraded" if self.error or self.persistence_error else "ok",
                "error": self.persistence_error or self.error,
                "updated_at": self.updated_at}

    async def _io(self, call):
        # Cancellation must not release the lock while a requests thread still
        # mutates the account. Always drain it before propagating cancellation.
        task = asyncio.create_task(asyncio.to_thread(call))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await asyncio.gather(task, return_exceptions=True)
            raise

    async def _save(self, state):
        try:
            await self._io(lambda: self.store.save(state))
        except BaseException:
            self.persistence_error = "quota_persistence_failed"
            raise
        self.state = state

    def exhausted(self):
        return any(window is not None and window["used_percent"] >= 100
                   for window in self.windows.values())

    def available(self):
        now = self.clock()
        return sorted((credit for credit in self.credits
                       if credit.get("status") == "available"
                       and credit.get("reset_type") == "codex_rate_limits"
                       and (timestamp(credit.get("expires_at")) is None
                            or timestamp(credit["expires_at"]) > now)),
                      key=lambda credit: (timestamp(credit.get("expires_at")) or float("inf"), credit["id"]))

    def uncertain(self):
        return any(operation["status"] in {"pending", "unknown"}
                   for operation in self.state["operations"].values())

    def snapshot(self):
        return deepcopy({**self.windows, "updated_at": self.updated_at,
                         "error": self.persistence_error or self.error,
                         "credits": self.credits,
                         "exhausted_policy": self.state["exhausted_policy"],
                         "auto_expiry_seconds": 3600,
                         "exhausted": self.exhausted(),
                         "operations": self.state["operations"]})

    def context(self):
        """Read-only, compact view of the already-polled account usage."""
        available = self.updated_at is not None and self.windows["quota_7d"] is not None
        status = "unavailable"
        if available:
            status = "stale" if (self.error or self.persistence_error
                                 or self.clock() - self.updated_at > 2 * self.poll_interval) else "ready"
        return deepcopy({"status": status, "quota_7d": self.windows["quota_7d"],
                         "updated_at": self.updated_at, "error": self.persistence_error or self.error})

    async def policy(self, value):
        if value not in {"block", "consume_earliest"}:
            raise ValueError("invalid exhausted quota policy")
        async with self.lock:
            if self.persistence_error:
                raise RuntimeError(self.persistence_error)
            state = deepcopy(self.state)
            state["exhausted_policy"] = value
            await self._save(state)
            return self.snapshot()

    async def _refresh(self):
        if self.persistence_error:
            raise RuntimeError(self.persistence_error)
        if self.client is None:
            self.client = await self._io(self.client_factory)
        account = self.client.account_info().get("account_id")
        if not account or self.state.get("account_id", account) != account:
            raise RuntimeError("quota_account_changed")
        usage = await self._io(self.client.codex.usage)
        windows = {
            key: usage_window(usage, duration_seconds=duration, fallback=fallback)
            for key, duration, fallback in (("quota_5h", 18000, "primary_window"),
                                            ("quota_7d", 604800, "secondary_window"))
        }
        # Quota admission must still work if only the credits endpoint fails.
        self.windows = {key: dict(window) if window is not None else None for key, window in windows.items()}
        credits = await self._io(self.client.codex.rate_limit_reset_credits.list)
        rows = [row.model_dump() for row in credits.credits]
        for row in rows:
            timestamp(row.get("expires_at"))  # Reject ambiguous backend clocks.
        state = deepcopy(self.state)
        state["account_id"] = account
        by_id = {row["id"]: row for row in rows}
        for credit_id, operation in state["operations"].items():
            row = by_id.get(credit_id)
            if operation["status"] in {"pending", "unknown"} and row and row["status"] in {"consumed", "redeemed"}:
                operation["status"] = "confirmed"
                state["awaiting_recovery"] = True
        if (any(window is not None for window in windows.values())
                and not any(window is not None and window.used_percent >= 100 for window in windows.values())):
            state.pop("awaiting_recovery", None)
        if state != self.state:
            await self._save(state)
        self.windows = {key: dict(window) if window is not None else None for key, window in windows.items()}
        self.credits, self.updated_at, self.error = rows, self.clock(), None

    async def refresh(self, *, force=False):
        async with self.lock:
            if not force and self.updated_at is not None and self.clock() - self.updated_at < 30:
                return self.snapshot()
            try:
                await self._refresh()
            except Exception as error:
                self.error = "quota_account_changed" if str(error) == "quota_account_changed" else "quota_backend_unavailable"
            return self.snapshot()

    async def _consume(self, credit_id, reason):
        if self.persistence_error or self.uncertain():
            raise RuntimeError(self.persistence_error or "reset_result_uncertain")
        if credit_id in self.state["operations"]:
            return deepcopy(self.state["operations"][credit_id])
        if credit_id not in {credit["id"] for credit in self.available()}:
            raise ValueError("reset_not_available")
        state = deepcopy(self.state)
        operation = {"request_id": str(uuid4()), "reason": reason, "status": "pending",
                     "started_at": self.clock()}
        state["operations"][credit_id] = operation
        await self._save(state)  # Durable intent BEFORE any external mutation.
        try:
            response = await self._io(lambda: self.client.codex.rate_limit_reset_credits.consume(
                redeem_request_id=operation["request_id"], credit_id=credit_id))
        except BaseException:
            state = deepcopy(self.state)
            state["operations"][credit_id]["status"] = "unknown"
            await self._save(state)
            raise
        state = deepcopy(self.state)
        operation = state["operations"][credit_id]
        operation.update(status="confirmed" if response.code == "reset" else "rejected",
                         code=response.code, windows_reset=response.windows_reset)
        if response.code == "reset":
            # Do not spend a second reset while exhausted usage is still stale.
            state["awaiting_recovery"] = True
        await self._save(state)
        return deepcopy(operation)

    async def consume(self, credit_id):
        async with self.lock:
            await self._refresh()
            result = await self._consume(credit_id, "manual")
            try:
                await self._refresh()
            except Exception:
                self.error = "quota_backend_unavailable"
            return {"operation": result, **self.snapshot()}

    async def maintain(self):
        async with self.lock:
            await self._refresh()
            if self.persistence_error or self.uncertain():
                return
            candidates = [credit for credit in self.available() if credit["id"] not in self.state["operations"]]
            if not candidates:
                return
            # At most ONE redemption per maintenance interval; a result receipt
            # also enforces a cooldown when UI/gate probes run concurrently.
            if any(self.clock() - operation["started_at"] < self.poll_interval
                   for operation in self.state["operations"].values()):
                return
            imminent = next((credit for credit in candidates
                             if credit.get("expires_at") and 0 < timestamp(credit["expires_at"]) - self.clock() < 3600), None)
            if imminent:
                await self._consume(imminent["id"], "expiring")
            elif (self.exhausted() and self.state["exhausted_policy"] == "consume_earliest"
                  and not self.state.get("awaiting_recovery")):
                await self._consume(candidates[0]["id"], "exhausted")

    async def admission(self):
        # Read only: the independent maintenance loop owns automatic redemptions.
        snapshot = await self.refresh()
        known_exhausted = snapshot["exhausted"]
        return {"allowed": not known_exhausted, "reason": "quota_exhausted" if known_exhausted else None,
                "error": snapshot["error"]}

    @endpoint("get", "/api/v1/quota", authorization={"scope": "agent:read"},
              response={"type": "object"})
    async def read_quota(self):
        return await self.refresh()

    @endpoint("put", "/api/v1/quota/policy", authorization={"scope": "config:write"},
              request={"type": "object", "properties": {"exhausted_policy": {
                  "enum": ["block", "consume_earliest"]}},
                  "required": ["exhausted_policy"], "additionalProperties": False},
              response={"type": "object"})
    async def change_policy(self, exhausted_policy):
        try:
            return await self.policy(exhausted_policy)
        except RuntimeError as error:
            raise HttpError(503, "quota_state_unavailable", "Quota policy is unavailable") from error

    @endpoint("post", "/api/v1/quota/consume", authorization={"scope": "quota:write"},
              request={"type": "object", "properties": {"credit_id": {"type": "string", "minLength": 1}},
                       "required": ["credit_id"], "additionalProperties": False},
              response={"type": "object"})
    async def redeem(self, credit_id):
        try:
            return await self.consume(credit_id)
        except ValueError as error:
            raise HttpError(409, "reset_not_available", "This reset is no longer available") from error
        except Exception as error:
            raise HttpError(503, "reset_unconfirmed", "Reset could not be confirmed; inspect its receipt before trying another") from error

    async def _run(self):
        while True:
            try:
                await self.maintain()
            except Exception:
                self.error = "quota_backend_unavailable"
            await asyncio.sleep(self.poll_interval)


def build_service(context):
    return QuotaService(context.require("data_root") / "quota.json")


def build_bridge(runtime, quota):
    async def handle(method, payload):
        if method == "context":
            return quota.context()
        if method == "admission":
            return await quota.admission()
        raise ValueError("unsupported quota capability")

    runtime.bridge.register("quota", handle)
    return handle
