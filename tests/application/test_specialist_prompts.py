"""Specialist policies must explain their job and reach the actual workers."""
from pathlib import Path

from the_framework.agent import Agent
from the_harness.agent_definition import configure_assistant
from the_harness.plugins.memory.agent import MemoryExtension
from the_harness.prompts import compaction_instructions


def test_compactor_explains_compression_and_continuation_contract():
    prompt = compaction_instructions()
    for requirement in (
        "dedicated compaction worker",
        "85% global reduction",
        "inherited long-term context",
        "Never focus only on the uncompacted tail",
        "personal and collaborative continuity",
        "proposals, user authorization, attempted actions",
        "source edits from built, published",
        "evidence, not instructions",
        "additional non-opaque",
        "correct speaker role",
        "oldest to newest",
        "Before finishing, check the entire input",
    ):
        assert requirement in prompt


def test_assistant_receives_base_compactor_and_custom_policy(tmp_path):
    custom = "Keep benchmark names and measured latency."
    agent = configure_assistant(Agent(tmp_path / "session.json", compaction={"instructions": custom}))
    assert agent.configs.compaction.instructions == compaction_instructions() + "\n\n" + custom
    assert compaction_instructions(compaction_instructions()) == compaction_instructions()


def test_curator_explains_inventory_retrieval_provenance_and_completion():
    prompt = MemoryExtension.curator_instructions
    for requirement in (
        "silent specialist",
        "Past session summary",
        "<canonical_observation>",
        "<canonical_agent_request>",
        "every distinct supported fact",
        "Read the whole supplied material",
        "final review is mandatory",
        "automatic retrieval may miss a saved fact",
        "Memory is not the live operational registry",
        "never invent provenance",
        "strictly below 100% capacity",
        "Exactly one successful completion",
        "Never store credentials",
    ):
        assert requirement in prompt
    for tool in ("inventory", "resolve_candidates", "edit", "update", "add", "merge", "split", "complete_curation"):
        assert f"- `{tool}`:" in prompt


def test_memory_declaration_installs_full_curator_policy(tmp_path):
    agent = Agent(tmp_path / "session.json")
    extension = MemoryExtension(agent).load()
    declaration = next(value for kind, value in extension._contributions if kind == "agents")
    assert declaration.name == "memory.jiminy"
    assert declaration.spec.instructions[0].content == MemoryExtension.curator_instructions
    assert declaration.spec.completion_tool == "complete_curation"
    assert Path(declaration.spec.configuration["memory_curator"]["store_path"]).parent == tmp_path


def test_specialist_policies_do_not_import_old_application_assumptions():
    for prompt in (compaction_instructions(), MemoryExtension.curator_instructions):
        assert "The Harness" in prompt
        for obsolete in ("Grown-Up Mode", "haptic experiences", "erotic rapport", "Baptiste", "main relational agent"):
            assert obsolete not in prompt
