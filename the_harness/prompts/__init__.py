from pathlib import Path
from the_framework.agent import Instruction
ROOT = Path(__file__).parent

def prompt_text(name):
    path = name if isinstance(name, Path) else ROOT / f"{name}.md"
    return Path(path).read_text(encoding="utf-8").strip()

def compose_prompts(*names):
    return "\n\n".join(prompt_text(name) for name in names)

def compaction_instructions(configured=None):
    base = prompt_text("compaction")
    if not configured or configured.strip() == base:
        return base
    return base + "\n\n" + configured.strip()

def install_assistant_instructions(agent):
    for name, scope in (("general", "general"), ("agentic", "agentic")):
        agent.add_instruction(Instruction.from_file(ROOT / f"{name}.md", name=name, scope=scope))
    return agent
