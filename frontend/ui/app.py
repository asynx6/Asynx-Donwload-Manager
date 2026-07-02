import os
import sys
import threading
import tkinter as tk
import customtkinter as ctk

from frontend.ui.api_client import APIClient
from frontend.ui.i18n import set_language, t
from frontend.ui.windows.main_window import MainWindow
from backend.system.config import load_config, update_config, mark_first_run_completed
from backend.system.tray import TrayIcon


class AsynxDLApp:
    """Aplikasi desktop AsynxDL dengan CustomTkinter + System Tray."""

    def __init__(self, minimized=False):
        self._root = ctk.CTk()
        self._root.title("AsynxDL")
        self._root.geometry("900x620")
        self._root.minsize(760, 480)

        config = load_config()
        lang = config.get("language", "en")
        theme = config.get("theme", "light")
        set_language(lang)
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")

        # Default font Inter jika tersedia, fallback Segoe UI
        try:
            self._root.option_add("*Font", "Inter")
        except tk.TclError:
            pass

        self._api = APIClient()
        self._main = MainWindow(self._root, self._api)
        self._main.pack(fill="both", expand=True)

        self._tray_icon: TrayIcon | None = None
        self._setup_window_behavior()
        self._load_icon()

        if minimized:
            self._root.withdraw()

    def _load_icon(self):
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "app.ico")
            if os.path.exists(icon_path):
                self._root.iconbitmap(icon_path)
        except Exception:
            pass

    def _setup_window_behavior(self):
        self._root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

    def _hide_to_tray(self):
        self._root.withdraw()
        if not self._tray_icon:
            self._tray_icon = TrayIcon(self)
            threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def show_window(self):
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()

    def hide_window(self):
        self._root.withdraw()

    def open_settings(self):
        self.show_window()
        self._main._show_settings()

    def pause_all(self):
        # Pause semua task via UI
        for card in self._main._cards.values():
            if card._status in ("DOWNLOADING", "PENDING"):
                threading.Thread(target=self._api.pause, args=(card._task_id,), daemon=True).start()

    def exit_app(self):
        self._root.destroy()

    def run(self):
        self._root.mainloop()


def run_app(minimized=False):
    app = AsynxDLApp(minimized=minimized)
    app.run()


if __name__ == "__main__":
    run_app()
