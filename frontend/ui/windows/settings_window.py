import os
import tkinter.filedialog as filedialog
import customtkinter as ctk

from frontend.ui.api_client import APIClient
from frontend.ui.i18n import t, set_language


class SettingsWindow(ctk.CTkToplevel):
    """Window pengaturan aplikasi dengan tampilan modern."""

    ACCENT = "#6366F1"
    ACCENT_HOVER = "#4F46E5"
    BG = ("#FFFFFF", "#18181E")
    TEXT_PRIMARY = ("#111827", "#F9FAFB")
    TEXT_SECONDARY = ("#6B7280", "#9CA3AF")

    def __init__(self, master, api: APIClient, on_save=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title(t("settings.title"))
        self.geometry("560x600")
        self.resizable(False, False)
        self._api = api
        self._on_save = on_save
        self._config = {}
        self.configure(fg_color=self.BG)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._frame.grid(row=0, column=0, sticky="nsew", padx=28, pady=28)
        self._frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._frame, text=t("settings.title"), font=("Arial", 20, "bold"),
            text_color=self.TEXT_PRIMARY
        ).grid(row=0, column=0, sticky="w", pady=(0, 18))

        self._build_fields()
        self._load()

        # Buttons
        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_frame.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 22))
        self._btn_frame.grid_columnconfigure(0, weight=1)

        self._btn_save = ctk.CTkButton(
            self._btn_frame, text=t("btn.save"), width=110, height=36, corner_radius=10,
            font=("Arial", 12, "bold"), fg_color=self.ACCENT, hover_color=self.ACCENT_HOVER,
            command=self._save
        )
        self._btn_save.grid(row=0, column=1, padx=(8, 0))

        self._btn_close = ctk.CTkButton(
            self._btn_frame, text=t("btn.close"), width=110, height=36, corner_radius=10,
            font=("Arial", 12), fg_color=("#E5E7EB", "#27272A"), text_color=self.TEXT_PRIMARY,
            hover_color=("#D1D5DB", "#3F3F46"), command=self.destroy
        )
        self._btn_close.grid(row=0, column=2, padx=(8, 0))

        self._center_on_parent()

    def _center_on_parent(self):
        self.update_idletasks()
        parent = self.winfo_toplevel()
        px = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _build_fields(self):
        row = 1

        # Default path
        self._add_label(row, t("settings.default_path"))
        row += 1
        self._path_frame = ctk.CTkFrame(self._frame, fg_color="transparent")
        self._path_frame.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        self._path_frame.grid_columnconfigure(0, weight=1)
        self._entry_path = ctk.CTkEntry(
            self._path_frame, height=36, corner_radius=10, font=("Arial", 12)
        )
        self._entry_path.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            self._path_frame, text=t("btn.browse"), width=90, height=34, corner_radius=10,
            font=("Arial", 12), command=self._browse_path
        ).grid(row=0, column=1)
        row += 1

        # Speed limit
        self._add_label(row, t("settings.speed_limit"))
        row += 1
        self._entry_speed = ctk.CTkEntry(
            self._frame, placeholder_text="0", height=36, corner_radius=10, font=("Arial", 12)
        )
        self._entry_speed.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        row += 1

        # Max threads
        self._add_label(row, t("settings.max_threads"))
        row += 1
        self._slider_threads = ctk.CTkSlider(self._frame, from_=1, to=8, number_of_steps=7)
        self._slider_threads.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        self._label_threads = ctk.CTkLabel(self._frame, text="8", font=("Arial", 12), text_color=self.TEXT_SECONDARY)
        self._label_threads.grid(row=row + 1, column=0, sticky="w", pady=(0, 14))
        self._slider_threads.configure(command=lambda v: self._label_threads.configure(text=str(int(v))))
        row += 2

        # Max concurrent
        self._add_label(row, t("settings.max_concurrent"))
        row += 1
        self._entry_concurrent = ctk.CTkEntry(
            self._frame, placeholder_text="3", height=36, corner_radius=10, font=("Arial", 12)
        )
        self._entry_concurrent.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        row += 1

        # Language
        self._add_label(row, t("settings.language"))
        row += 1
        self._combo_lang = ctk.CTkComboBox(
            self._frame, values=["en", "id"], height=36, corner_radius=10, font=("Arial", 12)
        )
        self._combo_lang.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        row += 1

        # Theme
        self._add_label(row, t("settings.theme"))
        row += 1
        self._combo_theme = ctk.CTkComboBox(
            self._frame, values=[t("settings.light"), t("settings.dark")],
            height=36, corner_radius=10, font=("Arial", 12)
        )
        self._combo_theme.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        row += 1

        # Run on startup
        self._var_startup = ctk.BooleanVar()
        self._check_startup = ctk.CTkCheckBox(
            self._frame, text=t("settings.run_startup"), variable=self._var_startup,
            font=("Arial", 12), text_color=self.TEXT_PRIMARY
        )
        self._check_startup.grid(row=row, column=0, sticky="w", pady=(0, 12))
        row += 1

    def _add_label(self, row, text):
        ctk.CTkLabel(
            self._frame, text=text, font=("Arial", 12, "bold"),
            text_color=self.TEXT_SECONDARY
        ).grid(row=row, column=0, sticky="w", pady=(0, 4))

    def _browse_path(self):
        path = filedialog.askdirectory()
        if path:
            self._entry_path.delete(0, "end")
            self._entry_path.insert(0, path)

    def _load(self):
        try:
            self._config = self._api.get_settings()
        except Exception:
            self._config = {}
        self._entry_path.insert(0, self._config.get("default_download_path", os.path.expandvars("%USERPROFILE%\\Downloads")))
        self._entry_speed.insert(0, str(self._config.get("speed_limit_kbps", 0)))
        self._slider_threads.set(self._config.get("max_threads_per_download", 8))
        self._label_threads.configure(text=str(self._config.get("max_threads_per_download", 8)))
        self._entry_concurrent.insert(0, str(self._config.get("max_concurrent_downloads", 3)))
        self._combo_lang.set(self._config.get("language", "en"))
        theme = self._config.get("theme", "dark")
        self._combo_theme.set(t("settings.light") if theme == "light" else t("settings.dark"))
        self._var_startup.set(self._config.get("run_on_startup", False))

    def _save(self):
        try:
            speed = int(self._entry_speed.get() or 0)
        except ValueError:
            speed = 0
        try:
            concurrent = int(self._entry_concurrent.get() or 3)
        except ValueError:
            concurrent = 3
        threads = int(self._slider_threads.get())
        lang = self._combo_lang.get()
        theme = "light" if self._combo_theme.get() == t("settings.light") else "dark"
        settings = {
            "default_download_path": self._entry_path.get(),
            "speed_limit_kbps": speed,
            "max_threads_per_download": threads,
            "max_concurrent_downloads": concurrent,
            "language": lang,
            "theme": theme,
            "run_on_startup": self._var_startup.get(),
        }
        try:
            self._api.put_settings(settings)
            set_language(lang)
            ctk.set_appearance_mode(theme)
        except Exception as exc:
            print(f"[SettingsWindow] failed to save: {exc}")
        if self._on_save:
            self._on_save()
        self.destroy()
