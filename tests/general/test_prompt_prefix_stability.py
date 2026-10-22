"""The request prefix is deterministic; live providers remain a replaceable suffix."""
import os
from pathlib import Path
import subprocess
import sys


AUDIT = '''
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile

from codex_backend_sdk import OpenAI
from the_framework.agent import AgentResources, Message, Session
from the_harness.application import application

class Captured(Exception):
    pass

client = OpenAI()
wire = []
def capture(path, **kwargs):
    assert path == "/responses"
    body = kwargs["body"]
    assert kwargs["headers"]["session-id"] == body["prompt_cache_key"]
    wire.append(json.dumps(body, ensure_ascii=False, separators=(",", ":")))
    raise Captured()
client._post = capture

def send(payload):
    try:
        client.responses.create(**payload)
    except Captured:
        return wire[-1]
    raise AssertionError("Request did not reach offline transport")

def message(role, text, identity):
    return Message(id=identity, role=role, content=[{"type": "input_text", "text": text}])

session = Session(id="stable-session", history=[message("user", "Keep the prefix", "user-1")])
spec = application.compile().agents["assistant"]
agent = spec.build_agent(session, resources=AgentResources(client=client))

def request(agent, live):
    return asyncio.run(agent.agentic_loop.ageneration_payload([
        message("developer", live, "ephemeral-provider"),
    ]))

first = request(agent, "provider version one")
first_wire = send(first)
prefix = first["input"][:-1]
assert len(prefix) == 1
assert first["input"][-1]["content"][0]["text"] == "provider version one"
second = request(agent, "provider version two")
assert first["input"][:-1] == second["input"][:-1]
assert first["input"][-1] != second["input"][-1]
assert {k: v for k, v in first.items() if k != "input"} == {
    k: v for k, v in second.items() if k != "input"
}
assert len(session.history) == 1

# Rebuild from the same saved state, as a worker restart would do.
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "session.json"
    path.write_text(json.dumps(session))
    restored = Session.open(path)
    restored.set_attr("path", None)
rebuilt = spec.build_agent(restored, resources=AgentResources(client=client))
assert send(request(rebuilt, "provider version one")) == first_wire

# Append-only history must extend the prefix, never reorder its earlier items.
rebuilt.add_message("assistant", "A stable answer")
rebuilt.add_message("user", "Continue")
extended = request(rebuilt, "provider version three")
assert extended["input"][:len(prefix)] == prefix
assert extended["prompt_cache_key"] == first["prompt_cache_key"]
assert extended["instructions"] == first["instructions"]
assert extended["tools"] == first["tools"]

print(hashlib.sha256(first_wire.encode()).hexdigest())
'''


def test_wire_prefix_is_stable_across_steps_restores_and_python_hash_seeds():
    root = Path(__file__).resolve().parents[2]
    digests = []
    for seed in ("1", "2", "42"):
        run = subprocess.run(
            [sys.executable, "-c", AUDIT], cwd=root,
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True, text=True, timeout=30,
        )
        assert run.returncode == 0, run.stderr
        digests.append(run.stdout.strip())
    assert len(digests[0]) == 64
    assert len(set(digests)) == 1
