"""Live quota context reuses the server cache without exposing account policy."""

import asyncio
from types import SimpleNamespace

import pytest
from the_framework.agent import Agent
from the_framework.plugins.system import SystemExtension as GenericSystemExtension

from the_harness.application import application
from the_harness.plugins.system import SystemExtension
from the_harness.quota import QuotaService, build_bridge


def test_system_binding_keeps_generic_instructions_and_tools():
    declaration = next(plugin for plugin in application.plugins if plugin.name == "system")
    assert declaration.agent_extension is SystemExtension
    assert declaration.agent_binding_required
    agent = Agent(client=object())
    extension = agent.add_extension(SystemExtension)
    assert "current_datetime" in agent.registry("providers")
    assert "reboot_server" in {tool.name for tool in agent.registry("tools")["system"].tools}
    assert extension.instructions_section() == GenericSystemExtension(agent).instructions_section()
    assert agent.registry("providers")["account_quota"].channels == ["text"]


@pytest.mark.parametrize("age,error,expected", [
    (None, None, "unavailable"),
    (0, None, "ready"),
    (120, None, "ready"),
    (121, None, "stale"),
    (0, "quota_backend_unavailable", "stale"),
])
def test_context_uses_only_cached_usage(tmp_path, age, error, expected):
    def no_backend():
        raise AssertionError("context must not create an SDK client")

    quota = QuotaService(tmp_path / "quota.json", clock=lambda: 1000, client_factory=no_backend)
    quota.windows["quota_7d"] = {"used_percent": 2, "reset_at": 2000}
    quota.windows["quota_5h"] = {"used_percent": 99, "reset_at": 1500}
    quota.updated_at = None if age is None else 1000 - age
    quota.error = error
    quota.credits = [{"id": "private-credit"}]
    quota.state["account_id"] = "private-account"
    snapshot = quota.context()
    assert snapshot == {
        "status": expected,
        "quota_7d": {"used_percent": 2, "reset_at": 2000},
        "updated_at": quota.updated_at, "error": error,
    }
    snapshot["quota_7d"]["used_percent"] = 99
    assert quota.windows["quota_7d"]["used_percent"] == 2
    quota.windows["quota_7d"] = None
    assert quota.context()["status"] == "unavailable"


def test_provider_reads_server_context_and_reports_bridge_outage(tmp_path):
    async def run():
        quota = QuotaService(tmp_path / "quota.json", clock=lambda: 1000)
        quota.updated_at = 1000
        quota.windows["quota_7d"] = {"used_percent": 2, "reset_at": 2000}
        handlers = {}
        build_bridge(SimpleNamespace(bridge=SimpleNamespace(register=handlers.__setitem__)), quota)
        agent = Agent(client=object())
        extension = agent.add_extension(SystemExtension)

        async def request(payload):
            assert payload.capability == "quota"
            assert payload.method == "context"
            return await handlers["quota"](payload.method, payload.payload)

        agent.bridge.bind(request)
        assert await extension.account_quota() == quota.context()
        outputs = await agent.registry("providers")["account_quota"].aoutputs()
        assert len(outputs) == 1
        assert '"used_percent":2' in outputs[0].content[0].text

        async def broken(payload):
            raise RuntimeError("private transport detail")

        agent.bridge.bind(broken)
        assert await extension.account_quota() == {
            "status": "unavailable", "error": "quota_bridge_unavailable",
        }
        with pytest.raises(ValueError, match="unsupported"):
            await handlers["quota"]("consume", {})

    asyncio.run(run())
