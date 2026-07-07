"""AsynxDL — Restart required info dialog (Brutalist W98 mono-grey).

Dialog peringatan murni: user diberitahu bahwa perubahan bahasa/tema
memerlukan restart manual. Tidak ada tombol restart otomatis; hanya
tombol Close di tengah.
"""

import customtkinter as ctk

from frontend.ui import theme
from frontend.ui.i18n import t


def ask_restart_choice(parent, title: str, message: str,
                       mode: str = "light") -> str:
    """Tampilkan dialog peringatan restart; return 'later' (tidak auto-restart)."""
    dlg = RestartDialog(parent, title=title, message=message, mode=mode)
    parent.wait_window(dlg)
    return dlg.result


class RestartDialog(ctk.CTkToplevel):
    """Brutalist restart warning — square edges, bordered, mono-grey."""

    def __init__(self, parent, title: str, message: str, mode: str = "light"):
        tk = theme.tokens(mode)
        super().__init__(parent, fg_color=tk["BG2"])
        self.title(title)
        self.result: str = "later"
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

        width, height = 480, 220
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

        # Title
        title_border = ctk.CTkFrame(card, fg_color="transparent",
                                   corner_radius=theme.CORNER_NONE,
                                   border_width=1, border_color=tk["BORDER"])
        title_border.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        ctk.CTkLabel(title_border, text=title, font=theme.font(13, bold=True),
                    text_color=tk["FG"], anchor="w").pack(fill="x", padx=10, pady=8)

        # Body
        ctk.CTkLabel(card, text=message, font=theme.font(11), text_color=tk["FG2"],
                    anchor="w", justify="left", wraplength=420).grid(
                        row=1, column=0, sticky="ew", padx=10, pady=(0, 12))

        # Single centered Close button
        btn_frame = ctk.CTkFrame(card, fg_color="transparent",
                                corner_radius=theme.CORNER_NONE)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_frame, text=t("btn.close", default="Close"),
            width=180, height=theme.BUTTON_HEIGHT,
            corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
            fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
            text_color=tk["SEL_FG"], border_width=1, border_color=tk["BORDER2"],
            command=self._on_close,
        ).grid(row=0, column=0)

        # Keyboard
        self.bind("<Return>", lambda _e: self._on_close())
        self.bind("<Escape>", lambda _e: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, lambda: self.focus_force())

    def _on_close(self) -> None:
        self.result = "later"
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


__all__ = ["ask_restart_choice", "RestartDialog"]  # noqa
