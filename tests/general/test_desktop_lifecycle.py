"""Real isolated daemons: no user data, model turns or browser windows."""

import os
import json

import pytest
import signal
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

import httpx

from the_framework.server.clients.browser_rpc import BrowserRPCClient, browser_socket_path
from the_framework.agent.context.session import Session
from the_framework.agent.models.responses import Message
from the_harness.control import HarnessControl
from the_harness.configuration import AgentConfigStore

ROOT = Path(__file__).parents[2]


@contextmanager
def daemon(module, machine, *args):
    env = {**os.environ, "THE_HARNESS_MACHINE_ROOT": str(machine)}
    with (machine / f"{module.rsplit('.', 1)[-1]}.log").open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", module, "--machine-root", str(machine), *args],
            cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=log, stderr=log,
            start_new_session=True,
        )
        try:
            yield process
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


def wait_for(process, probe, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert process.poll() is None, "isolated daemon exited; see fixture logs"
        if probe():
            return
        time.sleep(0.05)
    raise AssertionError("isolated daemon did not become ready; see fixture logs")


def test_two_instances_cold_start_restart_and_clean_shutdown(tmp_path):
    artifact = tmp_path / "ui"
    artifact.mkdir()
    (artifact / "index.html").write_text("<!doctype html><title>Isolated test</title>")
    roots = [tmp_path / name for name in ("first", "second")]
    for root in roots:
        root.mkdir()
        session = Session.open(root / "data/session.json")
        session.append(Message(role="user", content=[{"type": "input_text", "text": "Durable conversation marker"}]))
        session.save()
    controls = [HarnessControl(root) for root in roots]
    args = ("--ui-root", str(artifact), "--exit-on-parent-stdin-close")
    with ExitStack() as stack:
        browsers = [stack.enter_context(daemon("the_harness.browser_process", root)) for root in roots]
        for root, browser in zip(roots, browsers):
            wait_for(browser, lambda root=root: browser_socket_path(root).exists())
        servers = [stack.enter_context(daemon("the_harness.server_process", root, *args)) for root in roots]
        for control, server in zip(controls, servers):
            wait_for(server, lambda control=control: control.status().get("status") == "ok")
        descriptors = [control.descriptor.read() for control in controls]
        assert descriptors[0]["port"] != descriptors[1]["port"]
        assert descriptors[0]["token"] != descriptors[1]["token"]
        secrets = [(root / "runtime/ui-session.key").read_text() for root in roots]
        assert secrets[0] != secrets[1]
        for control in controls:
            assert control.request("GET", "/api/v1/surfaces")["surfaces"][0]["active"]
        # Credentials from one instance never authenticate with the other.
        response = httpx.get(
            f"http://127.0.0.1:{descriptors[1]['port']}/api/v1/health",
            headers={"Authorization": f"Bearer {descriptors[0]['token']}"}, timeout=2,
        )
        assert response.status_code == 401
        # A duplicate owner cannot remove or replace the running descriptor.
        duplicate = subprocess.run(
            [sys.executable, "-m", "the_harness.server_process", "--machine-root", str(roots[0]), *args],
            cwd=ROOT, capture_output=True, timeout=15,
        )
        assert duplicate.returncode != 0
        assert b"another server owns" in duplicate.stderr
        assert controls[0].descriptor.read() == descriptors[0]
        # Server replacement preserves the independent browser and UI credential.
        servers[0].stdin.close()
        assert servers[0].wait(timeout=15) == 0
        assert not controls[0].descriptor.path.exists()
        assert browsers[0].poll() is None
        assert browser_socket_path(roots[0]).exists()
        replacement = stack.enter_context(daemon("the_harness.server_process", roots[0], *args))
        wait_for(replacement, lambda: controls[0].status().get("status") == "ok")
        assert controls[0].descriptor.read()["token"] != descriptors[0]["token"]
        assert (roots[0] / "runtime/ui-session.key").read_text() == secrets[0]
        assert "Durable conversation marker" in json.dumps(controls[0].request("GET", "/api/v1/session"))
        assert controls[1].status()["status"] == "ok"
        replacement.terminate()
        assert replacement.wait(timeout=15) == 0
        assert not controls[0].descriptor.path.exists()
        assert browsers[0].poll() is None
        servers[1].send_signal(signal.SIGINT)
        assert servers[1].wait(timeout=15) == 0
        assert not controls[1].descriptor.path.exists()
    for root, control in zip(roots, controls):
        assert not control.descriptor.path.exists()
        assert not browser_socket_path(root).exists()


@pytest.mark.skipif(not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"),
                    reason="requires an explicitly configured Chromium installation")
def test_server_replacement_preserves_live_browser_cookie_and_draft(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("""<!doctype html><title>Loading</title>
<textarea aria-label="Draft"></textarea><button onclick="load()">Refresh history</button>
<h1 id="history"></h1><script>
document.title = crypto.randomUUID();
async function load() {
  document.querySelector('#history').textContent = 'Loading';
  const response = await fetch('/api/v1/session');
  document.querySelector('#history').textContent = response.ok && (await response.text()).includes('Recovered conversation') ? 'Recovered conversation' : 'Unauthorized';
}
load();
</script>""")
    machine = tmp_path / "machine"
    data = machine / "data"
    data.mkdir(parents=True)
    AgentConfigStore(data / "config.json").save({"chromium": {"ui_headless": True, "web_headless": True}})
    session = Session.open(data / "session.json")
    session.append(Message(role="user", content=[{"type": "input_text", "text": "Recovered conversation"}]))
    session.save()
    control = HarnessControl(machine)
    rpc = BrowserRPCClient(browser_socket_path(machine))
    args = ("--ui-root", str(ui), "--exit-on-parent-stdin-close")
    with ExitStack() as stack:
        browser = stack.enter_context(daemon("the_harness.browser_process", machine))
        wait_for(browser, lambda: browser_socket_path(machine).exists())
        server = stack.enter_context(daemon("the_harness.server_process", machine, *args))
        wait_for(server, lambda: control.status().get("status") == "ok")
        descriptor = control.descriptor.read()
        assert control.request("POST", "/api/v1/ui/open")["status"] == "opened"

        def observe():
            return rpc.call("observe", "harness_ui", str(tmp_path / "browser.png"))[0]

        wait_for(browser, lambda: "Recovered conversation" in json.dumps(observe()))
        snapshot = observe()
        field = next(item for item in snapshot["elements"] if item["name"] == "Draft")
        rpc.session_call("harness_ui", "fill", field["id"], "Unsent draft")
        before = rpc.session_call("harness_ui", "status")
        link = control.request('POST', '/api/v1/surfaces/main/preview')['url']
        rpc.call('open_web', link, new_tab=True)
        def preview():
            return rpc.call('observe', 'web', str(tmp_path / 'preview.png'))[0]
        wait_for(browser, lambda: 'Recovered conversation' in json.dumps(preview()))
        assert rpc.session_call('harness_ui', 'status') == before
        principal_snapshot = observe()
        principal_field = next(item for item in principal_snapshot['elements'] if item['name'] == 'Draft')
        assert principal_field['value'] == 'Unsent draft'
        server.stdin.close()
        assert server.wait(timeout=15) == 0
        assert browser.poll() is None
        replacement = stack.enter_context(daemon(
            "the_harness.server_process", machine, *args, "--port", str(descriptor["port"]),
        ))
        wait_for(replacement, lambda: control.status().get("status") == "ok")
        assert control.descriptor.read()["token"] != descriptor["token"]
        assert rpc.session_call("harness_ui", "status") == before
        snapshot = observe()
        field = next(item for item in snapshot["elements"] if item["name"] == "Draft")
        assert field["value"] == "Unsent draft"
        refresh = next(item for item in snapshot["elements"] if item["name"] == "Refresh history")
        rpc.session_call("harness_ui", "click", refresh["id"])
        wait_for(browser, lambda: "Recovered conversation" in json.dumps(observe()))
        assert "Unauthorized" not in json.dumps(observe())
        preview_snapshot = preview()
        refresh_preview = next(item for item in preview_snapshot['elements'] if item['name'] == 'Refresh history')
        rpc.session_call('web', 'click', refresh_preview['id'])
        wait_for(browser, lambda: 'Recovered conversation' in json.dumps(preview()))
        assert 'Unauthorized' not in json.dumps(preview())
