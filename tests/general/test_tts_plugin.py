"""Piper is optional, local, bounded, cancellable and produces playable artifacts."""

import asyncio
import os
from pathlib import Path
import sys
from types import MethodType
import wave

import pytest

from the_framework.agent import Agent, Artifact
from the_framework.plugins.artifacts.server import ArtifactAssets
from the_harness.plugins.tts.agent import RUNTIME, TTSExtension


def setup(tmp_path):
    agent = Agent(client=object(), session_path=tmp_path / "session.json")
    plugin = agent.add_extension(TTSExtension)
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"model")
    model.with_suffix(".onnx.json").write_text("{}")
    plugin.config.model = str(model)
    assets = ArtifactAssets(tmp_path)

    async def bridge(request):
        assert request.capability == "artifacts"
        return await assets.handle(request.method, request.payload)

    agent.bridge.bind(bridge)
    return agent, plugin


def wav(path):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(22050)
        audio.writeframes(b"\x00\x01" * 2205)


def test_synthesis_publishes_immutable_audio_and_cleans_temporary_files(tmp_path):
    agent, plugin = setup(tmp_path)
    calls = []

    async def generate(self, text, model, output):
        calls.append((text, model))
        wav(output)

    plugin._synthesize = MethodType(generate, plugin)
    metadata, artifact = asyncio.run(plugin.synthesize("  Bonjour Baptiste.  "))
    assert calls == [("Bonjour Baptiste.", Path(plugin.config.model))]
    assert metadata["duration_seconds"] == .1 and metadata["sample_rate"] == 22050
    assert isinstance(artifact, Artifact) and artifact.kind == "audio"
    assert artifact.payload["mime_type"] in {"audio/x-wav", "audio/wav"}
    assert artifact.payload["src"].startswith("/api/v1/bucket/")
    assert artifact.payload["description"] == "Bonjour Baptiste."
    path = Path(metadata["path"])
    assert path.is_file() and path.stat().st_mode & 0o777 == 0o600
    assert not list(plugin.root.glob(".synthesize-*"))
    _, restored = setup(tmp_path)
    assert path.is_relative_to(restored.root) and path.is_file()
    assert "tts" in agent.registry("tools")
    plugin.deactivate()
    assert "tts" not in agent.registry("tools")


@pytest.mark.parametrize("text", ["", " \n ", "a" * 4001])
def test_input_is_bounded(tmp_path, text):
    _, plugin = setup(tmp_path)
    with pytest.raises(ValueError, match="text"):
        asyncio.run(plugin.synthesize(text))
    assert not list(plugin.root.iterdir())


def test_missing_model_and_runtime_are_actionable_errors(tmp_path):
    _, plugin = setup(tmp_path)
    Path(plugin.config.model + ".json").unlink()
    with pytest.raises(FileNotFoundError, match="voice missing"):
        asyncio.run(plugin.synthesize("Bonjour"))
    Path(plugin.config.model + ".json").write_text("{}")
    plugin.config.python = str(tmp_path / "no-python")
    with pytest.raises(RuntimeError, match="uv sync"):
        asyncio.run(plugin.synthesize("Bonjour"))
    assert not list(plugin.root.iterdir())


@pytest.mark.parametrize("invalid", [0, 301])
def test_timeout_is_validated(tmp_path, invalid):
    _, plugin = setup(tmp_path)
    plugin.config.timeout_seconds = invalid
    with pytest.raises(ValueError, match="timeout_seconds"):
        asyncio.run(plugin.synthesize("Bonjour"))


def test_failed_and_invalid_synthesis_do_not_publish_or_keep_partial_audio(tmp_path):
    _, plugin = setup(tmp_path)

    async def generate(self, text, model, output):
        output.write_bytes(b"not a WAV")
        if text == "fail":
            raise RuntimeError("synthesis failed")

    plugin._synthesize = MethodType(generate, plugin)
    for text, error in [("fail", RuntimeError), ("bad wav", wave.Error)]:
        with pytest.raises(error):
            asyncio.run(plugin.synthesize(text))
        assert not list(plugin.root.iterdir())
        assert not list((tmp_path / "bucket").iterdir())


@pytest.mark.parametrize("cancel", [False, True])
def test_timeout_and_cancellation_reap_child_and_remove_partial_files(tmp_path, monkeypatch, cancel):
    _, plugin = setup(tmp_path)
    plugin.config.python = sys.executable
    plugin.config.timeout_seconds = 1
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    pidfile = tmp_path / "child.pid"
    (runtime / "synthesize.py").write_text(
        f"import os,time\nfrom pathlib import Path\nPath({str(pidfile)!r}).write_text(str(os.getpid()))\ntime.sleep(30)\n"
    )
    monkeypatch.setattr("the_harness.plugins.tts.agent.RUNTIME", runtime)

    async def run():
        task = asyncio.create_task(plugin.synthesize("Bonjour"))
        for _ in range(100):
            if pidfile.exists():
                break
            await asyncio.sleep(.01)
        assert pidfile.exists()
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
            await task

    asyncio.run(run())
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)
    assert not list(plugin.root.iterdir())


def test_worker_imports_no_piper_runtime():
    assert (RUNTIME / "uv.lock").is_file()
    assert "piper" not in sys.modules and "onnxruntime" not in sys.modules


@pytest.mark.parametrize('show,play', [(False, False), (False, True), (True, False), (True, True)])
def test_display_and_playback_are_independent(tmp_path, show, play):
    agent, plugin = setup(tmp_path)
    calls = []
    assets = ArtifactAssets(tmp_path)

    async def bridge(request):
        calls.append(request.capability)
        if request.capability == 'artifacts':
            return await assets.handle(request.method, request.payload)
        assert request.capability == 'tts' and request.method == 'play'
        assert request.payload['src'].startswith('/api/v1/bucket/')
        return {'status': 'blocked'}

    async def generate(self, text, model, output):
        wav(output)

    agent.bridge.bind(bridge)
    plugin._synthesize = MethodType(generate, plugin)
    result = asyncio.run(plugin.synthesize('Bonjour', show_artifact=show, play_audio=play))
    metadata = result[0] if show else result
    assert isinstance(result, tuple) == show
    assert Path(metadata['path']).is_file()
    assert ('playback' in metadata) == play
    assert calls == (['artifacts'] if show or play else []) + (['tts'] if play else [])


@pytest.mark.parametrize('options', [{'show_artifact': 1}, {'play_audio': 'true'}])
def test_playback_flags_require_booleans(tmp_path, options):
    _, plugin = setup(tmp_path)
    with pytest.raises(ValueError, match='booleans'):
        asyncio.run(plugin.synthesize('Bonjour', **options))


def test_playback_service_accepts_only_bucket_assets():
    from the_harness.plugins.tts.server import TTSPlayback

    class Clients:
        async def request(self, operation, payload):
            assert operation == 'audio.play' and payload == {'src': '/api/v1/bucket/audio.wav'}
            return {'status': 'unavailable'}

    service = TTSPlayback(Clients())
    for src in (None, 'https://example.org/a.wav', '/api/v1/bucket/../secret',
                '/api/v1/bucket/%2e/a.wav', '/api/v1/bucket/a.wav?token=secret'):
        with pytest.raises(ValueError):
            asyncio.run(service.handle('play', {'src': src}))
    assert asyncio.run(service.handle('play', {'src': '/api/v1/bucket/audio.wav'})) == {'status': 'unavailable'}
