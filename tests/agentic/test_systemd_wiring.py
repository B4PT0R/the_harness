"""Feedback on the current systemd wiring; readiness behavior is in general."""

from configparser import ConfigParser
from pathlib import Path

def test_server_orders_initial_ui_build_before_surface_adoption():
    root = Path(__file__).parents[2] / "packaging/systemd"
    server, browser, tray = [ConfigParser(interpolation=None, strict=False) for _ in range(3)]
    server.read(root / "the-harness.service.in")
    browser.read(root / "the-harness-browser.service.in")
    tray.read(root / "the-harness-tray.service.in")
    assert "the-harness-ui.service" in server["Unit"]["After"].split()
    assert "the-harness-ui.service" in server["Unit"]["Wants"].split()
    assert "the-harness-browser.service" not in server["Unit"]["Wants"].split()
    assert "graphical-session.target" not in server["Unit"]["After"].split()
    assert browser["Install"]["WantedBy"] == "graphical-session.target"
    assert browser["Service"]["KillMode"] == server["Service"]["KillMode"] == "mixed"
    assert int(browser["Service"]["TimeoutStopSec"]) > 30
    assert "the-harness-browser.service" in tray["Unit"]["Wants"].split()
    assert "the-harness.service" not in browser["Unit"].get("PartOf", "").split()
    assert "the-harness.service" in tray["Unit"]["Requires"].split()
