import os
import threading
import tkinter.filedialog as filedialog
import customtkinter as ctk

from frontend.ui.api_client import APIClient
from frontend.ui.i18n import t


class AddDownloadWindow(ctk.CTkToplevel):
    """Dialog modern tambah download baru."""

    ACCENT = "#6366F1"
    ACCENT_HOVER = "#4F46E5"
    BG = ("#FFFFFF", "#18181E")
    TEXT_PRIMARY = ("#111827", "#F9FAFB")
    TEXT_SECONDARY = ("#6B7280", "#9CA3AF")

    def __init__(self, master, api: APIClient, on_added=None, default_path: str = "", **kwargs):
        super().__init__(master, **kwargs)
        self.title(t("add.title"))
        self.geometry("520x420")
        self.resizable(False, False)
        self._api = api
        self._on_added = on_added
        self._default_path = default_path
        self.configure(fg_color=self.BG)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=28, pady=28)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame, text=t("add.title"), font=("Arial", 20, "bold"),
            text_color=self.TEXT_PRIMARY
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))

        ctk.CTkLabel(frame, text=t("add.url"), font=("Arial", 12, "bold"), text_color=self.TEXT_SECONDARY).grid(row=1, column=0, sticky="w", pady=(0, 4))
        self._entry_url = ctk.CTkEntry(
            frame, placeholder_text="https://...", height=36, corner_radius=10, font=("Arial", 12)
        )
        self._entry_url.grid(row=1, column=1, sticky="ew", padx=(14, 0), pady=(0, 12))

        ctk.CTkLabel(frame, text=t("add.filename"), font=("Arial", 12, "bold"), text_color=self.TEXT_SECONDARY).grid(row=2, column=0, sticky="w", pady=(0, 4))
        self._entry_filename = ctk.CTkEntry(
            frame, placeholder_text="optional", height=36, corner_radius=10, font=("Arial", 12)
        )
        self._entry_filename.grid(row=2, column=1, sticky="ew", padx=(14, 0), pady=(0, 12))

        ctk.CTkLabel(frame, text=t("add.save_path"), font=("Arial", 12, "bold"), text_color=self.TEXT_SECONDARY).grid(row=3, column=0, sticky="w", pady=(0, 4))
        path_frame = ctk.CTkFrame(frame, fg_color="transparent")
        path_frame.grid(row=3, column=1, sticky="ew", padx=(14, 0), pady=(0, 12))
        path_frame.grid_columnconfigure(0, weight=1)
        self._entry_path = ctk.CTkEntry(
            path_frame, height=36, corner_radius=10, font=("Arial", 12)
        )
        self._entry_path.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entry_path.insert(0, default_path)
        ctk.CTkButton(
            path_frame, text=t("btn.browse"), width=90, height=34, corner_radius=10,
            font=("Arial", 12), command=self._browse
        ).grid(row=0, column=1)

        ctk.CTkLabel(frame, text=t("add.speed_limit"), font=("Arial", 12, "bold"), text_color=self.TEXT_SECONDARY).grid(row=4, column=0, sticky="w", pady=(0, 4))
        self._entry_limit = ctk.CTkEntry(
            frame, placeholder_text="0", height=36, corner_radius=10, font=("Arial", 12)
        )
        self._entry_limit.grid(row=4, column=1, sticky="ew", padx=(14, 0), pady=(0, 12))
        self._entry_limit.insert(0, "0")

        ctk.CTkLabel(
            frame,
            text=t("add.speed_hint"),
            font=("Arial", 11), text_color=self.TEXT_SECONDARY
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 22))
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_frame, text=t("btn.close"), width=110, height=36, corner_radius=10,
            font=("Arial", 12), fg_color=("#E5E7EB", "#27272A"), text_color=self.TEXT_PRIMARY,
            hover_color=("#D1D5DB", "#3F3F46"), command=self.destroy
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            btn_frame, text=t("btn.start"), width=110, height=36, corner_radius=10,
            font=("Arial", 12, "bold"), fg_color=self.ACCENT, hover_color=self.ACCENT_HOVER,
            command=self._start
        ).grid(row=0, column=2, padx=(8, 0))

        self._entry_url.focus()
        self._center_on_parent()

    def _center_on_parent(self):
        self.update_idletasks()
        parent = self.winfo_toplevel()
        px = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _browse(self):
        path = filedialog.askdirectory()
        if path:
            self._entry_path.delete(0, "end")
            self._entry_path.insert(0, path)

    def _start(self):
        url = self._entry_url.get().strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            self._entry_url.configure(border_color=("#DC2626", "#FCA5A5"))
            return
        filename = self._entry_filename.get().strip()
        save_path = self._entry_path.get().strip() or self._default_path
        try:
            limit = int(self._entry_limit.get() or 0)
        except ValueError:
            limit = 0

        def do_add():
            try:
                self._api.add_download(url, filename, save_path, limit)
                if self._on_added:
                    self._on_added()
            except Exception as exc:
                print(f"[AddDownloadWindow] failed: {exc}")
            self.after(0, self.destroy)

        threading.Thread(target=do_add, daemon=True).start()
