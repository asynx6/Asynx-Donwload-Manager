"""
AsynxDL — System Tray Icon
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integrasi pystray untuk minimize to tray.
"""

import os
import threading
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from frontend.ui.app import AsynxDLApp


class TrayIcon:
    """System tray icon untuk AsynxDL."""

    def __init__(self, app: "AsynxDLApp"):
        self._app = app
        self._icon = None
        self._running = False

    def _create_image(self, width=64, height=64) -> Image.Image:
        """Generate ikon tray sederhana (biru dengan panah bawah)."""
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        # Background circle
        dc.ellipse([4, 4, width - 4, height - 4], fill=(91, 107, 248, 255))
        # Arrow down
        arrow_x = width // 2
        arrow_top = 18
        arrow_bottom = 46
        dc.line([(arrow_x, arrow_top), (arrow_x, arrow_bottom)], fill="white", width=6)
        dc.polygon([(arrow_x - 10, arrow_bottom - 10), (arrow_x + 10, arrow_bottom - 10), (arrow_x, arrow_bottom)], fill="white")
        return image

    def _load_icon(self) -> Image.Image:
        paths = [
            os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "tray.png"),
            os.path.join(os.path.dirname(__file__), "..", "frontend", "ui", "assets", "icons", "tray.png"),
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    return Image.open(p)
                except Exception:
                    pass
        return self._create_image()

    def _build_menu(self):
        import pystray
        return pystray.Menu(
            pystray.MenuItem("Show AsynxDL", self._show),
            pystray.MenuItem("Pause All", self._pause_all),
            pystray.MenuItem("Settings", self._settings),
            pystray.MenuItem("Exit", self._exit),
        )

    def _show(self, icon=None, item=None):
        self._app._root.after(0, self._app.show_window)

    def _pause_all(self, icon=None, item=None):
        threading.Thread(target=self._app.pause_all, daemon=True).start()

    def _settings(self, icon=None, item=None):
        self._app._root.after(0, self._app.open_settings)

    def _exit(self, icon=None, item=None):
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
        self._app._root.after(0, self._app.exit_app)

    def run(self):
        import pystray
        self._running = True
        self._icon = pystray.Icon(
            "AsynxDL", self._load_icon(), "AsynxDL", self._build_menu()
        )
        self._icon.run()

    def stop(self):
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
