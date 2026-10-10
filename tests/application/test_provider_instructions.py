from the_framework.agent import Agent
from the_harness.prompts import install_assistant_instructions


def test_live_provider_guidance_is_installed_in_main_instructions():
    agent = install_assistant_instructions(Agent())
    text = agent.instructions.render(scope="agentic")
    assert "# Live context providers" in text
    assert "refreshed before each API turn" in text
    assert "not accumulated or persisted" in text
    assert "absence does not mean that" in text
    assert "before changing or clearing that state" in text
    assert "tool acknowledgement alone is not proof" in text
