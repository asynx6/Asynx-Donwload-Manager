"""
AsynxDL — System Tray Icon
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integrasi pystray untuk minimize to tray.

Fitur v1.0.1:
- Ikon berubah antara IDLE (abu) dan ACTIVE (hijau) ketika ada
  download yang sedang berjalan.
- Toast balloon "Download masih berjalan" saat user klik close.
- Menu Quit AsynxDL dengan pause_all sebelum exit.
- Thread-safe (icon update dipanggil dari main loop via callback).
"""

import os
import threading
from typing import TYPE_CHECKING, Optional, Callable

from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from frontend.ui.app import AsynxDLApp


# Saturation indicator colors
_TRAY_COLORS = {
    "idle": (91, 107, 248, 255),       # brand blue (downloads idling)
    "active": (50, 200, 90, 255),      # green = ada download berjalan
    "blocked": (220, 80, 70, 255),     # red = ada task errored/paused
}


class TrayIcon:
    """System tray icon untuk AsynxDL dengan indikator state."""

    def __init__(self, app: "AsynxDLApp"):
        self._app = app
        self._icon = None
        self._running = False
        self._state_lock = threading.Lock()
        self._state = "idle"
        # Optional callback untuk ambil active_count dari app
        self._state_provider: Optional[Callable[[], str]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_state_provider(self, provider: Callable[[], str]) -> None:
        """Register callback that returns 'idle' | 'active' | 'blocked'.

        Dipakai oleh AsynxDLApp._refresh_active_state() untuk update
        icon tray secara berkala (mis. tiap 1.5s sekali dari main loop).
        """
        self._state_provider = provider

    def update_state(self, new_state: Optional[str] = None) -> None:
        """Ganti state ikon (idle/active/blocked) secara thread-safe."""
        if new_state is None and self._state_provider is not None:
            try:
                new_state = self._state_provider()
            except Exception:
                new_state = "idle"
        if new_state not in _TRAY_COLORS:
            new_state = "idle"
        with self._state_lock:
            if new_state == self._state:
                return
            self._state = new_state
            icon = self._icon
        if icon is not None:
            try:
                from PIL import Image as _Im
                icon.icon = self._build_state_icon(new_state)
            except Exception:
                pass

    def notify(self, title: str, message: str) -> None:
        """Tampilkan toast balloon Windows di tray."""
        icon = self._icon
        if icon is None:
            return
        # pystray 0.19+: notify() jika didukung; fallback silent.
        try:
            icon.notify(message, title)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Image builders
    # ------------------------------------------------------------------
    def _build_state_icon(self, state: str, width=64, height=64) -> Image.Image:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        # Background circle dengan color sesuai state
        bg = _TRAY_COLORS.get(state, _TRAY_COLORS["idle"])
        dc.ellipse([4, 4, width - 4, height - 4], fill=bg)
        # Arrow down
        arrow_x = width // 2
        arrow_top = 18
        arrow_bottom = 46
        dc.line([(arrow_x, arrow_top), (arrow_x, arrow_bottom)], fill="white", width=6)
        dc.polygon([
            (arrow_x - 10, arrow_bottom - 10),
            (arrow_x + 10, arrow_bottom - 10),
            (arrow_x, arrow_bottom),
        ], fill="white")
        # Banner merah di atas kalau ada task errored
        if state == "blocked":
            dc.polygon([
                (width - 18, 6), (width - 6, 6),
                (width - 6, 14), (width - 12, 14),
            ], fill=(220, 80, 70, 255))
        return image

    def _create_image(self) -> Image.Image:
        return self._build_state_icon(self._state)

    def _load_icon(self) -> Image.Image:
        paths = [
            os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "tray.png"),
            os.path.join(os.path.dirname(__file__), "..", "frontend", "ui", "assets", "icons", "tray.png"),
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    return Image.open(p).convert("RGBA")
                except Exception:
                    pass
        # Optionally overlay with state color
        img = self._create_image()
        return img

    def _build_menu(self):
        import pystray
        return pystray.Menu(
            pystray.MenuItem("Show AsynxDL", self._show, default=True),
            pystray.MenuItem("Pause All Download", self._pause_all),
            pystray.MenuItem("Settings", self._settings),
            pystray.MenuItem(
                "Quit AsynxDL",
                self._exit,
            ),
        )

    def _show(self, icon=None, item=None):
        try:
            self._app._root.after(0, self._app.show_window)
        except Exception:
            pass

    def _pause_all(self, icon=None, item=None):
        threading.Thread(target=self._app.pause_all, daemon=True).start()

    def _settings(self, icon=None, item=None):
        try:
            self._app._root.after(0, self._app.open_settings)
        except Exception:
            pass

    def _exit(self, icon=None, item=None):
        """Quit AsynxDL: pause semua download dulu supaya tidak orphan
        chunk, lalu stop tray dan exit app."""
        try:
            threading.Thread(target=self._app.shutdown_clean, daemon=True).start()
        except Exception:
            pass
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
        try:
            self._app._root.after(0, self._app.exit_app)
        except Exception:
            pass

    def run(self):
        import pystray
        self._running = True
        self._icon = pystray.Icon(
            "AsynxDL",
            self._load_icon(),
            "AsynxDL",
            self._build_menu(),
        )
        self._icon.run()

    def stop(self):
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
