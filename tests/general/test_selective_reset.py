"""Destructive actions have distinct scopes and roll back on failed restart."""
import asyncio
from types import SimpleNamespace

import pytest

from the_harness.runtime_composition import Harness
from the_harness.runtime_reset import SESSION_RESET_ENTRIES, MEMORY_RESET_ENTRIES


class FixtureHarness(Harness):
    def __init__(self, root):
        self.supervisor = SimpleNamespace(session_path=root / "session.json")
        self.reset_transaction_factory = None
        self.reset_lock = asyncio.Lock()
        self.reset_hooks = []
        self.resetting = False
        self.ready = SimpleNamespace(session_id="fixture")
        self.fail_once = False
        self.published = []

    async def start(self):
        if self.fail_once:
            self.fail_once = False
            if not self.supervisor.session_path.exists():
                self.supervisor.session_path.write_text("failed worker output")
            raise RuntimeError("worker failed")
        return self.ready

    async def stop(self):
        pass

    async def publish(self, payload):
        self.published.append(payload)


@pytest.mark.parametrize("kind", ["session", "memory"])
@pytest.mark.parametrize("fail_start", [False, True])
def test_reset_preserves_unrelated_data_and_restores_failed_reset(tmp_path, kind, fail_start):
    paths = [
        "session.json", "session.turn-timing.json", "system-control.json",
        "session.auxiliaries/memory.jiminy/session.json",
        "session.auxiliaries/other/session.json",
        *MEMORY_RESET_ENTRIES[:3], "registry.json", "config.json",
        "bucket/keep.txt", "bucket/subtree/report.pdf", "scheduler.json", "plugins.json",
    ]
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    runtime = FixtureHarness(tmp_path)
    runtime.fail_once = fail_start
    action = runtime.reset_session if kind == "session" else runtime.reset_memory
    if fail_start:
        with pytest.raises(RuntimeError, match="previous state was restored"):
            asyncio.run(action())
        assert runtime.published == []
        selected = ()
    else:
        result = asyncio.run(action())
        assert result["status"] == "reset"
        selected = SESSION_RESET_ENTRIES if kind == "session" else MEMORY_RESET_ENTRIES
        assert runtime.published == ([{"type": "interface_refresh_requested"}] if kind == "session" else [])
    for name in paths:
        erased = any(name == item or name.startswith(item + "/") for item in selected)
        path = tmp_path / name
        if erased:
            assert not path.exists()
        else:
            assert path.read_text() == name
    assert not list(tmp_path.glob(".session-reset-*"))
    assert not runtime.resetting
