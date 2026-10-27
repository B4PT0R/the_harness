"""Application defaults and environment; resumable state belongs to the session."""
from .project_paths import PROJECT_ROOT
from the_framework import AgentResources
from .environment import load_runtime_environment


def runtime_resources(session_root):
    load_runtime_environment(session_root)
    return AgentResources(configuration={"bash": {"default_cwd": str(PROJECT_ROOT)}})
