import os
import threading
import customtkinter as ctk

from frontend.ui.api_client import APIClient
from frontend.ui.components.progress_bar import ProgressBar
from frontend.ui.components.format_utils import format_size, format_time
from frontend.ui.i18n import t


class DownloadCard(ctk.CTkFrame):
    """Kartu UI untuk satu item download."""

    COLORS = {
        "DOWNLOADING": "#5B6BF8",
        "PAUSED": "#FFA726",
        "COMPLETED": "#66BB6A",
        "ERROR": "#EF5350",
        "PENDING": "#9E9E9E",
        "CANCELLED": "#9E9E9E",
    }

    def __init__(self, master, api: APIClient, data: dict, on_change=None, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=("#FFFFFF", "#2A2A2A"), **kwargs)
        self._api = api
        self._data = data
        self._on_change = on_change
        self._task_id = data.get("id", "")

        self._filename = data.get("filename", data.get("url", "").split("/")[-1] or "unknown")
        self._status = data.get("status", "PENDING")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Header row
        self._header = ctk.CTkFrame(self, fg_color="transparent")
        self._header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 0))
        self._header.grid_columnconfigure(0, weight=1)

        self._icon_label = ctk.CTkLabel(self._header, text="📄", font=("Inter", 16))
        self._icon_label.grid(row=0, column=0, sticky="w")

        self._name_label = ctk.CTkLabel(
            self._header, text=self._filename, font=("Inter", 13, "bold"),
            anchor="w", width=300
        )
        self._name_label.grid(row=0, column=1, sticky="w", padx=(6, 0))

        self._status_badge = ctk.CTkLabel(
            self._header, text=t(f"status.{self._status.lower()}", default=self._status),
            font=("Inter", 10, "bold"), corner_radius=8, fg_color=("#E0E0E0", "#3A3A3A"),
            text_color=("#1A1A1A", "#EFEFEF"), padx=8, pady=2
        )
        self._status_badge.grid(row=0, column=2, sticky="e", padx=(12, 0))

        # Progress bar
        self._progress = ProgressBar(self, height=16)
        self._progress.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 4))

        # Info row
        self._info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._info_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 6))
        self._info_frame.grid_columnconfigure(0, weight=1)
        self._info_frame.grid_columnconfigure(1, weight=0)

        self._speed_label = ctk.CTkLabel(
            self._info_frame, text="", font=("Inter", 11), text_color=("#6B6B6B", "#9E9E9E")
        )
        self._speed_label.grid(row=0, column=0, sticky="w")

        self._size_label = ctk.CTkLabel(
            self._info_frame, text="", font=("Inter", 11), text_color=("#6B6B6B", "#9E9E9E")
        )
        self._size_label.grid(row=0, column=1, sticky="e")

        # Action buttons
        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))
        self._btn_frame.grid_columnconfigure(0, weight=1)
        self._btn_frame.grid_columnconfigure(1, weight=0)
        self._btn_frame.grid_columnconfigure(2, weight=0)
        self._btn_frame.grid_columnconfigure(3, weight=0)

        self._btn_action = ctk.CTkButton(
            self._btn_frame, text=t("btn.pause"), width=80, height=28,
            command=self._toggle_action
        )
        self._btn_action.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self._btn_folder = ctk.CTkButton(
            self._btn_frame, text=t("btn.open_folder"), width=90, height=28,
            command=self._open_folder, fg_color="transparent", border_width=1,
            text_color=("#5B6BF8", "#7B8BFF")
        )
        self._btn_folder.grid(row=0, column=1, padx=6)
        self._btn_folder.grid_remove()

        self._btn_run = ctk.CTkButton(
            self._btn_frame, text=t("btn.run"), width=70, height=28,
            command=self._run_file, fg_color="transparent", border_width=1,
            text_color=("#5B6BF8", "#7B8BFF")
        )
        self._btn_run.grid(row=0, column=2, padx=6)
        self._btn_run.grid_remove()

        self._btn_delete = ctk.CTkButton(
            self._btn_frame, text=t("btn.delete"), width=70, height=28,
            command=self._delete, fg_color=("#C62828", "#EF5350"), hover_color=("#B71C1C", "#E53935")
        )
        self._btn_delete.grid(row=0, column=3, padx=(6, 0))

        self.update_view(data)

    def update_view(self, data: dict):
        self._data = data
        self._status = data.get("status", self._status)
        status_text = t(f"status.{self._status.lower()}", default=self._status)
        if self._status == "PAUSED" and not data.get("graceful_exit", True):
            status_text = t("status.interrupted")

        self._status_badge.configure(text=status_text)
        color = self.COLORS.get(self._status, "#9E9E9E")
        self._progress.set_color(color)

        total = data.get("total_size", 0)
        downloaded = data.get("downloaded_size", 0)
        percent = data.get("percent", 0.0)
        if total > 0 and percent == 0.0:
            percent = min(100.0, downloaded / total * 100)
        self._progress.set(percent)

        speed = data.get("speed_kbps", 0.0)
        eta = data.get("eta_seconds", 0)
        if self._status == "DOWNLOADING":
            self._speed_label.configure(text=f"{speed:.0f} KB/s  •  ETA {format_time(eta)}")
        elif self._status == "COMPLETED":
            self._speed_label.configure(text=t("status.completed"))
        elif self._status == "ERROR":
            self._speed_label.configure(text=t("status.error"))
        else:
            self._speed_label.configure(text="")

        self._size_label.configure(text=f"{format_size(downloaded)} / {format_size(total)}")

        # Button states
        if self._status in ("DOWNLOADING", "PENDING"):
            self._btn_action.configure(text=t("btn.pause"))
        elif self._status in ("PAUSED", "ERROR"):
            self._btn_action.configure(text=t("btn.resume" if self._status == "PAUSED" else "btn.retry"))
        else:
            self._btn_action.configure(text=t("btn.pause"))
            self._btn_action.grid_remove()

        if self._status == "COMPLETED":
            self._btn_folder.grid()
            self._btn_run.grid()
        else:
            self._btn_folder.grid_remove()
            self._btn_run.grid_remove()

        # Force UI update
        self.update_idletasks()

    def _toggle_action(self):
        if self._status in ("DOWNLOADING", "PENDING"):
            threading.Thread(target=self._api.pause, args=(self._task_id,), daemon=True).start()
        elif self._status in ("PAUSED", "ERROR"):
            threading.Thread(target=self._api.resume, args=(self._task_id,), daemon=True).start()

    def _open_folder(self):
        path = self._data.get("save_path", "")
        if path and os.path.exists(path):
            self._api.open_folder(path)

    def _run_file(self):
        path = self._data.get("save_path", "")
        if path and os.path.exists(path):
            self._api.run_file(path)

    def _delete(self):
        threading.Thread(target=self._api.delete, args=(self._task_id, True), daemon=True).start()
        if self._on_change:
            self._on_change()

