import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image as Raster, UnidentifiedImageError

from the_framework.agent import Agent, AgentResponseItemAdded, Artifact, Image
from the_framework.plugins.artifacts.server import ArtifactAssets
from the_harness.plugins.images.agent import ImagesExtension


def png():
    output = BytesIO()
    Raster.new("RGB", (12, 8), "navy").save(output, format="PNG")
    return output.getvalue()


def generation(data=None, **updates):
    return {
        "type": "image_generation_call", "id": "ig_test", "status": "completed",
        "result": base64.b64encode(data if data is not None else png()).decode(),
        "revised_prompt": "A dark blue rectangle", "action": "generate",
        "output_format": "png", **updates,
    }


def setup(tmp_path):
    agent = Agent(client=object(), session_path=tmp_path / "session.json")
    plugin = agent.add_extension(ImagesExtension)
    assets = ArtifactAssets(tmp_path)

    async def bridge(request):
        assert request.capability == "artifacts"
        return await assets.handle(request.method, request.payload)

    agent.bridge.bind(bridge)
    return agent, plugin


def test_plugin_declares_server_tool_and_can_be_disabled(tmp_path):
    agent, plugin = setup(tmp_path)
    assert agent.registry("tools")["image_generation"] == {"type": "image_generation"}
    assert "images" in agent.registry("tools")
    plugin.deactivate()
    assert "image_generation" not in agent.registry("tools")
    assert "on_event" not in agent.registry("hooks")


def test_stream_result_becomes_immutable_vision_and_durable_artifact(tmp_path):
    agent, plugin = setup(tmp_path)
    raw = generation()
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: iter([
        {"type": "response.output_item.done", "item": raw},
        {"type": "response.completed", "response": {}},
    ])))
    agent.client = client
    asyncio.run(agent.agentic_loop.step())
    image, artifact = agent.session.history
    assert isinstance(image, Image) and isinstance(artifact, Artifact)
    assert image.generation_id == artifact.payload["generation_id"] == raw["id"]
    assert Path(image.path).read_bytes() == png()
    assert artifact.kind == "image" and artifact.payload["src"].startswith("/api/v1/bucket/")
    assert raw["result"] not in json.dumps(list(agent.session.history))
    assert "image_generation_call" not in json.dumps(agent.context.input())
    assert agent.context.input()[0]["content"][0]["type"] == "input_image"
    # Publication is idempotent across another generation and reloading a session.
    asyncio.run(plugin.after_generation(None))
    restored, reloaded = setup(tmp_path)
    asyncio.run(reloaded.after_generation(None))
    assert len(restored.session.history) == len(agent.session.history) == 2


def test_publication_failure_can_recover_after_restart(tmp_path):
    agent, plugin = setup(tmp_path)
    event = plugin.on_event(AgentResponseItemAdded(item=generation()))
    agent.add_response_item(event.item)

    async def fail(request):
        raise RuntimeError("bridge unavailable")

    agent.bridge.bind(fail)
    with pytest.raises(RuntimeError, match="bridge unavailable"):
        asyncio.run(plugin.after_generation(None))
    restored, reloaded = setup(tmp_path)
    asyncio.run(reloaded.after_generation(None))
    assert len(restored.session.history) == 2


def test_inspection_freezes_source_without_presenting_it(tmp_path):
    agent, plugin = setup(tmp_path)
    source = tmp_path / "source.png"
    source.write_bytes(png())
    result = asyncio.run(plugin.inspect_image(str(source), "Reference for an edit"))
    source.write_bytes(b"overwritten")
    assert isinstance(result, Image)
    assert result.context_tag == "local_image" and result.generation_id is None
    assert Path(result.path).read_bytes() == png()
    assert not agent.session.history
    # Inspection is a vision input only; unrelated generated images are not published.
    agent.add_response_item(Image(path=result.path, description="Other tool", generation_id="other"))
    asyncio.run(plugin.after_generation(None))
    assert len(agent.session.history) == 1


@pytest.mark.parametrize("item", [
    generation(status="failed", result=None), generation(status="in_progress", result=None),
])
def test_unfinished_results_are_not_published(tmp_path, item):
    agent, plugin = setup(tmp_path)
    event = AgentResponseItemAdded(item=item)
    assert plugin.on_event(event) is event
    assert not plugin.root.exists()


@pytest.mark.parametrize("encoded, error", [
    ("!invalid!", ValueError), (base64.b64encode(b"not an image").decode(), UnidentifiedImageError),
])
def test_invalid_results_are_rejected_without_persisting_binary(tmp_path, encoded, error):
    agent, plugin = setup(tmp_path)
    with pytest.raises(error):
        plugin.on_event(AgentResponseItemAdded(item=generation(result=encoded)))
    assert not agent.session.history
    assert not plugin.root.exists()


def test_identical_concurrent_inspections_are_safe(tmp_path):
    agent, plugin = setup(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(plugin._store, [png()] * 12))
    assert len(set(results)) == 1
    assert results[0].read_bytes() == png()
    assert list(plugin.root.iterdir()) == [results[0]]
