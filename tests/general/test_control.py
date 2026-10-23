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
        service="fixture.service",
        tray_service="fixture-tray.service",
        ui_service="fixture-ui.service",
        browser_service="fixture-browser.service",
        command_runner=run,
        client_factory=Client,
    )

    result = control.open()

    assert result == {"status": "ok"}
    assert commands[0][0] == [
        "systemctl",
        "--user",
        "start",
        "fixture-tray.service",
        "fixture-browser.service",
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

    control = HarnessControl(tmp_path, service="fixture.service", tray_service="fixture-tray.service",
                             ui_service="fixture-ui.service", browser_service="fixture-browser.service",
                             command_runner=run)
    control.stop()

    assert commands == [(
        [
            "systemctl",
            "--user",
            "stop",
            "fixture-tray.service",
            "fixture-ui.service",
            "fixture-browser.service",
            "fixture.service",
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

    control = HarnessControl(
        tmp_path,
        service="fixture.service",
        tray_service="fixture-tray.service",
        ui_service="fixture-ui.service",
        browser_service="fixture-browser.service",
        command_runner=run,
        client_factory=Client,
    )
    Client.calls = []
    control.restart()
    assert Client.calls[0][:3] == (
        "GET", "http://127.0.0.1:43210/api/v1/status", None,
    )
    assert Client.calls[1][:3] == (
        "POST", "http://127.0.0.1:43210/api/v1/server/prepare-restart", None,
    )
    assert 0 < Client.calls[0][3]["timeout"] < Client.calls[1][3]["timeout"] < 180

    assert commands[0][0] == [
        "systemctl",
        "--user",
        "restart",
        "fixture.service",
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


def test_control_resolves_data_from_selected_machine_bootstrap(tmp_path):
    from the_harness.runtime_paths import configure_data_root

    machine = tmp_path / "machine"
    selected = tmp_path / "data"
    configure_data_root(selected, bootstrap=machine)
    assert HarnessControl(machine).data_root() == {"data_root": str(selected)}


@pytest.mark.parametrize("action", ["start", "stop", "restart"])
def test_custom_instance_never_controls_installed_units(tmp_path, action):
    commands = []
    control = HarnessControl(tmp_path, command_runner=lambda *args, **kwargs: commands.append(args))
    with pytest.raises(RuntimeError, match="refusing to control the installed instance"):
        getattr(control, action)()
    assert commands == []


def test_data_root_cli_honors_machine_root(tmp_path, monkeypatch, capsys):
    import json
    from the_harness.control import main

    machine, data = tmp_path / "machine", tmp_path / "data"
    monkeypatch.setattr("sys.argv", ["control", "data-root", str(data), "--machine-root", str(machine)])
    main()
    assert json.loads(capsys.readouterr().out)["data_root"] == str(data)
    assert HarnessControl(machine).data_root() == {"data_root": str(data)}


@pytest.mark.parametrize('failed_path', ['status', 'server/prepare-restart'])
@pytest.mark.parametrize('failure', ['timeout', 'transport', 'upstream'])
def test_restart_recovers_when_worker_probe_or_graceful_preparation_fails(tmp_path, monkeypatch, caplog, failed_path, failure):
    import httpx
    from unittest.mock import Mock

    control = HarnessControl(tmp_path, service='fixture.service')
    paths = []
    def request(method, path, **kwargs):
        paths.append(path)
        assert kwargs['timeout'] is not None
        if path != '/api/v1/' + failed_path:
            return {}
        if failure == 'timeout':
            raise httpx.ReadTimeout('worker unresponsive')
        if failure == 'transport':
            raise httpx.RemoteProtocolError('server closed connection')
        response = httpx.Response(503, request=httpx.Request(method, 'http://localhost' + path))
        response.raise_for_status()
    monkeypatch.setattr(control, 'request', request)
    systemctl = Mock()
    ready = Mock(return_value={'status': 'ok'})
    monkeypatch.setattr(control, 'systemctl', systemctl)
    monkeypatch.setattr(control, 'wait_until_ready', ready)
    assert control.restart() == {'status': 'ok'}
    systemctl.assert_called_once_with('restart', 'fixture.service')
    ready.assert_called_once_with()
    assert 'systemd' in caplog.text
    if failed_path == 'status':
        assert paths == ['/api/v1/status'], 'do not drain an unresponsive worker'


def test_restart_does_not_treat_authentication_failure_as_an_unresponsive_server(tmp_path, monkeypatch):
    import httpx
    from unittest.mock import Mock

    control = HarnessControl(tmp_path)
    def request(method, path, **kwargs):
        response = httpx.Response(403, request=httpx.Request(method, 'http://localhost' + path))
        response.raise_for_status()
    monkeypatch.setattr(control, 'request', request)
    systemctl = Mock()
    monkeypatch.setattr(control, 'systemctl', systemctl)
    with pytest.raises(httpx.HTTPStatusError):
        control.restart()
    systemctl.assert_not_called()
