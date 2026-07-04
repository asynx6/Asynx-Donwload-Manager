"""AsynxDL — Offline & Error UI banner + transient toast.

Spesifikasi v1.1.0:
- BannerConnection: header tipis di atas list HomePanel, otomatis
  show/hide saat backend nggak merespons atau kembali online.
- Toast: transient notification square Brutalist untuk event penting
  (mis. 'Restart diperlukan', 'Theme disimpan', dll).

Pakai ``tk.CTkFrame`` Brutalist — square, mono-grey, tanpa rounded badge.
"""

from typing import Callable

import customtkinter as ctk

from frontend.ui import theme


class ConnectionBanner(ctk.CTkFrame):
    """Banner tipis di HomePanel yang menampilkan status backend live.

    State machine:
        online   -> hidden (grid_forget)
        offline  -> tampil "⚠ Backend Offline" mono-grey border
        retrying -> tampil "⟳ Connecting..." anim ping-pong fill

    Refresh via set_state() dipanggil dari Home tiap poll/release.
    """

    def __init__(self, master, mode: str = "light", **kwargs):
        tk = theme.tokens(mode)
        super().__init__(master, fg_color=tk["BG3"], corner_radius=theme.CORNER_NONE,
                         border_width=1, border_color=tk["BORDER2"], **kwargs)
        self._mode = mode
        self._state = "online"
        self._tk = tk
        self._label = ctk.CTkLabel(
            self, text="", font=theme.font(10, bold=True),
            text_color=tk["FG2"], anchor="w")
        self._label.pack(side="left", fill="x", expand=True, padx=12, pady=4)
        self._icon = ctk.CTkLabel(
            self, text="", font=theme.font(10, bold=True),
            text_color=tk["FG"], anchor="e", width=20)
        self._icon.pack(side="right", padx=12, pady=4)
        # Default hidden
        try:
            self.grid_forget()
        except Exception:
            pass

    def set_state(self, state: str) -> None:
        state = (state or "").lower()
        tk = self._tk
        if state == self._state:
            return
        self._state = state
        if state == "online":
            try:
                self.grid_forget()
            except Exception:
                pass
            return
        if state == "offline":
            try:
                self._icon.configure(text="⚠")
                self._label.configure(text="Backend Offline — klik untuk retry",
                                      text_color=tk["ERROR"])
                self.configure(border_color=tk["BORDER2"])
                self.grid()
            except Exception:
                pass
            return
        if state == "retrying":
            try:
                self._icon.configure(text="⟳")
                self._label.configure(text="Menghubungkan Backend...",
                                      text_color=tk["FG2"])
                self.configure(border_color=tk["BORDER"])
                self.grid()
            except Exception:
                pass


class Toast(ctk.CTkToplevel):
    """Transient square Brutalist toast di pojok kanan bawah parent."""

    def __init__(self, parent, message: str, mode: str = "light",
                 duration_ms: int = 3000, level: str = "info"):
        tk = theme.tokens(mode)
        super().__init__(parent, fg_color=tk["BG3"], corner_radius=theme.CORNER_NONE,
                         border_width=1, border_color=tk["BORDER2"])
        self.title("")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self._mode = mode
        self._level = level
        self._duration = duration_ms
        self._tk = tk

        bar_color = tk["BORDER2"] if level == "info" else tk["ERROR"]
        ctk.CTkLabel(
            self, text=message, font=theme.font(11, bold=True),
            text_color=tk["FG"], fg_color="transparent",
            anchor="w", justify="left", wraplength=320,
        ).pack(padx=14, pady=8, fill="x")

        # Place bottom-right of parent
        try:
            parent.update_idletasks()
            px = parent.winfo_toplevel()
            sw = px.winfo_screenwidth()
            sh = px.winfo_screenheight()
            xx = px.winfo_x() + px.winfo_width() - 360
            yy = px.winfo_y() + px.winfo_height() - 90
            xx = max(0, min(sw - 360, xx))
            yy = max(0, min(sh - 90, yy))
            self.geometry(f"340x70+{xx}+{yy}")
        except Exception:
            self.geometry("340x70")
        # Border accent
        try:
            self.configure(border_color=bar_color, border_width=2)
        except Exception:
            pass

        try:
            self.after(self._duration, self._fade)
        except Exception:
            self.destroy()

    def _fade(self) -> None:
        try:
            self.destroy()
        except Exception:
            pass


def show_toast(parent, message: str, mode: str = "light",
               duration_ms: int = 3000, level: str = "info") -> Toast:
    """Helper factory — panggil dari UI untuk show transient toast."""
    try:
        toast = Toast(parent, message=message, mode=mode,
                      duration_ms=duration_ms, level=level)
        return toast
    except Exception as exc:
        print(f"[Toast] show failed: {exc}")
        return None


def when_idle(call: Callable) -> Callable:
    """Decorator helper: jalankan callback 1 kali 30ms setelah idle.

    Misalnya: refresh banner sesaat setelah add_download sekarang.
    """
    def wrap(self, *args, **kwargs):
        try:
            return self.after(30, lambda: call(self, *args, **kwargs))
        except Exception:
            try:
                return call(self, *args, **kwargs)
            except Exception:
                return None
    return wrap


__all__: list[str] = ["ConnectionBanner", "Toast", "show_toast", "when_idle"]
