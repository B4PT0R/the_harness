import asyncio
from types import MethodType

from test_tts_plugin import setup, wav


def test_prepare_alarm_audio_publishes_without_display_playback_or_scheduling(tmp_path):
    agent, plugin = setup(tmp_path)
    spoken = []

    async def generate(self, text, model, output):
        spoken.append(text)
        wav(output)

    plugin._synthesize = MethodType(generate, plugin)
    result = asyncio.run(plugin.prepare_alarm_audio("Bonjour Baptiste."))
    assert spoken == ["Bonjour Baptiste."]
    assert result["audio_src"].startswith("/api/v1/bucket/")
    assert result["duration_seconds"] == .1
    # setup's bridge accepts only artifact asset publication, not playback/scheduler calls.
    assert list((tmp_path / "bucket").rglob("*.wav"))
