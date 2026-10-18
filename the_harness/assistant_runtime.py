"""Application defaults and environment; resumable state belongs to the session."""
from pathlib import Path
from the_framework import AgentResources
from .environment import load_runtime_environment


def runtime_resources(session_path):
    load_runtime_environment(session_path)
    return AgentResources(configuration={"bash": {"default_cwd": str(Path(__file__).parents[1])}})
