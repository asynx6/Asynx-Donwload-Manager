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

    def __init__(self, root=None, minimized=False):
        if root is None:
            self._root = ctk.CTk()
        else:
            self._root = root
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
            from PIL import Image, ImageTk
            # Prefer the new Logo-based PNG if available
            for logo_name in ("logo.png", "tray.png"):
                logo_path = os.path.join(os.path.dirname(__file__), "assets", "icons", logo_name)
                if os.path.exists(logo_path):
                    img = Image.open(logo_path)
                    img_tk = ImageTk.PhotoImage(img)
                    self._root.wm_iconphoto(True, img_tk)
                    return
            # Fallback to the packaged .ico
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "app.ico")
            if os.path.exists(icon_path):
                self._root.iconbitmap(icon_path)
        except Exception:
            pass

    def _setup_window_behavior(self):
        self._root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

    def _hide_to_tray(self):
        # Balloon notify kalau ada download sedang berjalan.
        active = self._count_active_downloads()
        if active > 0:
            self._notify_tray(
                title="AsynxDL — download masih berjalan",
                message=f"{active} download aktif di background. "
                        f"Klik tray icon untuk membuka lagi.",
            )
        self._root.withdraw()
        if not self._tray_icon:
            self._tray_icon = TrayIcon(self)
            self._tray_icon.set_state_provider(self._tray_state)
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        # Update icon saat pertama hide
        try:
            self._tray_icon.update_state()
        except Exception:
            pass

    def _count_active_downloads(self) -> int:
        """Hitung download yang DOWNLOADING/PENDING di MainWindow."""
        try:
            n = 0
            for card in getattr(self._main, "_cards", {}).values():
                if getattr(card, "_status", "") in ("DOWNLOADING", "PENDING"):
                    n += 1
            return n
        except Exception:
            return 0

    def _tray_state(self) -> str:
        n = self._count_active_downloads()
        if n == 0:
            return "idle"
        # Future: kalau ada task ERRORED, return "blocked". Untuk
        # sekarang aktif = aktif ≥1.
        return "active"

    def _notify_tray(self, title: str, message: str) -> None:
        """Kirim balloon ke tray icon — di thread-safe (after(0,...))."""
        def _do():
            try:
                if self._tray_icon is not None:
                    self._tray_icon.notify(title, message)
            except Exception:
                pass
        try:
            self._root.after(0, _do)
        except Exception:
            pass

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
        try:
            self._main._show_settings()
        except Exception:
            pass

    def pause_all(self):
        for card in getattr(self._main, "_cards", {}).values():
            if card._status in ("DOWNLOADING", "PENDING"):
                threading.Thread(target=self._api.pause, args=(card._task_id,), daemon=True).start()

    def shutdown_clean(self):
        """Pause semua download dulu supaya chunk tidak orphan saat
        proses exit. Dipakai dari menu tray Quit."""
        try:
            self.pause_all()
            # Tiny grace supaya pause thread sempat jalan.
            threading.Event().wait(timeout=0.5)
        except Exception:
            pass

    def exit_app(self):
        try:
            if self._tray_icon is not None:
                self._tray_icon.stop()
        except Exception:
            pass
        try:
            self._root.destroy()
        except Exception:
            pass

    def run(self):
        # Heartbeat supaya tray icon berubah status sesuai active count.
        def _heartbeat():
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


def run_app(minimized=False):
    app = AsynxDLApp(minimized=minimized)
    app.run()


if __name__ == "__main__":
    run_app()
