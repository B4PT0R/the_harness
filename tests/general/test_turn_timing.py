from datetime import datetime, timezone

import pytest

from the_harness.turn_timing import TurnTiming


@pytest.mark.parametrize("content", ["null", "[]", '"text"', "42", "false", "{}", "{"])
def test_invalid_timing_is_ignored_without_overwriting(tmp_path, content):
    session = tmp_path / "session.json"
    path = tmp_path / "session.turn-timing.json"
    path.write_text(content, encoding="utf-8")
    timing = TurnTiming(session)
    assert timing.begin()["previous_turn"] is None
    assert path.read_text(encoding="utf-8") == content


def test_valid_completed_timing_is_restored(tmp_path):
    session = tmp_path / "session.json"
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    timing = TurnTiming(session, now=lambda: now)
    timing.begin()
    saved = timing.finish()
    restored = TurnTiming(session, now=lambda: now)
    previous = restored.begin()["previous_turn"]
    assert previous["started_at"] == saved["started_at"]
    assert previous["ended_at"] == saved["ended_at"]
