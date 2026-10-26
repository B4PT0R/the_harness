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


def test_native_identity_last_repr_and_explicit_projection(runtime):
    _, plugin = runtime

    async def scenario():
        first = await plugin.execute('''
class Native:
    def __repr__(self):
        return "<Native result>"
x = Native()
identity = id(x)
x
''')
        assert first["status"] == "ok"
        assert "result_type" not in first and "error" not in first
        assert first["stdout"] == "<Native result>\n" and first["exports"] == {}
        result = await plugin.execute('agent.export({"same": id(x) == identity, "underscore": _ is x})')
        assert result["session_id"] == first["session_id"]
        assert result["exports"]["result"] == {"same": True, "underscore": True}
        assert not result["namespace_lost"]
        frozen = await plugin.execute('v = [1]; agent.export(v); v.append(2)')
        assert frozen["exports"] == {"result": [1]}
        bad = await plugin.execute('agent.export(x)')
        assert bad["status"] == "error" and "JSON serializable" in bad["stderr"]
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
        assert missing_feedback["status"] == "error" and "user_feedback" in missing_feedback["stderr"]
        for name in ["pynteract.reset", "reset", "pynteract.execute"]:
            recursive = await plugin.execute(f'await agent.call({name!r}, user_feedback="Je teste la récursion.")')
            assert recursive["status"] == "error" and "Recursive" in recursive["stderr"]
        worker.deactivate()
        disabled = await plugin.execute('await agent.call("example.echo", value=1, user_feedback="Je teste un outil désactivé.")')
        assert disabled["status"] == "error" and "unknown tool namespace" in disabled["stderr"]
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
        assert "error" not in failed and "result_type" not in failed
        assert failed["stderr"].count("ValueError: cell failure") == 1
        assert (await plugin.execute('agent.export(x)'))["exports"]["result"] == 2
        input_result = await plugin.execute('input("question")')
        assert "Interactive input" in input_result["stderr"]
        native = await plugin.execute('import os; os.write(1, b"not protocol JSON\\n"); agent.export(3)')
        assert native["exports"]["result"] == 3
        for value in ['float("nan")', 'float("inf")', '{1, 2}', 'b"bytes"']:
            assert (await plugin.execute(f'agent.export({value})'))["status"] == "error"
        too_big = await plugin.execute('agent.export("x" * (2 * 1024 * 1024))')
        assert too_big["status"] == "error" and "1 MiB" in too_big["stderr"]
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


def test_verbose_stdout_stderr_and_repr_keep_both_edges(runtime):
    from the_framework.utils.tokens import truncate_middle
    from the_harness.plugins.pynteract.protocol import MAX_OUTPUT_TOKENS
    _, plugin = runtime
    text = "BEGIN\n" + "word " * 20000 + "\nEND\n"

    async def scenario():
        for code, stream in [
            ('import sys; print(text, end=""); completed = True', "stdout"),
            ('print(text, end="", file=sys.stderr); completed = True', "stderr"),
            ('class Verbose:\n    def __repr__(self): return text\nVerbose()', "stdout"),
        ]:
            await plugin.execute(f'text = {text!r}; completed = False')
            result = await plugin.execute(code)
            assert result["status"] == "ok", result
            actual = result[stream]
            raw = text + ("\n" if code.endswith("Verbose()") else "")
            assert actual == truncate_middle(raw, max_tokens=MAX_OUTPUT_TOKENS)
            assert actual.startswith("BEGIN\n") and actual.rstrip().endswith("END")
            assert "Middle truncated" in actual
            assert len(actual) < len(text)
            assert "error" not in result and "result_type" not in result
            if not code.endswith("Verbose()"):
                assert (await plugin.execute('completed'))["stdout"] == "True\n"
        chunks = await plugin.execute('''
print("BEGIN")
for i in range(1000):
    print("word " * 10)
print("END")
completed = True
''')
        assert chunks["status"] == "ok"
        assert chunks["stdout"].startswith("BEGIN\n")
        assert chunks["stdout"].endswith("END\n")
        assert "Middle truncated" in chunks["stdout"]
        short = await plugin.execute('print("short"); 21 * 2')
        assert short["stdout"] == "short\n42\n" and short["stderr"] == ""
    asyncio.run(scenario())


async def until_output(plugin, job_id, text, stream="stdout"):
    async with asyncio.timeout(10):
        while True:
            state = await plugin.check(job_id)
            if text in state[stream]:
                return state
            assert state["status"] in {"running", "interrupting"}, state
            await asyncio.sleep(.01)


def test_job_live_sync_output_busy_and_final_result(runtime):
    _, plugin = runtime

    async def scenario():
        await plugin.execute("kept = object(); identity = id(kept)")
        started = await plugin.job('''import time, sys
print("FIRST")
print("warning", file=sys.stderr)
time.sleep(.6)
print("LAST")
agent.export(id(kept) == identity)
42
''')
        job_id = started["job_id"]
        assert started["status"] == "started"
        with pytest.raises(RuntimeError, match="busy"):
            await plugin.job("1")
        with pytest.raises(RuntimeError, match="busy"):
            await plugin.execute("1")
        with pytest.raises(RuntimeError, match="busy"):
            await plugin.call_python("anything", "{}", "value")
        live = await until_output(plugin, job_id, "FIRST")
        assert live["status"] == "running" and "LAST" not in live["stdout"]
        assert (await until_output(plugin, job_id, "warning", "stderr"))["status"] == "running"
        short = await plugin.wait(job_id, .01)
        assert short["status"] == "running" and short["wait_reason"] == "timeout"
        final = await plugin.wait(job_id, 10)
        assert final["status"] == "completed" and final["result_status"] == "ok"
        assert final["wait_reason"] == "job_completed" and not final["namespace_lost"]
        assert final["stdout"] == "FIRST\nLAST\n42\n" and final["stderr"] == "warning\n"
        assert final["exports"]["result"] is True
        assert (await plugin.interrupt(job_id)) == (await plugin.check(job_id))
        again = await plugin.execute("agent.export(id(kept) == identity)")
        assert again["exports"]["result"] and again["session_id"] == final["session_id"]
        assert (await plugin.check(job_id))["session_id"] == final["session_id"]
    asyncio.run(scenario())


def test_job_tail_rolls_and_large_frames_are_split(runtime):
    _, plugin = runtime

    async def scenario():
        job_id = (await plugin.job('''import time
print("OLD")
print("é" * 20000 + "NEW")
time.sleep(.5)
'''))["job_id"]
        live = await until_output(plugin, job_id, "NEW")
        assert live["status"] == "running" and len(live["stdout"]) == 12000
        assert "OLD" not in live["stdout"] and live["output_chars"]["stdout"] == 20008
        final = await plugin.wait(job_id, 10)
        assert final["status"] == "completed" and final["stdout"].startswith("OLD\n")
        assert final["stdout"].endswith("NEW\n") and "Middle truncated" in final["stdout"]
    asyncio.run(scenario())


def test_job_kill_reset_shutdown_and_immediate_cancel(runtime):
    _, plugin = runtime

    async def scenario():
        await plugin.execute("precious = 1")
        immediate = (await plugin.job("import time; time.sleep(30)"))["job_id"]
        stopped = await plugin.kill(immediate)
        assert stopped["status"] == "interrupted" and stopped["namespace_lost"]
        assert plugin._active_job is None and plugin._process is None
        for action in ["kill", "reset", "shutdown", "deactivate"]:
            job_id = (await plugin.job('import time; print("READY"); time.sleep(30)'))["job_id"]
            live = await until_output(plugin, job_id, "READY")
            process = plugin._process
            if action == "kill":
                await plugin.kill(job_id)
            elif action == "reset":
                await plugin.reset()
            else:
                await asyncio.to_thread(getattr(plugin, action))
                await asyncio.gather(plugin._jobs[job_id]["task"], return_exceptions=True)
                if action == "deactivate":
                    plugin.activate()
            assert process.poll() is not None
            final = await plugin.check(job_id)
            assert final["status"] == "interrupted" and final["namespace_lost"]
            assert final["session_id"] == live["session_id"] and "READY" in final["stdout"]
            restored = await plugin.execute('agent.export("precious" in globals())')
            assert restored["session_id"] != live["session_id"]
            assert restored["exports"]["result"] is False
    asyncio.run(scenario())


def test_job_timeout_crash_and_cell_error(runtime):
    _, plugin = runtime

    async def scenario():
        await plugin.execute("x = 1")
        for code, deadline, status, lost in [
            ('import time; print("BEFORE"); time.sleep(30)', .5, "timed_out", True),
            ('import os; os._exit(7)', 10, "failed", True),
            ('x = 3; raise ValueError("oops")', 10, "failed", False),
        ]:
            job_id = (await plugin.job(code, deadline))["job_id"]
            final = await plugin.wait(job_id, 10)
            assert final["status"] == status and final["namespace_lost"] == lost, final
            if status == "timed_out":
                assert final["stdout"] == "BEFORE\n"
            if not lost:
                assert "ValueError: oops" in final["stderr"]
                assert (await plugin.execute("x"))["stdout"] == "3\n"
    asyncio.run(scenario())


def test_job_worker_rpc_uses_canonical_pipeline(runtime):
    agent, plugin = runtime
    agent.add_extension(WorkerTools)
    hooked = []

    def on_tool_output(output):
        hooked.append(output.call_id)
        return output
    agent.hooks.add(on_tool_output)

    async def scenario():
        job_id = (await plugin.job('''import asyncio
print("RPC")
await asyncio.sleep(.05)
agent.export(await agent.call("example.echo", value=17,
                             user_feedback="Je teste un outil depuis un job Python."))
'''))["job_id"]
        final = await plugin.wait(job_id, 10)
        assert final["status"] == "completed", final
        reply = final["exports"]["result"]
        assert reply["outputs"][0]["value"]["echo"] == 17
        calls = [item for item in agent.session.history
                 if isinstance(item, FunctionCall) and item.namespace == "example"]
        assert len(calls) == 1 and calls[0].call_id in hooked
        assert sum(item.get("id") == reply["message_ids"][0] for item in agent.session.history) == 1
    asyncio.run(scenario())


def test_job_wait_steering_cancellation_limits_and_retention(runtime, monkeypatch):
    agent, plugin = runtime

    async def scenario():
        job_id = (await plugin.job('import time; print("READY"); time.sleep(30)'))["job_id"]
        await until_output(plugin, job_id, "READY")
        with monkeypatch.context() as patch:
            patch.setattr(agent.agentic_loop, "wait_for_activity", lambda _: "steering")
            steered = await plugin.wait(job_id, 10)
            assert steered["status"] == "running" and steered["wait_reason"] == "steering"
        waiting = asyncio.create_task(plugin.wait(job_id, 10))
        await asyncio.sleep(.02)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert (await plugin.check(job_id))["status"] == "running"
        for value in [-1, 61, True, float("nan"), float("inf")]:
            with pytest.raises(ValueError):
                await plugin.wait(job_id, value)
        await plugin.interrupt(job_id)
        assert (await plugin.wait(job_id, 10))["status"] == "interrupted"
        for value in [0, 901, True, float("nan"), float("inf")]:
            with pytest.raises(ValueError):
                await plugin.job("1", value)
        with pytest.raises(ValueError, match="128 KiB"):
            await plugin.job("x" * (MAX_CODE + 1))
        for _ in range(33):
            next_id = (await plugin.job("pass"))["job_id"]
            assert (await plugin.wait(next_id, 10))["status"] == "completed"
        assert len(plugin._jobs) == 32
        with pytest.raises(ValueError, match="expired"):
            await plugin.check(job_id)
    asyncio.run(scenario())


@pytest.mark.parametrize("body", ["while True:\n        counter += 1", "await asyncio.sleep(30)", "time.sleep(30)"])
def test_job_soft_interrupt_preserves_identity_and_finally(runtime, body):
    _, plugin = runtime

    async def scenario():
        await plugin.execute("kept = object(); identity = id(kept)")
        job_id = (await plugin.job('import asyncio, time\ncounter = 0\ntry:\n    print("READY")\n    '
                                   + body + '\nfinally:\n    cleaned = True'))["job_id"]
        live = await until_output(plugin, job_id, "READY")
        process = plugin._process
        requested = await plugin.interrupt(job_id)
        assert requested["status"] == "interrupting"
        final = await plugin.wait(job_id, 10)
        assert final["status"] == "interrupted" and not final["namespace_lost"], final
        assert final["result_status"] == "interrupted" and "READY" in final["stdout"]
        assert process.poll() is None
        after = await plugin.execute("agent.export([id(kept) == identity, cleaned])")
        assert after["exports"]["result"] == [True, True]
        assert after["session_id"] == live["session_id"] == final["session_id"]
    asyncio.run(scenario())


def test_soft_interrupt_requested_before_child_start(runtime):
    _, plugin = runtime

    async def scenario():
        job_id = (await plugin.job("kept = 42\nwhile True:\n    pass"))["job_id"]
        assert (await plugin.interrupt(job_id))["status"] == "interrupting"
        final = await plugin.wait(job_id, 10)
        assert final["status"] == "interrupted" and not final["namespace_lost"], final
        assert (await plugin.execute("42"))["stdout"] == "42\n"
    asyncio.run(scenario())


def test_soft_interrupt_during_worker_rpc_drains_reply(runtime):
    agent, plugin = runtime
    agent.add_extension(WorkerTools)

    async def scenario():
        job_id = (await plugin.job('kept = 42; print("READY"); await agent.call("example.slow", user_feedback="Test interruption RPC.")'))["job_id"]
        await until_output(plugin, job_id, "READY")
        await plugin.interrupt(job_id)
        final = await plugin.wait(job_id, 10)
        assert final["status"] == "interrupted" and not final["namespace_lost"], final
        after = await plugin.execute("agent.export(kept)")
        assert after["exports"]["result"] == 42 and after["session_id"] == final["session_id"]
    asyncio.run(scenario())


def test_ignored_soft_interrupt_can_be_force_killed(runtime):
    _, plugin = runtime

    async def scenario():
        job_id = (await plugin.job('from pynteract import ExecutionInterrupted\nimport time\ntry:\n    print("READY")\n    time.sleep(30)\nexcept ExecutionInterrupted:\n    print("IGNORED")\n    time.sleep(30)'))["job_id"]
        await until_output(plugin, job_id, "READY")
        await plugin.interrupt(job_id)
        await until_output(plugin, job_id, "IGNORED")
        assert (await plugin.check(job_id))["status"] == "interrupting"
        final = await plugin.kill(job_id)
        assert final["status"] == "interrupted" and final["namespace_lost"], final
        assert (await plugin.execute('"ExecutionInterrupted" in globals()'))["stdout"] == "False\n"
    asyncio.run(scenario())


@pytest.mark.parametrize("text", ["x", "é", "\x00"])
def test_output_relay_bounds_wire_queue_and_resets(text):
    from the_harness.plugins.pynteract.session import OutputRelay
    from the_harness.plugins.pynteract.protocol import MAX_STREAM_BYTES

    class Writer:
        def __init__(self):
            self.frames = []
        def write(self, frame):
            self.frames.append(frame)

    writer = Writer()
    relay = OutputRelay(writer)
    relay.reset(True)
    for stream in ("stdout", "stderr"):
        capture = relay.output(stream)
        for _ in range(10000):
            capture(text * 100, "")
        assert relay.truncated[stream]
    notices = [json.loads(frame) for frame in writer.frames]
    assert sum(len(frame) for frame in writer.frames) <= MAX_STREAM_BYTES + 512
    assert len([n for n in notices if n.get("truncated")]) == 2
    relay.reset(False)
    count = len(writer.frames)
    relay.output("stdout")("ignored", "")
    assert len(writer.frames) == count
    relay.reset(True)
    relay.output("stdout")("fresh", "")
    assert json.loads(writer.frames[-1])["text"] == "fresh"


@pytest.mark.parametrize("writes", ["sys.stdout.write('x' * 2_000_000)",
                                     "for _ in range(100_000): sys.stdout.write('x' * 20)"])
def test_output_capture_overflow_keeps_counts_and_namespace(runtime, writes):
    _, plugin = runtime

    async def scenario():
        result = await plugin.execute("import sys; kept = 42\n" + writes + "\nNone")
        assert result["status"] == "ok"
        assert result["output_chars"] == {"stdout": 2_000_000, "stderr": 0}
        assert result["output_truncated"] == {"stdout": True, "stderr": False}
        assert "capture limit reached" in result["stdout"]
        from the_framework.utils.tokens import truncate_middle
        from the_harness.plugins.pynteract.protocol import MAX_CAPTURE_CHARS, MAX_OUTPUT_TOKENS
        from pynteract.streams import TRUNCATION_MARKER
        assert result["stdout"] == truncate_middle(
            "x" * MAX_CAPTURE_CHARS + TRUNCATION_MARKER, max_tokens=MAX_OUTPUT_TOKENS)
        assert (await plugin.execute("kept"))["stdout"] == "42\n"
    asyncio.run(scenario())


def test_live_overflow_and_soft_interrupt_preserve_namespace(runtime):
    _, plugin = runtime

    async def scenario():
        job_id = (await plugin.job("import sys, time\nkept = 42\nprint('é' * 2_000_000)\ntime.sleep(30)"))["job_id"]
        live = await until_output(plugin, job_id, "transport budget reached")
        assert live["status"] == "running" and live["output_truncated"]["stdout"]
        assert len(live["stdout"]) <= 12000
        await plugin.interrupt(job_id)
        final = await plugin.wait(job_id, 10)
        assert final["status"] == "interrupted" and not final["namespace_lost"]
        assert (await plugin.execute("kept"))["stdout"] == "42\n"
    asyncio.run(scenario())
