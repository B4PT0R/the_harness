import json

import pytest

from the_harness.runtime_paths import (
    bootstrap_root,
    server_paths,
    configure_data_root,
    ensure_data_root_config,
    resolve_data_root,
)


def test_custom_machine_defaults_to_its_own_data(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert resolve_data_root(bootstrap=tmp_path / ".the_harness") == tmp_path / ".the_harness/data"


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
    assert ensure_data_root_config(bootstrap=bootstrap) == bootstrap / "data"
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


def test_machine_root_precedence_and_isolated_default_data(tmp_path, monkeypatch):
    environment = tmp_path / "environment"
    explicit = tmp_path / "explicit"
    monkeypatch.setenv("THE_HARNESS_MACHINE_ROOT", str(environment))
    assert bootstrap_root() == environment
    assert bootstrap_root(explicit) == explicit
    assert resolve_data_root() == environment / "data"
    paths = server_paths()
    assert paths.machine_root == environment
    assert paths.session_path == environment / "data/session.json"
    assert paths.descriptor_path == environment / "runtime/server.json"


def test_explicit_session_isolates_machine_state_unless_overridden(tmp_path, monkeypatch):
    monkeypatch.setenv("THE_HARNESS_MACHINE_ROOT", str(tmp_path / "installed"))
    session = tmp_path / "fixture/session.json"
    paths = server_paths(session=session)
    assert paths.machine_root == session.parent
    assert paths.data_root == session.parent
    assert paths.descriptor_path == session.parent / "runtime/server.json"
    explicit = tmp_path / "explicit"
    paths = server_paths(session=session, machine_root=explicit, descriptor=tmp_path / "custom.json")
    assert paths.machine_root == explicit
    assert paths.session_path == session
    assert paths.descriptor_path == tmp_path / "custom.json"


def test_moving_data_keeps_machine_state_in_place(tmp_path):
    machine = tmp_path / "machine"
    selected = tmp_path / "movable-data"
    configure_data_root(selected, bootstrap=machine)
    paths = server_paths(machine_root=machine)
    assert paths.data_root == selected
    assert paths.machine_root == machine
    assert paths.descriptor_path == machine / "runtime/server.json"
