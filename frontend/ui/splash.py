"""
AsynxDL — Startup Splash Window
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Menampilkan jendela splash sederhana saat aplikasi dimulai.
Splash ini dibuat dengan CustomTkinter agar root window yang sama
bisa digunakan oleh UI utama, menghindari dua instance Tk.
"""

import customtkinter as ctk
import os
from PIL import Image


class SplashWindow:
    """Splash window sederhana dengan progress label."""

    def __init__(self, title: str = "AsynxDL"):
        self._root = ctk.CTk()
        self._root.title(title)
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.resizable(False, False)

        # Ukuran splash
        width, height = 420, 260
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self._root.geometry(f"{width}x{height}+{x}+{y}")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._root.configure(fg_color="#1E1E2E")

        # Logo image
        self._logo_label = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "icons.png")
            if os.path.exists(logo_path):
                logo_img = ctk.CTkImage(Image.open(logo_path), size=(64, 64))
                self._logo_label = ctk.CTkLabel(self._root, image=logo_img, text="")
                self._logo_label.pack(pady=(20, 6))
        except Exception:
            pass

        ctk.CTkLabel(
            self._root,
            text=title,
            font=("Arial", 24, "bold"),
            fg_color="#1E1E2E",
            text_color="#7B8BFF",
        ).pack(pady=(10, 10))

        self._status = ctk.CTkLabel(
            self._root,
            text="Starting up...",
            font=("Arial", 11),
            fg_color="#1E1E2E",
            text_color="#E0E0E0",
        )
        self._status.pack(pady=(0, 20))

        self._progress = ctk.CTkProgressBar(self._root, width=300, mode="indeterminate")
        self._progress.pack(pady=10)
        self._progress.start()

        ctk.CTkLabel(
            self._root,
            text="v1.0.2",
            font=("Arial", 9),
            fg_color="#1E1E2E",
            text_color="#888888",
        ).pack(side="bottom", pady=10)

        self._root.update_idletasks()

    def set_status(self, text: str):
        self._status.configure(text=text)
        self._root.update_idletasks()

    def close(self):
        try:
            self._progress.stop()
            # Withdraw instead of destroying the root so the main window survives.
            self._root.withdraw()
        except Exception:
            pass

    def show(self):
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()
        self._root.update_idletasks()
