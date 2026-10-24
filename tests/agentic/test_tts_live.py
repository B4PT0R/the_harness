"""Opt-in smoke test against the actual local Piper runtime and French voice."""

import asyncio
import os
from pathlib import Path
import struct
import time
import wave

import pytest
from the_framework.agent import Agent
from the_framework.plugins.artifacts.server import ArtifactAssets
from the_harness.plugins.tts.agent import TTSExtension

pytestmark = pytest.mark.skipif(os.environ.get("HARNESS_TTS_LIVE") != "1", reason="requires local Piper runtime and voice")


def test_french_piper_produces_non_silent_audio(tmp_path):
    agent = Agent(client=object(), session_path=tmp_path / "session.json")
    plugin = agent.add_extension(TTSExtension)
    assets = ArtifactAssets(tmp_path)

    async def bridge(request):
        return await assets.handle(request.method, request.payload)

    agent.bridge.bind(bridge)
    start = time.monotonic()
    result, artifact = asyncio.run(plugin.synthesize("Bonjour Baptiste. Ceci est un test de synthèse vocale locale."))
    with wave.open(result["path"], "rb") as audio:
        samples = struct.unpack(f"<{audio.getnframes()}h", audio.readframes(audio.getnframes()))
    assert result["sample_rate"] == 22050
    assert .5 < result["duration_seconds"] < 30
    assert max(abs(sample) for sample in samples) > 100
    assert artifact.kind == "audio" and Path(result["path"]).is_file()
    print({**result, "generation_seconds": round(time.monotonic() - start, 3)})
