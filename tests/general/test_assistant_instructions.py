from the_framework.agent import Agent
from the_framework.plugins.agentic.agent import AgenticExtension

from the_harness.prompts import install_assistant_instructions, prompt_text


def test_agentic_plugin_preserves_the_assistants_agentic_instructions(tmp_path):
    agent = install_assistant_instructions(Agent(tmp_path / "session.json"))
    plugin = agent.add_extension(AgenticExtension)
    core = prompt_text("agentic")
    instructions = agent.registry("instructions")

    assert core in instructions.render(scope="agentic")
    assert plugin.instructions_section().content in instructions.render(scope="agentic")
    assert plugin.instructions_section().content not in instructions.render(scope="vocal")
    plugin.deactivate()
    assert core in agent.registry("instructions").render(scope="agentic")
    assert plugin.instructions_section().content not in agent.registry("instructions").render()
