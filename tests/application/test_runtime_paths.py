import json

import pytest

from the_harness.runtime_paths import (
    configure_data_root,
    ensure_data_root_config,
    resolve_data_root,
)


def test_runtime_root_defaults_to_the_harness_in_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert resolve_data_root(bootstrap=tmp_path / ".the_harness") == tmp_path / "TheHarness"


def test_runtime_root_is_read_from_stable_bootstrap(tmp_path):
    bootstrap = tmp_path / ".the_harness"
    selected = tmp_path / "Dropbox" / "The Harness"
    result = configure_data_root(selected, bootstrap=bootstrap)
    assert result == selected
    assert selected.is_dir()
    assert resolve_data_root(bootstrap=bootstrap) == selected
    assert json.loads((bootstrap / "config.json").read_text()) == {"data_root": str(selected)}


def test_first_launch_persists_default_without_overwriting_later_choice(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    bootstrap = tmp_path / ".the_harness"
    assert ensure_data_root_config(bootstrap=bootstrap) == tmp_path / "TheHarness"
    selected = configure_data_root(tmp_path / "Dropbox" / "The Harness", bootstrap=bootstrap)
    assert ensure_data_root_config(bootstrap=bootstrap) == selected


def test_explicit_runtime_root_has_priority(tmp_path):
    bootstrap = tmp_path / ".the_harness"
    configure_data_root(tmp_path / "Dropbox", bootstrap=bootstrap)
    assert resolve_data_root(tmp_path / "fixture", bootstrap=bootstrap) == tmp_path / "fixture"


def test_invalid_bootstrap_fails_loudly(tmp_path):
    bootstrap = tmp_path / ".the_harness"
    bootstrap.mkdir()
    (bootstrap / "config.json").write_text("not json")
    with pytest.raises(RuntimeError, match="invalid Harness bootstrap"):
        resolve_data_root(bootstrap=bootstrap)
