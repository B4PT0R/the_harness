"""The plugin owns native objects; worker RPC retains canonical tool semantics."""

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest

from the_framework.agent import Agent, AgentExtension, Artifact, tool
from the_framework.agent.models.responses import FunctionCall, ToolOutput
from the_framework.plugins.artifacts.agent import ArtifactsExtension
from the_harness.plugins.pynteract.agent import PynteractExtension
from the_harness.plugins.pynteract.protocol import MAX_CODE, MAX_FRAME, encode, receive

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX private process transport")


@pytest.fixture
def runtime(tmp_path):
    agent = Agent(client=object(), session_path=tmp_path / "session.json")
    plugin = agent.add_extension(PynteractExtension)
    try:
        yield agent, plugin
    finally:
        plugin.shutdown()


def decode(item):
    return json.loads(ElementTree.fromstring(item.content[0].text).text)


class WorkerTools(AgentExtension):
    name = "example"

    @tool
    def echo(self, value: int):
        """Return structured JSON."""
        return {"echo": value, "unicode": "é<&"}

    @tool
    async def slow(self):
        """Leave time for cancellation while an RPC response is in flight."""
        await asyncio.sleep(.1)
        return {"finished": True}

    @tool
    async def fail(self):
        """Fail normally through the tool pipeline."""
        raise ValueError("deliberate failure")

    @tool
    def many(self):
        """Multiple outputs including a presentation."""
        return {"a": 1}, Artifact(kind="custom", payload={"count": 3})

    @tool
    def large(self):
        """An output that is truncated by the worker's normal budget."""
        return {"data": "word " * 10000}


def test_composition_binding_and_shutdown(runtime):
    from the_harness.application import application
    from the_harness.plugins.pynteract import PLUGIN
    assert PLUGIN in application.plugins
    agent, plugin = runtime
    assert "pynteract" in agent.registry("tools")
    assert "pynteract" in agent.registry("instructions")
    asyncio.run(plugin.execute("value = object()"))
    process = plugin._process
    plugin.deactivate()
    assert process.poll() is not None
    assert "pynteract" not in agent.registry("tools")
    assert "pynteract" not in agent.registry("instructions")
    plugin.activate()
    assert "pynteract" in agent.registry("tools")


def test_native_identity_no_implicit_repr_and_explicit_projection(runtime):
    _, plugin = runtime

    async def scenario():
        first = await plugin.execute('''
class Native:
    def __repr__(self):
        raise RuntimeError("must not render")
x = Native()
identity = id(x)
x
''')
        assert first["status"] == "ok" and first["result_type"] == "Native"
        assert first["stdout"] == "" and first["exports"] == {}
        result = await plugin.execute('agent.export({"same": id(x) == identity, "underscore": _ is x})')
        assert result["session_id"] == first["session_id"]
        assert result["exports"]["result"] == {"same": True, "underscore": True}
        assert not result["namespace_lost"]
        frozen = await plugin.execute('v = [1]; agent.export(v); v.append(2)')
        assert frozen["exports"] == {"result": [1]}
        bad = await plugin.execute('agent.export(x)')
        assert bad["status"] == "error" and "JSON serializable" in bad["error"]
        assert (await plugin.execute('agent.export(id(x) == identity)'))["exports"]["result"]
    asyncio.run(scenario())


def test_python_local_registry_sync_async_and_entrypoint(runtime):
    _, plugin = runtime

    async def scenario():
        registered = await plugin.execute('''
from collections import Counter
@agent.python.register
def counts(words):
    return Counter(words)
@agent.python.register(name="double")
async def doubling(value):
    return value * 2
agent.export(agent.python.list())
''')
        assert [f["name"] for f in registered["exports"]["result"]] == ["counts", "double"]
        result = await plugin.call_python("counts", '{"words":["x","x","y"]}', "counter")
        assert result["result_type"] == "Counter" and result["saved_as"] == "counter"
        projected = await plugin.execute('agent.export({"counts": dict(counter), "double": await agent.python.call("double", value=3)})')
        assert projected["exports"]["result"] == {"counts": {"x": 2, "y": 1}, "double": 6}
        bad = await plugin.call_python("counts", '{"words":[]}', "agent")
        assert bad["status"] == "error" and "save_as" in bad["error"]
        missing = await plugin.call_python("absent", '{}', "result")
        assert missing["status"] == "error" and "KeyError" in missing["error"]
    asyncio.run(scenario())


def test_worker_rpc_uses_pipeline_and_hook_even_inside_outer_tool(runtime):
    agent, plugin = runtime
    agent.add_extension(WorkerTools)
    events, hooked = [], []
    agent.emit = events.append

    def on_tool_output(output):
        hooked.append(output.call_id)
        return output
    agent.hooks.add(on_tool_output)

    async def scenario():
        call = FunctionCall(namespace="pynteract", name="execute", call_id="outer", arguments=json.dumps({
            "code": 'r = await agent.call("example.echo", value=42, user_feedback="Je teste le passage par le worker."); agent.export(r)',
            "user_feedback": "Je lance une cellule avec appel imbriqué.",
        }))
        agent.add_response_item(call)
        result = await asyncio.wait_for(agent.agentic_loop.run_tool_call(call), 10)
        cell = decode(result.output_items[0])
        assert cell["status"] == "ok", cell
        reply = cell["exports"]["result"]
        assert reply["status"] == "success"
        assert reply["outputs"] == [{"format": "json", "value": {"echo": 42, "unicode": "é<&"}}]
        inner_calls = [i for i in agent.session.history if isinstance(i, FunctionCall) and i.namespace == "example"]
        assert len(inner_calls) == 1
        assert inner_calls[0].call_id in hooked and "outer" in hooked
        assert any(e.type == "agent.tool_call.start" for e in events)
        ids = reply["message_ids"]
        assert len(ids) == 1 and any(i.get("id") == ids[0] for i in agent.session.history)
        assert sum(i.get("id") == ids[0] for i in agent.session.history) == 1
    asyncio.run(scenario())


def test_discovery_failures_disabled_tools_and_recursion(runtime):
    agent, plugin = runtime
    worker = agent.add_extension(WorkerTools)

    async def scenario():
        found = await plugin.execute('agent.export(await agent.tools())')
        names = [item["name"] for item in found["exports"]["result"]]
        assert "example" in names and "pynteract" not in names
        failed = await plugin.execute('agent.export(await agent.call("example.fail", user_feedback="Je teste un échec normal."))')
        assert failed["exports"]["result"]["status"] == "failure"
        assert "deliberate failure" in failed["exports"]["result"]["error"]
        missing_feedback = await plugin.execute('await agent.call("example.echo", value=1, user_feedback="")')
        assert missing_feedback["status"] == "error" and "user_feedback" in missing_feedback["error"]
        for name in ["pynteract.reset", "reset", "pynteract.execute"]:
            recursive = await plugin.execute(f'await agent.call({name!r}, user_feedback="Je teste la récursion.")')
            assert recursive["status"] == "error" and "Recursive" in recursive["error"]
        worker.deactivate()
        disabled = await plugin.execute('await agent.call("example.echo", value=1, user_feedback="Je teste un outil désactivé.")')
        assert disabled["status"] == "error" and "unknown tool namespace" in disabled["error"]
    asyncio.run(scenario())


def test_multiple_outputs_artifacts_and_truncation(runtime):
    agent, plugin = runtime
    agent.add_extension(WorkerTools)

    async def scenario():
        multi = await plugin.execute('agent.export(await agent.call("example.many", user_feedback="Je teste les sorties multiples."))')
        outputs = multi["exports"]["result"]["outputs"]
        assert outputs[0] == {"format": "json", "value": {"a": 1}}
        assert outputs[1]["format"] == "artifact"
        assert outputs[1]["value"]["payload"] == {"count": 3}
        agent.configs.max_tool_output_tokens = 100
        large = await plugin.execute('agent.export(await agent.call("example.large", user_feedback="Je teste la sortie bornée."))')
        output = large["exports"]["result"]["outputs"][0]
        assert output["format"] == "text" and len(output["value"]) < 10000
    asyncio.run(scenario())


def test_file_export_delegates_to_artifact_publisher(runtime, tmp_path):
    agent, plugin = runtime
    agent.add_extension(ArtifactsExtension)
    calls = []

    async def publish(plugin_name, method, payload, **options):
        calls.append((plugin_name, method, payload))
        assert Path(payload["payload"]["path"]).read_text() == "hello"
        return {"src": "/bucket/durable.txt", "title": "Export"}
    agent.bridge = SimpleNamespace(call=publish)
    path = tmp_path / "report.txt"

    async def scenario():
        result = await plugin.execute(f'''
from pathlib import Path
path = Path({str(path)!r})
path.write_text("hello")
agent.export(await agent.artifact("file", {{"path": str(path)}}, user_feedback="Je présente le fichier exporté."))
''')
        assert result["status"] == "ok", result
        output = result["exports"]["result"]["outputs"][0]
        assert output["format"] == "artifact" and output["value"]["payload"]["src"] == "/bucket/durable.txt"
        assert calls[0][:2] == ("artifacts", "publish")
        assert sum(isinstance(i, Artifact) for i in agent.session.history) == 1
    asyncio.run(scenario())


def test_errors_limits_stdio_and_reset_keep_worker_alive(runtime):
    _, plugin = runtime

    async def scenario():
        await plugin.execute("x = 1")
        failed = await plugin.execute('x = 2\nraise ValueError("cell failure")')
        assert failed["status"] == "error" and not failed["namespace_lost"]
        assert (await plugin.execute('agent.export(x)'))["exports"]["result"] == 2
        noisy = await plugin.execute('for i in range(100000): print("x" * 100)')
        assert noisy["status"] == "error" and "output exceeds" in noisy["error"]
        assert len(noisy.get("stdout", "")) <= 32768
        input_result = await plugin.execute('input("question")')
        assert "Interactive input" in input_result["error"]
        native = await plugin.execute('import os; os.write(1, b"not protocol JSON\\n"); agent.export(3)')
        assert native["exports"]["result"] == 3
        for value in ['float("nan")', 'float("inf")', '{1, 2}', 'b"bytes"']:
            assert (await plugin.execute(f'agent.export({value})'))["status"] == "error"
        too_big = await plugin.execute('agent.export("x" * (2 * 1024 * 1024))')
        assert too_big["status"] == "error" and "1 MiB" in too_big["error"]
        reset = await plugin.reset()
        assert reset["namespace_lost"]
        fresh = await plugin.execute('agent.export("x" in globals())')
        assert not fresh["exports"]["result"]
        assert fresh["session_id"] != reset["previous_session_id"]
    asyncio.run(scenario())


def test_timeout_crash_and_cancellation_lose_namespace_and_recover(runtime):
    _, plugin = runtime

    async def scenario():
        await plugin.execute("value = 42")
        process = plugin._process
        timeout = await plugin.execute('import time; time.sleep(30)', timeout_seconds=0.1)
        assert timeout["namespace_lost"] and "TimeoutError" in timeout["error"]
        assert process.poll() is not None
        recovered = await plugin.execute('agent.export("value" in globals())')
        assert not recovered["exports"]["result"]
        crashed = await plugin.execute('import os; os._exit(7)')
        assert crashed["namespace_lost"]
        assert (await plugin.execute('agent.export(42)'))["exports"]["result"] == 42
        running = asyncio.create_task(plugin.execute('import time; time.sleep(30)'))
        await asyncio.sleep(0.1)
        process = plugin._process
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert process.poll() is not None
        assert (await plugin.execute('agent.export(43)'))["exports"]["result"] == 43
    asyncio.run(scenario())


def test_calls_are_serialized_and_leftover_tasks_cancelled(runtime):
    _, plugin = runtime

    async def scenario():
        first, second = await asyncio.gather(
            plugin.execute('import asyncio; x = []; await asyncio.sleep(.05); x.append(1)'),
            plugin.execute('x.append(2); agent.export(x)'),
        )
        assert first["session_id"] == second["session_id"]
        assert second["exports"]["result"] == [1, 2]
        await plugin.execute('task = asyncio.create_task(asyncio.sleep(100))')
        result = await plugin.execute('agent.export(task.cancelled())')
        assert result["exports"]["result"] is True
    asyncio.run(scenario())


def test_unawaited_rpc_is_drained_before_next_cell(runtime):
    agent, plugin = runtime
    agent.add_extension(WorkerTools)

    async def scenario():
        first = await plugin.execute('''
import asyncio
task = asyncio.create_task(agent.call("example.slow", user_feedback="Je teste un appel non attendu."))
await asyncio.sleep(.02)
''')
        assert first["status"] == "ok", first
        second = await plugin.execute('agent.export(task.cancelled())')
        assert second["status"] == "ok", second
        assert second["exports"]["result"] is True
        assert second["session_id"] == first["session_id"]
    asyncio.run(scenario())


def test_transport_and_argument_bounds(runtime):
    _, plugin = runtime
    with pytest.raises(ValueError, match="1 MiB"):
        encode({"data": "x" * MAX_FRAME})
    with pytest.raises(ValueError):
        encode({"nan": float("nan")})

    async def scenario():
        reader = asyncio.StreamReader(limit=MAX_FRAME)
        reader.feed_data(b'[]\n')
        with pytest.raises(ValueError, match="objects"):
            await receive(reader)
        for timeout in [0, -1, True, 901, float("nan")]:
            with pytest.raises(ValueError):
                await plugin.execute("1", timeout)
        with pytest.raises(ValueError, match="128 KiB"):
            await plugin.execute("x" * (MAX_CODE + 1))
        with pytest.raises(ValueError, match="JSON object"):
            await plugin.call_python("any", "[]", "x")
        assert plugin._process is None
    asyncio.run(scenario())
