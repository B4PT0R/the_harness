import pytest

from the_harness.control import HarnessControl
from the_framework.server.runtime.discovery import ServerDescriptorStore


class Response:
    content = b"payload"

    def raise_for_status(self):
        return None

    def json(self):
        return {"status": "ok"}


class Client:
    calls = []

    def __init__(self, **options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def request(self, method, url, json=None):
        self.calls.append((method, url, json, self.options))
        return Response()


def test_control_reads_private_descriptor_and_opens_ui(tmp_path):
    descriptor = ServerDescriptorStore(tmp_path / "runtime" / "server.json")
    descriptor.write({
        "version": 1,
        "host": "127.0.0.1",
        "port": 43210,
        "token": "secret",
        "pid": 1,
        "started_at": 1,
    })
    commands = []

    def run(command, **options):
        commands.append((command, options))

    Client.calls = []
    control = HarnessControl(
        tmp_path,
        command_runner=run,
        client_factory=Client,
    )

    result = control.open()

    assert result == {"status": "ok"}
    assert commands[0][0] == [
        "systemctl",
        "--user",
        "start",
        "the-harness-tray.service",
    ]
    assert Client.calls[-1][:3] == (
        "POST",
        "http://127.0.0.1:43210/api/v1/ui/open",
        None,
    )
    assert Client.calls[-1][3]["headers"] == {
        "Authorization": "Bearer secret",
    }


def test_control_status_is_stopped_without_descriptor(tmp_path):
    control = HarnessControl(tmp_path)
    assert control.status() == {"status": "stopped"}


def test_control_stops_tray_and_server_together(tmp_path):
    commands = []

    def run(command, **options):
        commands.append((command, options))

    control = HarnessControl(tmp_path, command_runner=run)
    control.stop()

    assert commands == [(
        [
            "systemctl",
            "--user",
            "stop",
            "the-harness-tray.service",
            "the-harness-ui.service",
            "the-harness-browser.service",
            "the-harness.service",
        ],
        {"check": False, "text": True, "capture_output": True},
    )]


def test_control_restart_preserves_browser_and_waits_for_server(tmp_path):
    ServerDescriptorStore(tmp_path / "runtime" / "server.json").write({
        "version": 1,
        "host": "127.0.0.1",
        "port": 43210,
        "token": "secret",
        "pid": 1,
        "started_at": 1,
    })
    commands = []

    def run(command, **options):
        commands.append((command, options))

    control = HarnessControl(tmp_path, command_runner=run, client_factory=Client)
    control.restart()

    assert commands[0][0] == [
        "systemctl",
        "--user",
        "restart",
        "the-harness.service",
    ]


@pytest.mark.parametrize("action", ["start", "open", "restart"])
def test_remote_ui_is_unavailable_without_side_effects(tmp_path, action):
    commands = []
    Client.calls = []
    control = HarnessControl(
        tmp_path,
        command_runner=lambda command, **options: commands.append((command, options)),
        client_factory=Client,
    )
    configured = control.mode("remote", "https://assistant.example")
    with pytest.raises(RuntimeError, match="remote UI is not installed"):
        getattr(control, action)()
    assert commands == []
    assert Client.calls == []
    assert control.mode() == configured
    assert control.status() == {
        "status": "unavailable", "reason": "remote_ui_not_installed", **configured,
    }
    assert control.data_root() == {"data_root": None, "mode": "remote"}


def test_remote_open_cli_reports_unavailable_without_traceback(tmp_path, monkeypatch, capsys):
    from the_harness.control import main

    HarnessControl(tmp_path).mode("remote", "https://assistant.example")
    monkeypatch.setattr("sys.argv", ["control", "open", "--runtime-root", str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "remote UI is not installed" in output.err
    assert "Traceback" not in output.err
