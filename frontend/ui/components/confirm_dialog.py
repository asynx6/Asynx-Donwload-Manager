"""AsynxDL — ConfirmDialog (Brutalist W98 mono-grey).

Modal reusable Yakin/Tidak — terpadu dengan tema app (kotak kaku, mono-grey).
Dipakai oleh download_card untuk pause/delete confirmation.

Contoh pakai:
    if not ask_yes_no(self.winfo_toplevel(), title="Hapus download?",
                      message="...", danger=True, mode=app_mode):
        return
"""
from typing import Optional  # noqa: F401  (kept for back-compat)

import customtkinter as ctk

from frontend.ui import theme


def ask_yes_no(
    parent,
    title: str,
    message: str,
    yes_label: str = "Yes",
    no_label: str = "No",
    danger: bool = False,
    mode: str = "light",
) -> bool:
    """Tampilkan modal yes/no Brutalist. Return True kalau user klik Yes."""
    dlg = ConfirmDialog(
        parent, title=title, message=message,
        yes_label=yes_label, no_label=no_label, danger=danger, mode=mode,
    )
    parent.wait_window(dlg)
    return dlg.result


class ConfirmDialog(ctk.CTkToplevel):
    """Brutalist yes/no modal — square edges, bordered, mono-grey."""

    def __init__(
        self,
        parent,
        title: str,
        message: str,
        yes_label: str = "Yes",
        no_label: str = "No",
        danger: bool = False,
        mode: str = "light",
    ):
        tk = theme.tokens(mode)
        super().__init__(parent, fg_color=tk["BG2"])
        self.title(title)
        self.result: bool = False
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._mode = mode
        try:
            self.transient(parent)
            self.grab_set()
            self.lift()
            self.focus_force()
        except Exception:
            pass

        # Geometry
        width, height = 440, 200
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 2}")
        except Exception:
            self.geometry(f"{width}x{height}")

        # Bordered card
        card = ctk.CTkFrame(self, fg_color=tk["BG3"], corner_radius=theme.CORNER_NONE,
                           border_width=1, border_color=tk["BORDER"])
        card.pack(fill="both", expand=True, padx=10, pady=10)
        card.grid_columnconfigure(0, weight=1)

        # Title — bold, with underline border
        title_border = ctk.CTkFrame(card, fg_color="transparent",
                                   corner_radius=theme.CORNER_NONE,
                                   border_width=1, border_color=tk["BORDER"])
        title_border.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        ctk.CTkLabel(title_border, text=title, font=theme.font(13, bold=True),
                    text_color=tk["FG"], anchor="w").pack(fill="x", padx=10, pady=8)

        # Body
        ctk.CTkLabel(card, text=message, font=theme.font(11), text_color=tk["FG2"],
                    anchor="w", justify="left", wraplength=380).grid(
                        row=1, column=0, sticky="ew", padx=10, pady=(0, 12))

        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent",
                                corner_radius=theme.CORNER_NONE)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        # No — secondary, transparent outline (Brutalist square)
        ctk.CTkButton(
            btn_frame, text=no_label, width=160, height=theme.BUTTON_HEIGHT,
            corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
            fg_color="transparent", hover_color=tk["SEL_DEEP"],
            text_color=tk["FG"], border_width=1, border_color=tk["BORDER"],
            command=self._on_no,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        # Yes — primary, mono-grey accent (Brutalist: danger juga no red fill,
        # cuma SEL_BG + SEL_FG untuk destructive ops).
        if danger:
            yes_fg = tk["SEL_BG"]
            yes_text = tk["SEL_FG"]
            yes_hover = tk["SEL_DEEP"]
            yes_border = tk["BORDER2"]
        else:
            yes_fg = tk["ACCENT"]
            yes_text = tk["SEL_FG"]
            yes_hover = tk["ACCENT_H"]
            yes_border = tk["BORDER2"]
        ctk.CTkButton(
            btn_frame, text=yes_label, width=160, height=theme.BUTTON_HEIGHT,
            corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
            fg_color=yes_fg, text_color=yes_text, hover_color=yes_hover,
            border_width=1, border_color=yes_border,
            command=self._on_yes,
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        # Keyboard
        self.bind("<Return>", lambda _e: self._on_yes())
        self.bind("<Escape>", lambda _e: self._on_no())
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
