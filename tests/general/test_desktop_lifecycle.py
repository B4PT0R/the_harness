"""Real isolated daemons: no user data, model turns or browser windows."""

import os
import signal
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

import httpx

from the_framework.server.clients.browser_rpc import browser_socket_path
from the_harness.control import HarnessControl

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
