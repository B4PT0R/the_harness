"""Application contracts for the independent, neutral canonical example."""
from pathlib import Path
from the_harness.application import application
from the_harness import runtime_paths
from the_harness.prompts import compaction_instructions


def test_application_uses_shared_features_without_companion_plugins():
    plan = application.compile()
    assert plan.primary_agent.name == "assistant"
    assert {"chat", "realtime", "memory", "registry", "bash", "chromium", "scheduler", "system"} <= set(plan.plugins)
    assert not {"succubus_satiety", "haptics", "image_generation", "video_generation", "media_library", "webcam", "remote_control"} & set(plan.plugins)
    assert plan.plugins["chat"].server_extension == "the_framework.plugins.chat.server:build_server_extensions"
    assert plan.plugins["realtime"].server_extension == "the_framework.plugins.realtime.server:build_server_extensions"


def test_new_instance_never_opens_old_companion_data(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("THE_HARNESS_MACHINE_ROOT", raising=False)
    (tmp_path / '.the_harness').mkdir()
    (tmp_path / '.the_harness/config.json').write_text('{"data_root":"/do/not/open/old/data"}')
    assert runtime_paths.bootstrap_root() == tmp_path / '.the_harness_assistant'
    assert runtime_paths.resolve_data_root() == tmp_path / 'TheHarness'


def test_neutral_compaction_preserves_task_continuity():
    prompt = compaction_instructions()
    assert 'objectives' in prompt
    assert 'Grown-Up Mode' not in prompt
    assert not (Path(__file__).parents[2] / 'the_harness/prompts/adult_mode.md').exists()
