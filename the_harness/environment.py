import os
from pathlib import Path


def load_dotenv(path):
    """Load a small, predictable dotenv subset without overriding process env."""
    path = Path(path)
    if not path.is_file():
        return {}
    loaded = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or not name or not name.replace("_", "a").isalnum() or name[0].isdigit():
            raise ValueError(f"invalid dotenv assignment at {path}:{line_number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if name not in os.environ:
            os.environ[name] = value
            loaded[name] = value
    return loaded


def load_runtime_environment(session_path):
    machine_root = os.environ.get("THE_HARNESS_MACHINE_ROOT")
    root = Path(machine_root).expanduser().resolve() if machine_root else Path(session_path).parent
    return load_dotenv(root / ".env")
