"""Stable bootstrap configuration for the movable Harness data directory."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_BOOTSTRAP_ROOT = Path("~/.the_harness_assistant")
DEFAULT_DATA_ROOT = Path("~/TheHarnessAssistant")
BOOTSTRAP_CONFIG_NAME = "config.json"


def bootstrap_root(path=None) -> Path:
    return Path(path or DEFAULT_BOOTSTRAP_ROOT).expanduser().resolve()


def bootstrap_config_path(path=None) -> Path:
    return bootstrap_root(path) / BOOTSTRAP_CONFIG_NAME


def default_data_root() -> Path:
    return DEFAULT_DATA_ROOT.expanduser().resolve()


def resolve_data_root(explicit=None, *, bootstrap=None) -> Path:
    """Resolve an explicit root or the root recorded in the stable bootstrap."""
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    path = bootstrap_config_path(bootstrap)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default_data_root()
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"invalid Harness bootstrap configuration: {path}") from error
    value = payload.get("data_root") if isinstance(payload, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Harness bootstrap data_root is missing or invalid: {path}")
    return Path(value).expanduser().resolve()


def configure_data_root(value, *, bootstrap=None) -> Path:
    """Persist the data root atomically without moving existing application data."""
    root = Path(value).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    config_path = bootstrap_config_path(bootstrap)
    config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(config_path.parent, 0o700)
    payload = json.dumps({"data_root": str(root)}, indent=2) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{config_path.name}.", dir=config_path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, config_path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return root


def ensure_data_root_config(*, bootstrap=None) -> Path:
    """Create the deterministic bootstrap on first launch and return its root."""
    path = bootstrap_config_path(bootstrap)
    if path.exists():
        os.chmod(path.parent, 0o700)
        return resolve_data_root(bootstrap=bootstrap)
    return configure_data_root(default_data_root(), bootstrap=bootstrap)
