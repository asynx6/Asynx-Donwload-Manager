"""
AsynxDL — Confirm Dialog
~~~~~~~~~~~~~~~~~~~~~~~~~
Dialog reusable untuk "Yakin?" — konsisten dengan tema CustomTkinter
AsynxDL (dark blue + danger styling untuk delete).

Pakai:

    if not ask_yes_no(parent, title="Hapus download?", message="..."):
        return
    # ... proceed

    if not ask_yes_no(parent, title="Hapus dari Riwayat?",
                      message="...", danger=True):
        return
"""

from typing import Optional

import customtkinter as ctk


# Theming konsisten dengan AsynxDL.
_BG = ("#FFFFFF", "#18181E")
_FG_PRIMARY = ("#111827", "#F9FAFB")
_FG_SECONDARY = ("#6B7280", "#9CA3AF")
_ACCENT = ("#6366F1", "#818CF8")
_DANGER = ("#DC2626", "#FCA5A5")
_DANGER_BG = ("#FEE2E2", "#3F1818")
_DANGER_HOVER = ("#FECACA", "#522424")


def ask_yes_no(
    parent,
    title: str,
    message: str,
    yes_label: str = "Yes",
    no_label: str = "No",
    danger: bool = False,
) -> bool:
    """Tampilkan modal Yes/No dialog dan tunggu jawaban.

    Returns True kalau user klik Yes, False kalau No / close window.
    Aman dipakai dari main thread Tk (menggunakan wait_window).
    """
    dlg = ConfirmDialog(
        parent,
        title=title,
        message=message,
        yes_label=yes_label,
        no_label=no_label,
        danger=danger,
    )
    parent.wait_window(dlg)
    return dlg.result


class ConfirmDialog(ctk.CTkToplevel):
    """Modal Yes/No dialog reusable."""

    def __init__(
        self,
        parent,
        title: str,
        message: str,
        yes_label: str = "Yes",
        no_label: str = "No",
        danger: bool = False,
    ):
        super().__init__(parent, fg_color=_BG)
        self.title(title)
        self.result: bool = False
        self.resizable(False, False)
        self.attributes("-topmost", True)
        try:
            self.transient(parent)
            self.grab_set()
            self.lift()
            self.focus_force()
        except Exception:
            pass

        # Layout: title + message + buttons
        width, height = 420, 200
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - width) // 2
            y = (screen_h - height) // 2
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            self.geometry(f"{width}x{height}")

        # Title bar (large)
        ctk.CTkLabel(
            self, text=title, font=("Arial", 16, "bold"),
            text_color=_FG_PRIMARY, anchor="w",
        ).pack(fill="x", padx=20, pady=(20, 6))

        # Message body
        ctk.CTkLabel(
            self, text=message, font=("Arial", 12),
            text_color=_FG_SECONDARY, anchor="w", justify="left",
            wraplength=380,
        ).pack(fill="x", padx=20, pady=(0, 14))

        # Buttons row
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        if danger:
            yes_color, yes_hover = _DANGER_BG, _DANGER_HOVER
            yes_text = _DANGER
        else:
            yes_color = ("#E0E7FF", "#312E81")
            yes_hover = ("#C7D2FE", "#3730A3")
            yes_text = _ACCENT

        # No button (left)
        ctk.CTkButton(
            btn_frame, text=no_label, width=160, height=36,
            corner_radius=10, font=("Arial", 12, "bold"),
            fg_color=("#E5E7EB", "#27272A"), text_color=_FG_PRIMARY,
            hover_color=("#D1D5DB", "#3F3F46"),
            command=self._on_no,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        # Yes button (right)
        ctk.CTkButton(
            btn_frame, text=yes_label, width=160, height=36,
            corner_radius=10, font=("Arial", 12, "bold"),
            fg_color=yes_color, text_color=yes_text,
            hover_color=yes_hover,
            command=self._on_yes,
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        # Keyboard bindings
        self.bind("<Return>", lambda _e: self._on_yes())
        self.bind("<Escape>", lambda _e: self._on_no())

        # Cleanup kalau window dihancurkan paksa
        self.protocol("WM_DELETE_WINDOW", self._on_no)
        self.after(50, lambda: self.focus_force())

    def _on_yes(self) -> None:
        self.result = True
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _on_no(self) -> None:
        self.result = False
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
