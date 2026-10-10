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
    assert "Complete the work that depends on a temporary provider's information before" in text
    assert "Merely observing it is not enough" in text
    assert "information-dependent work is complete" in text
