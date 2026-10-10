import asyncio
import json

from the_harness.plugins.desktop_notifications.service import DesktopNotificationService


class Transport:
    event_connection_count = 0


class Sender:
    available = True

    def __init__(self):
        self.messages = []

    async def __call__(self, **message):
        self.messages.append(message)
        return True


def test_desktop_notification_is_only_delivered_while_local_ui_is_closed(tmp_path):
    async def run():
        transport = Transport()
        sender = Sender()
        service = DesktopNotificationService(
            tmp_path / "desktop-notifications.json", transport, sender=sender,
        )

        await service.notify("closed-message")
        transport.event_connection_count = 1
        await service.notify("visible-message")
        return sender.messages

    assert asyncio.run(run()) == [{
        "title": "The Harness",
        "body": "Ton assistant t’a envoyé un message",
    }]


def test_desktop_notification_preference_is_persisted_and_disables_delivery(tmp_path):
    async def run():
        path = tmp_path / "desktop-notifications.json"
        sender = Sender()
        service = DesktopNotificationService(path, Transport(), sender=sender)
        assert service.update(False)["enabled"] is False
        assert json.loads(path.read_text())["enabled"] is False
        assert path.stat().st_mode & 0o777 == 0o600

        restarted = DesktopNotificationService(path, Transport(), sender=sender)
        await restarted.notify("ignored")
        return restarted.snapshot(), sender.messages

    snapshot, messages = asyncio.run(run())
    assert snapshot == {
        "enabled": False,
        "available": True,
        "delivery": "host_desktop",
    }
    assert messages == []


def test_real_event_sockets_suppress_only_local_host_notifications(tmp_path):
    from starlette.testclient import TestClient
    from the_framework.server.runtime.supervisor import WorkerSupervisor
    from the_harness.app import create_app
    from the_harness.runtime_composition import EVENT_SUBPROTOCOL, REMOTE_EVENT_SUBPROTOCOL

    app = create_app(WorkerSupervisor(tmp_path / "session.json"), token="local",
                     browser_token="browser", browser_runtime_root=tmp_path,
                     client_remote_root=tmp_path)
    extensions = app.state.application.server_extensions
    transport = extensions["canonical_transport"].service
    notifications = extensions["desktop_notifications"].service
    remote = extensions["client_remote"].service
    assert notifications.transport is transport
    assert remote.message_notification_listener == notifications.notify
    sender = Sender()
    notifications.sender = sender
    _phone, token = remote.clients.issue("phone", platform="android")
    client = TestClient(app, base_url="http://127.0.0.1:48887")
    headers = {"Host": "127.0.0.1:48887", "Origin": "http://127.0.0.1:48887"}
    with client.websocket_connect("/remote/v1/events", headers=dict(headers),
                                  subprotocols=[REMOTE_EVENT_SUBPROTOCOL, token]) as phone:
        assert transport.event_connection_count == 0
        assert remote.event_connections
        phone.portal.call(notifications.notify, "remote-only")
        assert len(sender.messages) == 1
        with client.websocket_connect("/api/v1/events", headers=dict(headers),
                                      subprotocols=[EVENT_SUBPROTOCOL, "local"]) as local:
            assert transport.event_connection_count == 1
            assert not extensions["runtime"].service.application.connected
            local.portal.call(notifications.notify, "local-open")
            assert len(sender.messages) == 1
        assert transport.event_connection_count == 0
        phone.portal.call(notifications.notify, "local-closed")
        assert len(sender.messages) == 2
    assert not remote.event_connections
