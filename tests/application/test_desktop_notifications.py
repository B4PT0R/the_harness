import asyncio
import json

from the_harness.plugins.desktop_notifications.service import DesktopNotificationService


class Application:
    connected = False


class Sender:
    available = True

    def __init__(self):
        self.messages = []

    async def __call__(self, **message):
        self.messages.append(message)
        return True


def test_desktop_notification_is_only_delivered_while_local_ui_is_closed(tmp_path):
    async def run():
        application = Application()
        sender = Sender()
        service = DesktopNotificationService(
            tmp_path / "desktop-notifications.json", application, sender=sender,
        )

        await service.notify("closed-message")
        application.connected = True
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
        service = DesktopNotificationService(path, Application(), sender=sender)
        assert service.update(False)["enabled"] is False
        assert json.loads(path.read_text())["enabled"] is False
        assert path.stat().st_mode & 0o777 == 0o600

        restarted = DesktopNotificationService(path, Application(), sender=sender)
        await restarted.notify("ignored")
        return restarted.snapshot(), sender.messages

    snapshot, messages = asyncio.run(run())
    assert snapshot == {
        "enabled": False,
        "available": True,
        "delivery": "host_desktop",
    }
    assert messages == []
