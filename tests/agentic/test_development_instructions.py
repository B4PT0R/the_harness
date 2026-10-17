from the_framework.agent import Agent
from the_harness.prompts import install_assistant_instructions


def test_development_preferences_are_installed_in_agentic_scope():
    agent = install_assistant_instructions(Agent())
    text = agent.instructions.render(scope="agentic")
    for section in (
        "Incidental findings",
        "Responsibility for code quality",
        "Economy of code",
        "Modularity and extensibility",
        "Refactoring and compatibility",
    ):
        assert f"## {section}" in text
    assert "record a concise actionable note in the registry" in text
    assert "Finish X cleanly first" in text
    assert "# Development discipline" not in agent.instructions.render(scope="vocal")
