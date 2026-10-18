import asyncio
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from the_framework.server.api.endpoints import HttpError
from the_framework.server.runtime.supervisor import WorkerSupervisor
from the_harness.app import create_app
from the_harness.plugins.local_files import service as module

LOCAL = SimpleNamespace(principal=SimpleNamespace(id="local-browser"))


def test_paths_classify_text_directories_and_binary_without_executing(tmp_path):
    text = tmp_path / "a b.md"
    text.write_text("# Bonjour\n", encoding="utf-8")
    binary = tmp_path / "binary.md"
    binary.write_bytes(b"abc\0def")
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    assert module.local_resource(str(text)) == (text, "text")
    assert module.local_resource(str(tmp_path)) == (tmp_path, "directory")
    assert module.local_resource(str(binary)) == (tmp_path, "directory")
    assert module.local_resource(str(image)) == (tmp_path, "directory")
    executable = tmp_path / "file.desktop"
    executable.write_text("[Desktop Entry]\nExec=evil")
    assert module.local_resource(str(executable)) == (tmp_path, "directory")
    link = tmp_path / "linked.md"
    link.symlink_to(text)
    assert module.local_resource(str(link)) == (text, "text")


@pytest.mark.parametrize("path", ["relative.md", "https://example.org/a", "file:///tmp/a", "/tmp/hello\n.txt", "/tmp/hello\0.txt"])
def test_invalid_paths_are_rejected(path):
    with pytest.raises(HttpError) as error:
        module.local_resource(path)
    assert error.value.status_code == 422


def test_missing_files_and_special_files_are_rejected(tmp_path):
    import os
    with pytest.raises(HttpError) as error:
        module.local_resource(str(tmp_path / "absent.txt"))
    assert error.value.status_code == 404
    fifo = tmp_path / "pipe.txt"
    os.mkfifo(fifo)
    with pytest.raises(HttpError) as error:
        module.local_resource(str(fifo))
    assert error.value.code == "not_regular_file"


def test_editor_preferences_persist_and_launch_is_explicit(tmp_path):
    launches = []
    async def launcher(*args):
        launches.append(args)
    async def run():
        file = tmp_path / "test.md"
        file.write_text("text")
        service = module.LocalFilesService(tmp_path / "settings.json", launcher=launcher)
        assert service.settings(LOCAL) == {"editor": "system"}
        await service.update("vscode", LOCAL)
        restarted = module.LocalFilesService(tmp_path / "settings.json", launcher=launcher)
        assert restarted.settings(LOCAL) == {"editor": "vscode"}
        assert not launches
        result = await restarted.open(str(file), LOCAL)
        assert result["kind"] == "text"
        assert launches == [("text", file, "vscode")]
        assert (tmp_path / "settings.json").stat().st_mode & 0o777 == 0o600
    asyncio.run(run())


def test_failed_persistence_does_not_change_preference(tmp_path, monkeypatch):
    service = module.LocalFilesService(tmp_path / "settings.json")
    def fail(_value):
        raise OSError("disk full")
    monkeypatch.setattr(service.store, "save", fail)
    with pytest.raises(OSError):
        asyncio.run(service.update("vscode", LOCAL))
    assert service.editor == "system"


def test_launchers_use_argument_lists_and_default_text_editor(tmp_path, monkeypatch):
    commands = []
    data = tmp_path / "data"
    desktop = data / "applications" / "text-editor.desktop"
    desktop.parent.mkdir(parents=True)
    desktop.touch()
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "other"))
    monkeypatch.setattr(module.shutil, "which", lambda name: f"/usr/bin/{name}")
    async def command(*args):
        commands.append(args)
        return "text-editor.desktop" if args[0].endswith("xdg-mime") else ""
    monkeypatch.setattr(module, "run_editor_command", command)
    target = tmp_path / "a ; $(touch hacked).md"
    asyncio.run(module.launch_resource("text", target, "vscode"))
    asyncio.run(module.launch_resource("text", target, "system"))
    asyncio.run(module.launch_resource("directory", tmp_path, "vscode"))
    assert commands == [
        ("/usr/bin/code", "--reuse-window", str(target)),
        ("/usr/bin/xdg-mime", "query", "default", "text/plain"),
        ("/usr/bin/gio", "launch", str(desktop), target.as_uri()),
        ("/usr/bin/gio", "open", tmp_path.as_uri()),
    ]


def test_host_opening_and_settings_are_unavailable_to_paired_clients(tmp_path):
    app = create_app(WorkerSupervisor(tmp_path / "session.json"), token="local", browser_token="browser")
    service = app.state.application.default_session.extensions["local_files"].service
    launches = []
    async def launcher(*args):
        launches.append(args)
    service.launcher = launcher
    remote = app.state.application.default_session.extensions["client_remote"].service
    _, remote_token = remote.clients.issue("desktop", platform="desktop")
    client = TestClient(app, base_url="http://127.0.0.1:48887")
    file = tmp_path / "a.md"
    file.write_text("text")
    for auth in ({}, {"Authorization": f"Bearer {remote_token}"}):
        assert client.post("/api/v1/local-files/open", json={"path": str(file)}, headers=auth).status_code == 401
        assert client.get("/api/v1/local-files/settings", headers=auth).status_code == 401
    headers = {"Authorization": "Bearer local"}
    assert client.get("/api/v1/local-files/settings", headers=headers).json() == {"editor": "system"}
    assert client.put("/api/v1/local-files/settings", json={"editor": "vscode"}, headers=headers).status_code == 200
    assert client.put("/api/v1/local-files/settings", json={"editor": "evil"}, headers=headers).status_code == 422
    assert client.post("/api/v1/local-files/open", json={"path": str(file)}, headers=headers).status_code == 200
    assert launches == [("text", file, "vscode")]
    # Defense in depth, even if a future desktop allowlist changes.
    with pytest.raises(HttpError) as error:
        asyncio.run(service.open(str(file), SimpleNamespace(principal=SimpleNamespace(id="remote:desktop"))))
    assert error.value.status_code == 403
