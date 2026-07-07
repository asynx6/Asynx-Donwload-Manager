"""AsynxDL — DownloadCard (Brutalist W98 mono-grey).

Square edges, no rounded badge, only greys. Tombol [Pause] / [Hapus] di kanan
bawah, status text di kanan atas tanpa badge warna.
"""

import os
import threading

import customtkinter as ctk

from frontend.ui import theme
from frontend.ui.api_client import APIClient
from frontend.ui.components.format_utils import format_size, format_speed, format_time
from frontend.ui.components.progress_bar import ProgressBar
from frontend.ui.components.confirm_dialog import ask_yes_no
from frontend.ui.i18n import t


class DownloadCard(ctk.CTkFrame):
    """Kartu UI Brutalist mono-grey."""

    def __init__(self, master, api: APIClient, data: dict, on_change=None, mode: str = "light", **kwargs):
        tk = theme.tokens_for(mode)
        super().__init__(
            master,
            corner_radius=theme.CORNER_NONE,
            fg_color=tk["BG3"],
            border_width=1,
            border_color=tk["BORDER"],
            **kwargs,
        )
        self._mode = mode
        self._tk = tk
        self._api = api
        self._data = data
        self._on_change = on_change
        self._task_id = data.get("id", "")
        self._filename = data.get("filename", data.get("url", "").split("/")[-1] or "unknown")
        self._status = data.get("status", "PENDING")

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Header: filename + status text (right) — no rounded icon
        header = ctk.CTkFrame(self, fg_color="transparent", corner_radius=theme.CORNER_NONE)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(12, 6))
        header.grid_columnconfigure(0, weight=1)

        self._name_label = ctk.CTkLabel(
            header, text=self._filename, font=theme.font(12, bold=True),
            anchor="w", text_color=tk["FG"]
        )
        self._name_label.grid(row=0, column=0, sticky="ew")

        self._status_label = ctk.CTkLabel(
            header, text=self._status_text(),
            font=theme.font(11, bold=True),
            text_color=tk["FG2"],
        )
        self._status_label.grid(row=0, column=1, sticky="e", padx=(12, 0))

        # Progress bar — mono-grey fill
        self._progress = ProgressBar(self, height=14, mode=mode, color=tk["PROGRESS"])
        self._progress.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 6))

        # Info row
        info = ctk.CTkFrame(self, fg_color="transparent", corner_radius=theme.CORNER_NONE)
        info.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))
        info.grid_columnconfigure(0, weight=1)
        info.grid_columnconfigure(1, weight=1)
        info.grid_columnconfigure(2, weight=1)

        self._speed_label = ctk.CTkLabel(info, text="", font=theme.font(10), text_color=tk["FG2"])
        self._speed_label.grid(row=0, column=0, sticky="w")
        self._size_label  = ctk.CTkLabel(info, text="", font=theme.font(10), text_color=tk["FG2"])
        self._size_label.grid(row=0, column=1, sticky="w")
        self._eta_label   = ctk.CTkLabel(info, text="", font=theme.font(10), text_color=tk["FG2"])
        self._eta_label.grid(row=0, column=2, sticky="e")

        # Action buttons — square, grey
        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=theme.CORNER_NONE)
        self._btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 12))
        self._btn_frame.grid_columnconfigure(0, weight=1)
        self._btn_frame.grid_columnconfigure(1, weight=1)
        self._btn_frame.grid_columnconfigure(2, weight=1)

        self._btn_action = ctk.CTkButton(
            self._btn_frame, text=t("btn.pause"), width=90, height=theme.BUTTON_HEIGHT - 2,
            corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
            fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"], text_color=tk["SEL_FG"],
            border_width=1, border_color=tk["BORDER2"],
            command=self._toggle_action,
        )
        self._btn_action.grid(row=0, column=0, sticky="w")

        self._btn_cancel = ctk.CTkButton(
            self._btn_frame, text=t("btn.cancel", default="Batal"), width=90, height=theme.BUTTON_HEIGHT - 2,
            corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
            fg_color=tk["SEL_BG"], hover_color=tk["SEL_DEEP"], text_color=tk["SEL_FG"],
            border_width=1, border_color=tk["BORDER2"],
            command=self._cancel,
        )
        self._btn_cancel.grid(row=0, column=1, padx=6)

        self._btn_folder = ctk.CTkButton(
            self._btn_frame, text=t("btn.open_folder"), width=110, height=theme.BUTTON_HEIGHT - 2,
            corner_radius=theme.CORNER_NONE, font=theme.font(10),
            fg_color="transparent", hover_color=tk["SEL_DEEP"], text_color=tk["FG"],
            border_width=1, border_color=tk["BORDER"],
            command=self._open_folder,
        )
        self._btn_folder.grid(row=0, column=0, sticky="w")
        self._btn_folder.grid_remove()

        self._btn_run = ctk.CTkButton(
            self._btn_frame, text=t("btn.run"), width=70, height=theme.BUTTON_HEIGHT - 2,
            corner_radius=theme.CORNER_NONE, font=theme.font(10),
            fg_color="transparent", hover_color=tk["SEL_DEEP"], text_color=tk["FG"],
            border_width=1, border_color=tk["BORDER"],
            command=self._run_file,
        )
        self._btn_run.grid(row=0, column=1, padx=6)
        self._btn_run.grid_remove()

        self._btn_remove_history = ctk.CTkButton(
            self._btn_frame, text=t("btn.remove_history", default="Hapus Riwayat"),
            width=130, height=theme.BUTTON_HEIGHT - 2,
            corner_radius=theme.CORNER_NONE, font=theme.font(10),
            fg_color=tk["SEL_BG"], hover_color=tk["SEL_DEEP"], text_color=tk["SEL_FG"],
            border_width=1, border_color=tk["BORDER2"],
            command=self._remove_history,
        )
        self._btn_remove_history.grid(row=0, column=2, sticky="e", padx=(6, 0))
        self._btn_remove_history.grid_remove()

        self.update_view(data)

    # ------------------------------------------------------------------ helpers

    # Map status enum (uppercase dari backend) ke JSON key di bawah i18n/status.*.
    # Jangan pakai f"status.{status}" — kalau raw status berubah atau ada typo akan
    # bocor ke UI sebagai literal "status.XYZ".
    _STATUS_TO_KEY = {
        "DOWNLOADING":  "status.downloading",
        "PAUSED":       "status.paused",
        "COMPLETED":    "status.completed",
        "ERROR":        "status.error",
        "PENDING":      "status.pending",
        "CANCELLED":    "status.cancelled",
        "INTERRUPTED":  "status.interrupted",
    }

    def _status_text(self) -> str:
        try:
            if self._status == "PAUSED" and not self._data.get("graceful_exit", True):
                return t("status.interrupted")
        except Exception:
            pass
        key = self._STATUS_TO_KEY.get((self._status or "").upper(), None)
        if key:
            return t(key, default=self._status)
        return self._status or ""

    def update_view(self, data: dict) -> None:
        self._data = data
        self._status = data.get("status", self._status)

        self._status_label.configure(text=self._status_text())

        total = data.get("total_size", 0)
        downloaded = data.get("downloaded_size", 0)
        percent = data.get("percent", 0.0)
        if total > 0 and float(percent) == 0.0:
            try:
                percent = min(100.0, downloaded / total * 100)
            except Exception:
                percent = 0.0
        try:
            self._progress.set(float(percent))
        except Exception:
            pass

        speed = data.get("speed_kbps", 0.0)
        eta = data.get("eta_seconds", 0)
        size_text = f"{format_size(downloaded)} / {format_size(total)}"
        percent_text = f"{percent:.1f}%"

        if self._status == "DOWNLOADING":
            try:
                self._speed_label.configure(text=f"{percent_text}  •  {format_speed(speed)}  •  {size_text}")
            except Exception:
                pass
            try:
                self._size_label.configure(text="")
            except Exception:
                pass
            try:
                self._eta_label.configure(text=format_time(eta))
            except Exception:
                pass
        elif self._status == "COMPLETED":
            try:
                self._speed_label.configure(text=f"{percent_text}  •  {t('status.completed')}")
                self._size_label.configure(text=size_text)
                self._eta_label.configure(text="")
            except Exception:
                pass
        elif self._status == "ERROR":
            try:
                self._speed_label.configure(text=f"{percent_text}  •  {t('status.error')}")
                self._size_label.configure(text=size_text)
                self._eta_label.configure(text="")
            except Exception:
                pass
        else:
            try:
                self._speed_label.configure(text=f"{percent_text}  •  {self._status_text()}")
                self._size_label.configure(text=size_text)
                self._eta_label.configure(text="")
            except Exception:
                pass

        # Show/hide action buttons based on status
        if self._status in ("DOWNLOADING", "PENDING"):
            try:
                self._btn_action.configure(text=t("btn.pause"))
                self._btn_action.grid()
            except Exception:
                pass
        elif self._status in ("PAUSED", "ERROR"):
            try:
                self._btn_action.configure(text=t("btn.resume") if self._status == "PAUSED" else t("btn.retry"))
                self._btn_action.grid()
            except Exception:
                pass
        else:
            try:
                self._btn_action.grid_remove()
            except Exception:
                pass

        if self._status in ("DOWNLOADING", "PENDING", "PAUSED", "ERROR"):
            try:
                self._btn_cancel.grid()
            except Exception:
                pass
        else:
            try:
                self._btn_cancel.grid_remove()
            except Exception:
                pass

        if self._status == "COMPLETED":
            try:
                self._btn_folder.grid()
                self._btn_run.grid()
            except Exception:
                pass
        else:
            try:
                self._btn_folder.grid_remove()
                self._btn_run.grid_remove()
            except Exception:
                pass

        if self._status in ("COMPLETED", "ERROR", "CANCELLED"):
            try:
                self._btn_remove_history.grid()
            except Exception:
                pass
        else:
            try:
                self._btn_remove_history.grid_remove()
            except Exception:
                pass

    def recolor(self, mode: str) -> None:
        tk = theme.tokens_for(mode)
        self._mode = mode
        self._tk = tk
        try:
            self.configure(fg_color=tk["BG3"], border_color=tk["BORDER"])
        except Exception:
            pass
        try:
            self._name_label.configure(text_color=tk["FG"])
        except Exception:
            pass
        try:
            self._status_label.configure(text_color=tk["FG2"])
        except Exception:
            pass
        try:
            self._progress.recolor(mode)
        except Exception:
            pass
        try:
            self._speed_label.configure(text_color=tk["FG2"])
            self._size_label.configure(text_color=tk["FG2"])
            self._eta_label.configure(text_color=tk["FG2"])
        except Exception:
            pass
        try:
            self._btn_action.configure(
                fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"], text_color=tk["SEL_FG"], border_color=tk["BORDER2"]
            )
            self._btn_cancel.configure(
                fg_color=tk["SEL_BG"], hover_color=tk["SEL_DEEP"], text_color=tk["SEL_FG"], border_color=tk["BORDER2"]
            )
            self._btn_folder.configure(
                fg_color="transparent", hover_color=tk["SEL_DEEP"], text_color=tk["FG"], border_color=tk["BORDER"]
            )
            self._btn_run.configure(
                fg_color="transparent", hover_color=tk["SEL_DEEP"], text_color=tk["FG"], border_color=tk["BORDER"]
            )
            self._btn_remove_history.configure(
                fg_color=tk["SEL_BG"], hover_color=tk["SEL_DEEP"], text_color=tk["SEL_FG"], border_color=tk["BORDER2"]
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ actions

    def _toggle_action(self) -> None:
        if self._status in ("DOWNLOADING", "PENDING"):
            # Audit-fix H5: jangan diam-diam lewati dialog kalau error.
            # Log dan return — pause TIDAK boleh fire tanpa konfirmasi user.
            try:
                confirmed = ask_yes_no(
                    self.winfo_toplevel(),
                    title=t("dlg.pause.title", default="Pause Download?"),
                    message=t("dlg.pause.body",
                              default=f"Pause \"{self._filename}\"?\nProgress akan disimpan."),
                    danger=False,
                    mode=self._mode,
                )
            except Exception as exc:
                print(f"[DownloadCard] pause-confirm error: {exc}")
                return
            if not confirmed:
                return
            threading.Thread(target=self._api.pause, args=(self._task_id,), daemon=True).start()
        elif self._status in ("PAUSED", "ERROR"):
            threading.Thread(target=self._api.resume, args=(self._task_id,), daemon=True).start()

    def _open_folder(self) -> None:
        path = self._data.get("save_path", "")
        if path and os.path.exists(path):
            self._api.open_folder(path)

    def _run_file(self) -> None:
        path = self._data.get("save_path", "")
        if path and os.path.exists(path):
            self._api.run_file(path)

    def _cancel(self) -> None:
        """Cancel download: stop it, delete parts, and remove from the list."""
        try:
            confirmed = ask_yes_no(
                self.winfo_toplevel(),
                title=t("dlg.cancel.title", default="Batal Unduhan?"),
                message=t("dlg.cancel.body",
                          default=f"Batal \"{self._filename}\"?\n\nFile yang sudah diunduh sebagian akan dihapus."),
                danger=True,
                mode=self._mode,
            )
        except Exception as exc:
            print(f"[DownloadCard] cancel-confirm error: {exc}")
            return
        if not confirmed:
            return

        task_id = self._task_id

        def _vanish() -> None:
            try:
                self.destroy()
            except Exception:
                pass
        try:
            self.master.after(0, _vanish)
        except Exception:
            pass

        def _do_cancel() -> None:
            try:
                self._api.delete(task_id, delete_parts=True, remove_from_history=False)
            except Exception:
                pass
            if self._on_change:
                try:
                    self._on_change()
                except Exception:
                    pass

        threading.Thread(target=_do_cancel, daemon=True).start()

    def _delete(self) -> None:
        # Kept for backward compatibility; now also acts as cancel.
        self._cancel()

    def _remove_history(self) -> None:
        try:
            if not ask_yes_no(
                self.winfo_toplevel(),
                title=t("dlg.remove_history.title", default="Hapus dari Riwayat?"),
                message=t("dlg.remove_history.body",
                          default=f"Hapus \"{self._filename}\" dari riwayat?\n\nFile hasil download (kalau ada) tidak dihapus dari disk."),
                danger=True,
                mode=self._mode,
            ):
                return
        except Exception:
            pass
        threading.Thread(target=self._api.remove_history, args=(self._task_id, True), daemon=True).start()
        if self._on_change:
            self._on_change()
