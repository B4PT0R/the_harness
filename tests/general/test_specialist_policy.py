"""Specialist policies reach their workers and preserve custom configuration."""
from pathlib import Path

from the_framework.agent import Agent
from the_harness.agent_definition import configure_assistant
from the_harness.plugins.memory.agent import MemoryExtension
from the_harness.prompts import compaction_instructions


def test_assistant_receives_base_compactor_and_custom_policy(tmp_path):
    custom = "Keep benchmark names and measured latency."
    agent = configure_assistant(Agent(tmp_path / "session.json", compaction={"instructions": custom}))
    assert agent.configs.compaction.instructions == compaction_instructions() + "\n\n" + custom
    assert compaction_instructions(compaction_instructions()) == compaction_instructions()


def test_memory_declaration_installs_full_curator_policy(tmp_path):
    agent = Agent(tmp_path / "session.json")
    extension = MemoryExtension(agent).load()
    declaration = next(value for kind, value in extension._contributions if kind == "agents" and value.name == "memory.jiminy")
    assert declaration.name == "memory.jiminy"
    assert declaration.spec.instructions[0].content == MemoryExtension.curator_instructions
    assert declaration.completion_tool == "complete_curation"
    assert Path(declaration.spec.configuration["memory_curator"]["store_path"]).parent == tmp_path


def test_memory_consultation_is_jiminy_without_curation_capabilities(tmp_path):
    extension = MemoryExtension(Agent(tmp_path / "session.json")).load()
    declaration = next(value for kind, value in extension._contributions
                       if kind == "agents" and value.name == "memory.consultation")
    assert "Jiminy" in declaration.spec.instructions[0].content
    assert not declaration.spec.extensions
    assert not declaration.retain_history
    assert declaration.completion_tool is None
