"""Snapshot of the current product recipe, not a fixed plugin catalogue."""

from the_harness.application import application

def test_application_uses_shared_features():
    plan = application.compile()
    assert plan.primary_agent.name == "assistant"
    assert {"chat", "realtime", "memory", "registry", "bash", "chromium", "scheduler", "system"} <= set(plan.plugins)
    assert plan.plugins["chat"].server_extension == "the_framework.plugins.chat.server:build_server_extensions"
    assert plan.plugins["realtime"].server_extension == "the_framework.plugins.realtime.server:build_server_extensions"
