"""AsynxDL — Restart request dialog.

Modal 2-buttons: "Restart Now" + "Restart Later". Muncul setelah user melakukan
perubahan bahasa atau tema di Settings, karena live-redraw widget Brutalist
(hand-rolled fg_color/text_color token) tidak reliable.

Pakai:

    choice = ask_restart_choice(parent, title=..., message=...)
    if choice == "now":
        os.execv(sys.executable, [sys.executable, *sys.argv])
    elif choice == "later":
        pass  # settings sudah tetap tersimpan, restart manual nanti.
"""
import os
import sys

import customtkinter as ctk

from frontend.ui.components.confirm_dialog import _BG, _FG_PRIMARY, _FG_SECONDARY, _ACCENT


def ask_restart_choice(parent, title: str, message: str) -> str:
    """Tampilkan modal 2-button Restart Now / Restart Later.

    Return:
        "now"  — user klik primary button (Restart Now)
        "later" — user klik secondary button atau close window.
    """
    dlg = RestartDialog(parent, title=title, message=message)
    parent.wait_window(dlg)
    return dlg.result


class RestartDialog(ctk.CTkToplevel):
    """Modal 2-button yang tidak destructive."""

    def __init__(self, parent, title: str, message: str):
        super().__init__(parent, fg_color=_BG)
        self.title(title)
        self.result: str = "later"
        self.resizable(False, False)
        self.attributes("-topmost", True)
        try:
            self.transient(parent)
            self.grab_set()
            self.lift()
            self.focus_force()
        except Exception:
            pass

        width, height = 460, 220
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - width) // 2
            y = (screen_h - height) // 2
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            self.geometry(f"{width}x{height}")

        # Title
        ctk.CTkLabel(
            self, text=title,
            font=("Arial", 16, "bold"),
            text_color=_FG_PRIMARY, anchor="w",
        ).pack(fill="x", padx=20, pady=(20, 6))

        # Body
        ctk.CTkLabel(
            self, text=message,
            font=("Arial", 12),
            text_color=_FG_SECONDARY, anchor="w", justify="left",
            wraplength=420,
        ).pack(fill="x", padx=20, pady=(0, 14))

        # Buttons row
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        # Restart Later (left) — secondary.
        from frontend.ui.i18n import t
        ctk.CTkButton(
            btn_frame,
            text=t("btn.close", default="Close"),
            width=180, height=36,
            corner_radius=10, font=("Arial", 12, "bold"),
            fg_color=("#E5E7EB", "#27272A"),
            text_color=_FG_PRIMARY,
            hover_color=("#D1D5DB", "#3F3F46"),
            command=self._on_later,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))

        # Restart Now (right) — primary.
        ctk.CTkButton(
            btn_frame,
            text=t("btn.restart_now", default="Restart Now"),
            width=180, height=36,
            corner_radius=10, font=("Arial", 12, "bold"),
            fg_color=("#E0E7FF", "#312E81"),
            text_color=_ACCENT,
            hover_color=("#C7D2FE", "#3730A3"),
            command=self._on_now,
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        # Keyboard bindings
        self.bind("<Return>", lambda _e: self._on_now())
        self.bind("<Escape>", lambda _e: self._on_later())
        self.protocol("WM_DELETE_WINDOW", self._on_later)
        try:
            self.after(50, lambda: self.focus_force())
        except Exception:
            pass

    def _on_now(self) -> None:
        self.result = "now"
        try:
            self.grab_release()
        except Exception:
            pass
        self._restart_now()

    def _on_later(self) -> None:
        self.result = "later"
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _restart_now(self) -> None:
        """Re-launch python interpreter dengan argumen yang sama.

        Untuk dev-mode (sys.executable ~= python.exe): restart pakai execv.
        Untuk bundle mode (sys.executable ~= AsynxDL.exe): restart pakai sys.argv[0].
        Karena os.execv butuh full path argv[0], sys.argv sudah cukup karena
        execv pakai sys.executable as the "file".
        """
        self.destroy()
        try:
            argv = [sys.executable] + list(sys.argv)
            os.execv(sys.executable, argv)
        except Exception:
            # Best-effort: jika execv gagal, parent dihancurkan manual.
            try:
                root = self.master.winfo_toplevel()
                root.destroy()
            except Exception:
                pass


__all__ = ["ask_restart_choice", "RestartDialog"]
