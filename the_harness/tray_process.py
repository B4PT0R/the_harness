"""Independent AppIndicator tray client for the persistent Harness server."""

from __future__ import annotations

import os
import site
import threading
from pathlib import Path

from .control import HarnessControl


def expose_system_gi():
    """Expose distro GI bindings to isolated Python environments.

    PyGObject is intentionally supplied by the OS because it is coupled to the
    installed AppIndicator libraries. Virtual environments and the packaged
    dependency directory do not always inherit Debian's dist-packages path.
    """
    for candidate in (
        Path("/usr/lib/python3/dist-packages"),
        Path("/usr/local/lib/python3/dist-packages"),
    ):
        if candidate.is_dir():
            site.addsitedir(str(candidate))


def tray_icon_path():
    configured = os.environ.get("THE_HARNESS_TRAY_ICON")
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path(__file__).parents[1] / "assets" / "assistant.png",
    ]
    return next((path for path in candidates if path is not None and path.is_file()), None)


class TrayApplication:
    def __init__(self, *, control=None, icon_factory=None, image_loader=None):
        self.control = control or HarnessControl()
        self.icon_factory = icon_factory
        self.image_loader = image_loader
        self.icon = None
        self.last_error = None

    def _background(self, operation):
        def run():
            try:
                operation()
                self.last_error = None
            except Exception as error:  # tray must remain available for recovery
                self.last_error = str(error)
            finally:
                if self.icon is not None:
                    self.icon.update_menu()

        threading.Thread(target=run, daemon=True, name="harness-tray-action").start()

    def run(self):
        os.environ.setdefault("PYSTRAY_BACKEND", "appindicator")
        if self.icon_factory is None or self.image_loader is None:
            expose_system_gi()
            import pystray
            from PIL import Image as PillowImage

            self.icon_factory = pystray.Icon
            self.image_loader = PillowImage.open
            menu = pystray.Menu(
                pystray.MenuItem(
                    "Ouvrir The Harness",
                    lambda *_args: self._background(self.control.open),
                    default=True,
                ),
                pystray.MenuItem(
                    "Redémarrer le serveur",
                    lambda *_args: self._background(self.control.restart),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    lambda _item: self.last_error or "Serveur local actif",
                    None,
                    enabled=False,
                ),
                pystray.MenuItem("Arrêter The Harness", self._stop),
            )
        else:
            menu = None
        path = tray_icon_path()
        if path is None:
            raise RuntimeError("The Harness tray icon is unavailable")
        image = self.image_loader(path)
        self.icon = self.icon_factory("the-harness", image, "The Harness", menu)
        self.icon.run()

    def _stop(self, *_args):
        icon = self.icon

        def stop():
            try:
                self.control.stop()
            finally:
                if icon is not None:
                    icon.stop()

        self._background(stop)


def main():
    TrayApplication().run()


if __name__ == "__main__":
    main()
