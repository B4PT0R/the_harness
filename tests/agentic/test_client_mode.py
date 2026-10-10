import json

import pytest

from the_harness.client_mode import ClientModeStore, normalize_remote_endpoint


def test_client_mode_defaults_local_and_persists_remote_privately(tmp_path):
    path = tmp_path / "client.json"
    store = ClientModeStore(path)
    assert store.load() == {"version": 1, "mode": "local"}
    assert store.save("remote", "https://assistant.example:8443/") == {
        "version": 1, "mode": "remote", "endpoint": "https://assistant.example:8443",
    }
    assert json.loads(path.read_text()) == store.load()
    assert path.stat().st_mode & 0o777 == 0o600


def test_remote_endpoint_rejects_unencrypted_non_loopback_and_paths():
    assert normalize_remote_endpoint("http://127.0.0.1:48887") == "http://127.0.0.1:48887"
    with pytest.raises(ValueError, match="HTTPS"):
        normalize_remote_endpoint("http://assistant.example")
    with pytest.raises(ValueError, match="path"):
        normalize_remote_endpoint("https://assistant.example/ui")


@pytest.mark.parametrize("content", ["null", "[]", '"text"', "42", "false", "{}", "{"])
def test_invalid_client_configuration_fails_without_overwriting(tmp_path, content):
    path = tmp_path / "client.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        ClientModeStore(path).load()
    assert path.read_text(encoding="utf-8") == content
