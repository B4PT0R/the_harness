"""Neutral curation policy over reusable persistent memory."""
from pathlib import Path
from the_framework.plugins.memory.agent import MemoryExtension as GenericMemoryExtension

class MemoryExtension(GenericMemoryExtension):
    curator_instructions = (Path(__file__).parent / "prompts" / "curator.md").read_text()

    consultation_instructions = (
        "You are Jiminy, Pandora’s memory specialist. "
        + GenericMemoryExtension.consultation_instructions
    )
