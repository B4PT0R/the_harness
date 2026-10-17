"""Editorial feedback for evolving specialist instructions."""

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
