from datetime import datetime, timezone

import pytest

from the_harness.turn_timing import TurnTiming


@pytest.mark.parametrize("content", ["null", "[]", '"text"', "42", "false", "{}", "{"])
def test_invalid_timing_is_ignored_without_overwriting(tmp_path, content):
    path = tmp_path / "session.turn-timing.json"
    path.write_text(content, encoding="utf-8")
    timing = TurnTiming(path)
    assert timing.begin()["previous_turn"] is None
    assert path.read_text(encoding="utf-8") == content


def test_valid_completed_timing_is_restored(tmp_path):
    path = tmp_path / "session.turn-timing.json"
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    timing = TurnTiming(path, now=lambda: now)
    timing.begin()
    saved = timing.finish()
    restored = TurnTiming(path, now=lambda: now)
    previous = restored.begin()["previous_turn"]
    assert datetime.fromisoformat(previous["started_at"]) == datetime.fromisoformat(saved["started_at"])
    assert datetime.fromisoformat(previous["ended_at"]) == datetime.fromisoformat(saved["ended_at"])


def test_live_timing_uses_milliseconds_without_losing_persisted_precision(tmp_path):
    path = tmp_path / "timing.json"
    now = datetime(2026, 10, 23, 0, 0, 0, 123456, tzinfo=timezone.utc)
    timing = TurnTiming(path, now=lambda: now)
    assert timing.begin()["current_turn_started_at"] == "2026-10-23T00:00:00.123+00:00"
    saved = timing.finish()
    assert saved["started_at"].endswith(".123456+00:00")
    context = timing.begin()
    assert context["previous_turn"]["started_at"].endswith(".123+00:00")
    assert context["previous_turn"]["duration_seconds"] == 0
    assert context["previous_turn"]["elapsed_since_end_seconds"] == 0
