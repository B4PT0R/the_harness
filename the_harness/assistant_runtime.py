"""Application-owned persistence without companion-state migration."""
from pathlib import Path
from the_framework import AgentResources
from .configuration import AgentConfigStore, AgentStateStore, config_path, state_path
from .environment import load_runtime_environment

def runtime_resources(session_path):
    load_runtime_environment(session_path)
    config_store = AgentConfigStore(config_path(session_path))
    state_store = AgentStateStore(state_path(session_path))
    config = {"bash": {"default_cwd": str(Path(__file__).parents[1])}, **config_store.load()}
    return AgentResources(configuration=config, state=state_store.load(),
                          persist_config=config_store.save, persist_state=state_store.save)
