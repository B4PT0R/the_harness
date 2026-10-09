from pathlib import Path
from the_framework.utils.persistence import MappingStore

class AgentConfigStore(MappingStore):
    field = "agent"

class AgentStateStore(MappingStore):
    field = "plugins"

def config_path(session_path):
    return Path(session_path).with_name("config.json")

def state_path(session_path):
    return Path(session_path).with_name("state.json")
