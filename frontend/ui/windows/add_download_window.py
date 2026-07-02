import os
import threading
import tkinter.filedialog as filedialog
import customtkinter as ctk

from frontend.ui.api_client import APIClient
from frontend.ui.i18n import t


class AddDownloadWindow(ctk.CTkToplevel):
    """Dialog tambah download baru."""

    def __init__(self, master, api: APIClient, on_added=None, default_path: str = "", **kwargs):
        super().__init__(master, **kwargs)
        self.title(t("add.title"))
        self.geometry("480x300")
        self.resizable(False, False)
        self._api = api
        self._on_added = on_added
        self._default_path = default_path

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text=t("add.url"), font=("Inter", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self._entry_url = ctk.CTkEntry(frame, placeholder_text="https://...")
        self._entry_url.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        ctk.CTkLabel(frame, text=t("add.filename"), font=("Inter", 12, "bold")).grid(row=1, column=0, sticky="w", pady=(0, 4))
        self._entry_filename = ctk.CTkEntry(frame, placeholder_text="optional")
        self._entry_filename.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        ctk.CTkLabel(frame, text=t("add.save_path"), font=("Inter", 12, "bold")).grid(row=2, column=0, sticky="w", pady=(0, 4))
        path_frame = ctk.CTkFrame(frame, fg_color="transparent")
        path_frame.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))
        path_frame.grid_columnconfigure(0, weight=1)
        self._entry_path = ctk.CTkEntry(path_frame)
        self._entry_path.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._entry_path.insert(0, default_path)
        ctk.CTkButton(path_frame, text=t("btn.browse"), width=80, command=self._browse).grid(row=0, column=1)

        ctk.CTkLabel(frame, text=t("add.speed_limit"), font=("Inter", 12, "bold")).grid(row=3, column=0, sticky="w", pady=(0, 4))
        self._entry_limit = ctk.CTkEntry(frame, placeholder_text="0")
        self._entry_limit.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))
        self._entry_limit.insert(0, "0")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 16))
        btn_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(btn_frame, text=t("btn.close"), command=self.destroy).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(btn_frame, text=t("btn.start"), command=self._start).grid(row=0, column=2, padx=(8, 0))

        self._entry_url.focus()

    def _browse(self):
        path = filedialog.askdirectory()
        if path:
            self._entry_path.delete(0, "end")
            self._entry_path.insert(0, path)

    def _start(self):
        url = self._entry_url.get().strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            self._entry_url.configure(border_color=("#C62828", "#EF5350"))
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
            except Exception as exc:
                print(f"[AddDownloadWindow] failed: {exc}")
            if self._on_added:
                self._on_added()
            self.after(0, self.destroy)

        threading.Thread(target=do_add, daemon=True).start()
