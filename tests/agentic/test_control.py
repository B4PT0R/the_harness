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


def test_remote_control_opens_trusted_ui_without_starting_local_server(tmp_path, monkeypatch):
    calls = []
    commands = []

    class Browser:
        def __init__(self, socket_path):
            calls.append(("socket", socket_path))

        def call(self, method, url):
            calls.append((method, url))

    monkeypatch.setattr("the_harness.control.BrowserRPCClient", Browser)
    control = HarnessControl(
        tmp_path,
        command_runner=lambda command, **options: commands.append((command, options)),
    )
    assert control.mode("remote", "https://assistant.example") == {
        "version": 1, "mode": "remote", "endpoint": "https://assistant.example",
    }

    result = control.open()

    assert commands == [(["systemctl", "--user", "start", "the-harness-browser.service"], {
        "check": True, "text": True, "capture_output": True,
    })]
    assert calls[-1] == ("open_application_ui", "https://assistant.example/remote-ui/")
    assert result == {
        "status": "opened", "mode": "remote",
        "url": "https://assistant.example/remote-ui/",
    }
    assert control.data_root() == {"data_root": None, "mode": "remote"}
