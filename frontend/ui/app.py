"""AsynxDL — application entrypoint/root + tray.

Brutalist W98: kompak, square, kein sidebar. Logo berasal dari
C:\\Users\\asynx\\Downloads\\AsynxDL\\Logo.png atau fallback ke icon lokal.
"""

import os
import threading
import tkinter as tk

import customtkinter as ctk

from frontend.ui import theme
from frontend.ui.api_client import APIClient
from frontend.ui.i18n import set_language, t
from frontend.ui.windows.main_window import MainWindow
from backend.system.config import load_config
from backend.system.tray import TrayIcon


_LOCAL_LOGO_CANDIDATE = r"C:\Users\asynx\Downloads\AsynxDL\Logo.png"


class AsynxDLApp:
    """Aplikasi desktop AsynxDL dengan CustomTkinter + System Tray."""

    def __init__(self, root=None, minimized=False):
        if root is None:
            self._root = ctk.CTk()
        else:
            self._root = root
        self._root.title(t("app.title"))

        config = load_config()
        lang = config.get("language", "en")
        theme_mode = config.get("theme", "light")
        if theme_mode not in ("light", "dark"):
            theme_mode = "light"
        self._theme_mode = theme_mode
        set_language(lang)
        ctk.set_appearance_mode(theme_mode)
        ctk.set_default_color_theme("dark-blue")  # tidak dipakai (kita pakai token sendiri)

        # Center window
        theme.apply_window_geometry(self._root, width=1080, height=720)

        # Use Arial as default safe Windows font
        try:
            self._root.option_add("*Font", "Arial")
        except tk.TclError:
            pass

        self._api = APIClient()
        self._main = MainWindow(self._root, self._api)
        self._main.pack(fill="both", expand=True)

        self._tray_icon: TrayIcon | None = None
        self._setup_window_behavior()

        # Defer icon load
        if not minimized:
            try:
                self._root.after(30, self._load_icon)
            except Exception:
                pass
        else:
            self._load_icon()

        if minimized:
            self._root.withdraw()

    # ------------------------------------------------------------------ icon

    def _load_icon(self) -> None:
        """Load window + taskbar icon konsisten dengan Logo.png.

        Prioritas:
        1. `frontend/ui/assets/icons/app.ico` (sama file yang dipakai PyInstaller
           untuk embed Windows resource ke .exe).
        2. `Logo.png` mentah via PIL+ImageTk.PhotoImage → wm_iconphoto.
        3. Log kalau tidak ada yang ditemukan.
        """
        icon_path = os.path.join(
            os.path.dirname(__file__), "assets", "icons", "app.ico"
        )
        if os.path.exists(icon_path):
            try:
                self._root.iconbitmap(icon_path)
                return
            except Exception as exc:
                print(f"[AsynxDLApp] iconbitmap {icon_path} failed: {exc}")

        try:
            from PIL import Image, ImageTk
            for path in (
                _LOCAL_LOGO_CANDIDATE,
                os.path.join(os.path.dirname(__file__), "assets", "icons", "logo.png"),
                os.path.join(os.path.dirname(__file__), "assets", "icons", "logo.jpg"),
                os.path.join(os.path.dirname(__file__), "assets", "icons", "tray.png"),
            ):
                if path and os.path.exists(path):
                    img = Image.open(path)
                    img_tk = ImageTk.PhotoImage(img)
                    self._root.wm_iconphoto(True, img_tk)
                    return
            print("[AsynxDLApp] icon: no app.ico / no Logo.png found")
        except Exception as exc:
            print(f"[AsynxDLApp] icon load failed: {exc}")

    # ------------------------------------------------------------------ tray

    def _setup_window_behavior(self) -> None:
        self._root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

    def _hide_to_tray(self) -> None:
        active = self._count_active_downloads()
        if active > 0:
            self._notify_tray(
                title="AsynxDL — download masih berjalan",
                message=f"{active} download aktif di background. Klik tray icon untuk membuka lagi.",
            )
        self._root.withdraw()
        if not self._tray_icon:
            self._tray_icon = TrayIcon(self)
            self._tray_icon.set_state_provider(self._tray_state)
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        try:
            self._tray_icon.update_state()
        except Exception:
            pass

    def _count_active_downloads(self) -> int:
        try:
            n = 0
            for card in getattr(self._main, "_home_panel")._cards.values():
                if getattr(card, "_status", "") in ("DOWNLOADING", "PENDING"):
                    n += 1
            return n
        except Exception:
            return 0

    def _tray_state(self) -> str:
        n = self._count_active_downloads()
        return "idle" if n == 0 else "active"

    def _notify_tray(self, title: str, message: str) -> None:
        def _do() -> None:
            try:
                if self._tray_icon is not None:
                    self._tray_icon.notify(title, message)
            except Exception:
                pass
        try:
            self._root.after(0, _do)
        except Exception:
            pass

    def show_window(self) -> None:
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()
        self._root.attributes("-topmost", True)
        self._root.after(300, lambda: self._root.attributes("-topmost", False))

    def hide_window(self) -> None:
        self._root.withdraw()

    def open_settings(self) -> None:
        self.show_window()
        try:
            self._main.open_settings()
        except Exception:
            pass

    def pause_all(self) -> None:
        try:
            for card in getattr(self._main, "_home_panel")._cards.values():
                if card._status in ("DOWNLOADING", "PENDING"):
                    threading.Thread(target=self._api.pause, args=(card._task_id,), daemon=True).start()
        except Exception:
            pass

    def shutdown_clean(self) -> None:
        try:
            self.pause_all()
            # 5.0s grace: allow chunk threads (up to 8 per download) to flush
            # their in-flight writes to .part files before app exits.
            threading.Event().wait(timeout=5.0)
        except Exception:
            pass

    def exit_app(self) -> None:
        try:
            if self._tray_icon is not None:
                self._tray_icon.stop()
        except Exception:
            pass
        try:
            self._root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        def _heartbeat() -> None:
            try:
                if self._tray_icon is not None:
                    self._tray_icon.update_state()
            except Exception:
                pass
            try:
                self._root.after(1500, _heartbeat)
            except Exception:
                return
        try:
            self._root.after(1500, _heartbeat)
        except Exception:
            pass
        self._root.mainloop()


def run_app(minimized: bool = False) -> None:
    app = AsynxDLApp(minimized=minimized)
    app.run()


if __name__ == "__main__":
    run_app()
