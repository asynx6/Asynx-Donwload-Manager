import os
import sys
import threading
import tkinter as tk
import customtkinter as ctk

from frontend.ui.api_client import APIClient
from frontend.ui.i18n import set_language, t
from frontend.ui.windows.main_window import MainWindow
from backend.system.config import load_config
from backend.system.tray import TrayIcon


class AsynxDLApp:
    """Aplikasi desktop AsynxDL dengan CustomTkinter + System Tray."""

    def __init__(self, minimized=False):
        self._root = ctk.CTk()
        self._root.title(t("app.title"))
        self._root.geometry("1000x680")
        self._root.minsize(860, 560)

        config = load_config()
        lang = config.get("language", "en")
        theme = config.get("theme", "dark")
        set_language(lang)
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("dark-blue")

        # Center window on screen
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        w, h = 1000, 680
        x = (sw - w) // 2
        y = (sh - h) // 2
        self._root.geometry(f"{w}x{h}+{x}+{y}")

        # Use Arial as the default safe Windows font
        try:
            self._root.option_add("*Font", "Arial")
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
        self._root.attributes("-topmost", True)
        self._root.after(300, lambda: self._root.attributes("-topmost", False))

    def hide_window(self):
        self._root.withdraw()

    def open_settings(self):
        self.show_window()
        self._main._show_settings()

    def pause_all(self):
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
