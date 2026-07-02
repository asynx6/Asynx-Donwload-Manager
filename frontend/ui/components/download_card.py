import os
import threading
import customtkinter as ctk

from frontend.ui.api_client import APIClient
from frontend.ui.components.progress_bar import ProgressBar
from frontend.ui.components.format_utils import format_size, format_time
from frontend.ui.i18n import t


class DownloadCard(ctk.CTkFrame):
    """Kartu UI modern untuk satu item download."""

    STATUS_COLORS = {
        "DOWNLOADING": ("#6366F1", "#818CF8"),
        "PAUSED":      ("#F59E0B", "#FBBF24"),
        "COMPLETED":   ("#10B981", "#34D399"),
        "ERROR":       ("#EF4444", "#F87171"),
        "PENDING":     ("#6B7280", "#9CA3AF"),
        "CANCELLED":   ("#6B7280", "#9CA3AF"),
    }

    BG = ("#FFFFFF", "#18181E")
    TEXT_PRIMARY = ("#111827", "#F9FAFB")
    TEXT_SECONDARY = ("#6B7280", "#9CA3AF")

    def __init__(self, master, api: APIClient, data: dict, on_change=None, **kwargs):
        super().__init__(master, corner_radius=16, fg_color=self.BG, **kwargs)
        self._api = api
        self._data = data
        self._on_change = on_change
        self._task_id = data.get("id", "")

        self._filename = data.get("filename", data.get("url", "").split("/")[-1] or "unknown")
        self._status = data.get("status", "PENDING")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Header: icon + filename + badge
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(16, 8))
        header.grid_columnconfigure(1, weight=1)

        self._icon_label = ctk.CTkLabel(
            header, text="A", font=("Arial", 18, "bold"),
            text_color=self.STATUS_COLORS.get(self._status, self.STATUS_COLORS["PENDING"])[0]
        )
        self._icon_label.grid(row=0, column=0, sticky="w")

        self._name_label = ctk.CTkLabel(
            header, text=self._filename, font=("Arial", 14, "bold"),
            anchor="w", text_color=self.TEXT_PRIMARY
        )
        self._name_label.grid(row=0, column=1, sticky="ew", padx=(10, 12))

        self._status_badge = ctk.CTkLabel(
            header, text=self._status_text(),
            font=("Arial", 11, "bold"), corner_radius=20,
            fg_color=("#E5E7EB", "#27272A"),
            text_color=self.STATUS_COLORS.get(self._status, self.STATUS_COLORS["PENDING"])[0],
            padx=12, pady=4
        )
        self._status_badge.grid(row=0, column=2, sticky="e")

        # Progress bar
        self._progress = ProgressBar(self, height=18)
        self._progress.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(4, 8))

        # Info row
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 10))
        info.grid_columnconfigure(0, weight=1)
        info.grid_columnconfigure(1, weight=1)
        info.grid_columnconfigure(2, weight=1)

        self._speed_label = ctk.CTkLabel(
            info, text="", font=("Arial", 12), text_color=self.TEXT_SECONDARY
        )
        self._speed_label.grid(row=0, column=0, sticky="w")

        self._size_label = ctk.CTkLabel(
            info, text="", font=("Arial", 12), text_color=self.TEXT_SECONDARY
        )
        self._size_label.grid(row=0, column=1, sticky="w")

        self._eta_label = ctk.CTkLabel(
            info, text="", font=("Arial", 12), text_color=self.TEXT_SECONDARY
        )
        self._eta_label.grid(row=0, column=2, sticky="e")

        # Action buttons
        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 16))
        self._btn_frame.grid_columnconfigure(0, weight=1)
        self._btn_frame.grid_columnconfigure(1, weight=0)

        self._btn_action = ctk.CTkButton(
            self._btn_frame, text=t("btn.pause"), width=100, height=34,
            corner_radius=10, font=("Arial", 12, "bold"),
            fg_color=("#E5E7EB", "#27272A"), text_color=self.TEXT_PRIMARY,
            hover_color=("#D1D5DB", "#3F3F46"),
            command=self._toggle_action
        )
        self._btn_action.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self._btn_folder = ctk.CTkButton(
            self._btn_frame, text=t("btn.open_folder"), width=110, height=34,
            corner_radius=10, font=("Arial", 12),
            fg_color="transparent", border_width=1,
            text_color=("#6366F1", "#818CF8"),
            hover_color=("#E0E7FF", "#312E81"),
            command=self._open_folder
        )
        self._btn_folder.grid(row=0, column=1, padx=8)
        self._btn_folder.grid_remove()

        self._btn_run = ctk.CTkButton(
            self._btn_frame, text=t("btn.run"), width=90, height=34,
            corner_radius=10, font=("Arial", 12),
            fg_color="transparent", border_width=1,
            text_color=("#6366F1", "#818CF8"),
            hover_color=("#E0E7FF", "#312E81"),
            command=self._run_file
        )
        self._btn_run.grid(row=0, column=2, padx=8)
        self._btn_run.grid_remove()

        self._btn_delete = ctk.CTkButton(
            self._btn_frame, text=t("btn.delete"), width=90, height=34,
            corner_radius=10, font=("Arial", 12),
            fg_color=("#FEE2E2", "#3F1818"), text_color=("#DC2626", "#FCA5A5"),
            hover_color=("#FECACA", "#522424"),
            command=self._delete
        )
        self._btn_delete.grid(row=0, column=3, padx=(8, 0))

        self.update_view(data)

    def _status_text(self):
        status = self._status.lower()
        if self._status == "PAUSED" and not self._data.get("graceful_exit", True):
            return t("status.interrupted")
        return t(f"status.{status}", default=self._status)

    def update_view(self, data: dict):
        self._data = data
        self._status = data.get("status", self._status)

        self._status_badge.configure(text=self._status_text())
        color_pair = self.STATUS_COLORS.get(self._status, self.STATUS_COLORS["PENDING"])
        self._icon_label.configure(text_color=color_pair[0])
        self._status_badge.configure(text_color=color_pair[0])
        self._progress.set_color(color_pair[0])

        total = data.get("total_size", 0)
        downloaded = data.get("downloaded_size", 0)
        percent = data.get("percent", 0.0)
        if total > 0 and percent == 0.0:
            percent = min(100.0, downloaded / total * 100)
        self._progress.set(percent)

        speed = data.get("speed_kbps", 0.0)
        eta = data.get("eta_seconds", 0)
        if self._status == "DOWNLOADING":
            self._speed_label.configure(text=f"{speed:.0f} KB/s")
            self._eta_label.configure(text=f"{format_time(eta)}")
        elif self._status == "COMPLETED":
            self._speed_label.configure(text=t("status.completed"))
            self._eta_label.configure(text="")
        elif self._status == "ERROR":
            self._speed_label.configure(text=t("status.error"))
            self._eta_label.configure(text="")
        else:
            self._speed_label.configure(text="")
            self._eta_label.configure(text="")

        self._size_label.configure(text=f"{format_size(downloaded)} / {format_size(total)}")

        # Button states
        if self._status in ("DOWNLOADING", "PENDING"):
            self._btn_action.configure(text=t("btn.pause"))
            self._btn_action.grid()
        elif self._status in ("PAUSED", "ERROR"):
            self._btn_action.configure(
                text=t("btn.resume" if self._status == "PAUSED" else "btn.retry")
            )
            self._btn_action.grid()
        else:
            self._btn_action.grid_remove()

        if self._status == "COMPLETED":
            self._btn_folder.grid()
            self._btn_run.grid()
        else:
            self._btn_folder.grid_remove()
            self._btn_run.grid_remove()

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
