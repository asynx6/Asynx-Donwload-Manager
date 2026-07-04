"""AsynxDL — SettingsPanel (tab 'Setting' di MainWindow).

Mono-grey Brutalist — seperti kartu-kartu W98. Sama field dengan modal
lama, tapi sekarang di dalam tab, tanpa window terpisah.
"""

import os
import tkinter.filedialog as filedialog
from typing import Callable

import customtkinter as ctk

from frontend.ui import theme
from frontend.ui.api_client import APIClient
from frontend.ui.i18n import t, set_language


class SettingsPanel(ctk.CTkFrame):

    def __init__(self, master, mode: str = "light", **kw):
        super().__init__(master, fg_color=theme.tokens(mode)["BG2"], corner_radius=theme.CORNER_NONE, **kw)
        self._mode = mode
        self._api: APIClient | None = None
        self._on_save: Callable | None = None
        self._config: dict = {}
        self._widgets_by_row: list = []

        tk = theme.tokens(mode)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._frame = ctk.CTkScrollableFrame(self, fg_color=tk["BG2"], corner_radius=theme.CORNER_NONE)
        self._frame.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self._frame.grid_columnconfigure(0, weight=1)

        # header
        ctk.CTkLabel(
            self._frame, text=t("settings.title"),
            font=theme.font(14, bold=True), text_color=tk["FG"]
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        self._build_fields()
        self._footer()

        # Tunda load sampai attach()
        self._loaded = False

    def attach(self, api: APIClient, on_save: Callable | None) -> None:
        self._api = api
        self._on_save = on_save
        if not self._loaded:
            self._loaded = True
            self.after(80, self._load)

    def on_show(self) -> None:
        # refresh config setiap masuk tab
        if self._api is not None and self._loaded:
            self.after(80, self._load)

    # ------------------------------------------------------------------ UI build

    def _add_section_label(self, row: int, text: str) -> None:
        tk = theme.tokens(self._mode)
        ctk.CTkLabel(
            self._frame, text=text, font=theme.font(12, bold=True),
            text_color=tk["FG2"]
        ).grid(row=row, column=0, sticky="w", pady=(12, 4))

    def _add_form_row(self, row: int, key: str, kind: str, **opt) -> int:
        tk = theme.tokens(self._mode)
        wrap = ctk.CTkFrame(self._frame, fg_color=tk["BG3"], corner_radius=theme.CORNER_NONE,
                            border_width=1, border_color=tk["BORDER"])
        wrap.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            wrap, text=opt.get("label", ""),
            font=theme.font(11), text_color=tk["FG"]
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))

        if kind == "text":
            entry = ctk.CTkEntry(
                wrap, placeholder_text=opt.get("placeholder", ""),
                height=theme.INPUT_HEIGHT, corner_radius=theme.CORNER_NONE,
                font=theme.font(11), fg_color=tk["BG3"], text_color=tk["FG"],
                border_width=1, border_color=tk["BORDER2"],
                placeholder_text_color=tk["FG2"],
            )
            entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 10), columnspan=2 if opt.get("extra_button") else 1)
        elif kind == "int":
            entry = ctk.CTkEntry(
                wrap, placeholder_text=opt.get("placeholder", "0"),
                height=theme.INPUT_HEIGHT, corner_radius=theme.CORNER_NONE,
                font=theme.font(11), fg_color=tk["BG3"], text_color=tk["FG"],
                border_width=1, border_color=tk["BORDER2"],
                placeholder_text_color=tk["FG2"],
            )
            entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 10))
        elif kind == "combo":
            values = opt.get("values", [])
            entry = ctk.CTkComboBox(
                wrap, values=values, height=theme.INPUT_HEIGHT, corner_radius=theme.CORNER_NONE,
                font=theme.font(11), fg_color=tk["BG3"], text_color=tk["FG"],
                border_color=tk["BORDER2"], button_color=tk["ACCENT"],
                dropdown_fg_color=tk["BG3"], dropdown_text_color=tk["FG"],
                dropdown_hover_color=tk["SEL_DEEP"],
            )
            entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 10), columnspan=2)
        elif kind == "slider":
            slider = ctk.CTkSlider(
                wrap, from_=opt.get("from_", 1), to=opt.get("to", 32),
                number_of_steps=opt.get("steps", 31),
                fg_color=tk["BORDER2"], progress_color=tk["PROGRESS"],
                button_color=tk["ACCENT"], button_hover_color=tk["ACCENT_H"],
            )
            slider.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 0))
            label = ctk.CTkLabel(wrap, text="8",
                                 font=theme.font(11), text_color=tk["FG2"])
            label.grid(row=1, column=1, sticky="e", padx=(10, 10), pady=(4, 0))
            slider.configure(command=lambda v, lbl=label: lbl.configure(text=str(int(v))))
            entry = slider
            self._slider_label = label
        elif kind == "check":
            var = ctk.BooleanVar()
            entry = ctk.CTkCheckBox(
                wrap, text=opt.get("label", ""), variable=var,
                fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
                border_color=tk["BORDER2"], text_color=tk["FG"],
                font=theme.font(11), corner_radius=theme.CORNER_NONE,
            )
            entry.grid(row=1, column=0, sticky="w", padx=10, pady=(4, 10))
        else:
            entry = None

        if opt.get("extra_button"):
            btn = ctk.CTkButton(
                wrap, text=opt.get("extra_button_label", t("btn.browse")),
                width=82, height=theme.INPUT_HEIGHT,
                corner_radius=theme.CORNER_NONE,
                font=theme.font(11, bold=True),
                fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
                text_color=tk["SEL_FG"], border_width=1, border_color=tk["BORDER2"],
                command=opt["extra_button_command"],
            )
            btn.grid(row=1, column=1, sticky="e", padx=(0, 10), pady=(4, 10))

        setattr(self, f"_w_{key}", entry)
        self._widgets_by_row.append((row, key, kind))
        return row + 1

    def _build_fields(self) -> None:
        row = 1
        # Default path
        self._add_section_label(row, t("settings.default_path"))
        row += 1
        row = self._add_form_row(row, "default_download_path", "text",
                                  label=t("settings.default_path"),
                                  placeholder=os.path.expandvars("%USERPROFILE%\\Downloads"),
                                  extra_button=True,
                                  extra_button_label=t("btn.browse"),
                                  extra_button_command=self._browse_path)
        # Speed limit
        self._add_section_label(row, t("settings.speed_limit"))
        row += 1
        row = self._add_form_row(row, "speed_limit_kbps", "int",
                                  label=t("settings.speed_limit"),
                                  placeholder="0")
        # Max threads
        self._add_section_label(row, t("settings.max_threads"))
        row += 1
        row = self._add_form_row(row, "max_threads_per_download", "slider",
                                  label=t("settings.max_threads"),
                                  from_=1, to=32, steps=31)
        # Max concurrent
        self._add_section_label(row, t("settings.max_concurrent"))
        row += 1
        row = self._add_form_row(row, "max_concurrent_downloads", "int",
                                  label=t("settings.max_concurrent"),
                                  placeholder="3")
        # Language
        self._add_section_label(row, t("settings.language"))
        row += 1
        row = self._add_form_row(row, "language", "combo",
                                  label=t("settings.language"),
                                  values=["en", "id"])
        # Theme
        self._add_section_label(row, t("settings.theme"))
        row += 1
        row = self._add_form_row(row, "theme_label", "combo",
                                  label=t("settings.theme"),
                                  values=[t("settings.light"), t("settings.dark")])
        # Run on startup
        self._add_section_label(row, t("settings.run_startup"))
        row += 1
        row = self._add_form_row(row, "run_on_startup", "check",
                                  label=t("settings.run_startup"))
        self._end_row = row

    def _footer(self) -> None:
        tk = theme.tokens(self._mode)
        # pins beneath the scrollable _frame.
        footer = ctk.CTkFrame(self, fg_color=tk["BG2"], corner_radius=theme.CORNER_NONE)
        footer.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
        footer.grid_columnconfigure(0, weight=1)

        self._lbl_status = ctk.CTkLabel(
            footer, text=t("settings.saved_hint"),
            font=theme.font(10), text_color=tk["FG2"]
        )
        self._lbl_status.grid(row=0, column=0, sticky="w")

        self._btn_save = ctk.CTkButton(
            footer, text=t("btn.save"), width=110, height=theme.BUTTON_HEIGHT,
            corner_radius=theme.CORNER_NONE,
            font=theme.font(11, bold=True),
            fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"], text_color=tk["SEL_FG"],
            border_width=1, border_color=tk["BORDER2"],
            command=self._save,
        )
        self._btn_save.grid(row=0, column=1)

    def _browse_path(self) -> None:
        path = filedialog.askdirectory()
        if path:
            try:
                self._w_default_download_path.delete(0, "end")
                self._w_default_download_path.insert(0, path)
            except Exception:
                pass

    # ------------------------------------------------------------------ state

    def _load(self) -> None:
        if not self._api:
            return
        try:
            self._config = self._api.get_settings() or {}
        except Exception:
            self._config = {}
        # path
        try:
            self._w_default_download_path.delete(0, "end")
            self._w_default_download_path.insert(
                0, self._config.get("default_download_path",
                                    os.path.expandvars("%USERPROFILE%\\Downloads"))
            )
        except Exception:
            pass
        try:
            self._w_speed_limit_kbps.delete(0, "end")
            self._w_speed_limit_kbps.insert(0, str(self._config.get("speed_limit_kbps", 0)))
        except Exception:
            pass
        try:
            self._w_max_threads_per_download.set(self._config.get("max_threads_per_download", 8))
            if hasattr(self, "_slider_label"):
                self._slider_label.configure(text=str(int(self._w_max_threads_per_download.get())))
        except Exception:
            pass
        try:
            self._w_max_concurrent_downloads.delete(0, "end")
            self._w_max_concurrent_downloads.insert(0, str(self._config.get("max_concurrent_downloads", 3)))
        except Exception:
            pass
        try:
            self._w_language.set(self._config.get("language", "en"))
        except Exception:
            pass
        theme_val = self._config.get("theme", "dark")
        try:
            self._w_theme_label.set(t("settings.light") if theme_val == "light" else t("settings.dark"))
        except Exception:
            pass
        try:
            self._w_run_on_startup.select() if self._config.get("run_on_startup", False) else self._w_run_on_startup.deselect()
        except Exception:
            pass
        # Cache loaded values as baseline supaya _save() dapat membandingkan
        # apakah language/theme berubah dan membutuhkan restart.
        try:
            self._prev_lang_loaded = self._config.get("language", "en")
            self._prev_theme_loaded = self._config.get("theme", "dark") or "dark"
        except Exception:
            self._prev_lang_loaded = "en"
            self._prev_theme_loaded = "dark"

    def _save(self) -> None:
        if not self._api:
            return
        try:
            speed = int(self._w_speed_limit_kbps.get() or 0)
        except ValueError:
            speed = 0
        except Exception:
            speed = 0
        try:
            concurrent = int(self._w_max_concurrent_downloads.get() or 3)
        except ValueError:
            concurrent = 3
        except Exception:
            concurrent = 3
        try:
            threads = int(self._w_max_threads_per_download.get())
        except Exception:
            threads = 8
        try:
            lang = self._w_language.get()
        except Exception:
            lang = "en"
        try:
            theme_val = "light" if self._w_theme_label.get() == t("settings.light") else "dark"
        except Exception:
            theme_val = "dark"
        try:
            startup = bool(self._w_run_on_startup.get())
        except Exception:
            startup = False
        settings = {
            "default_download_path": self._w_default_download_path.get(),
            "speed_limit_kbps": speed,
            "max_threads_per_download": threads,
            "max_concurrent_downloads": concurrent,
            "language": lang,
            "theme": theme_val,
            "run_on_startup": startup,
        }
        # Apply in-process tapi live-redraw belum reliable untuk Brutalist,
        # sehingga perubahan language/theme akan men-trigger restart dialog
        # (lihat bawah).
        try:
            set_language(lang)
            ctk.set_appearance_mode(theme_val)
            self._mode = theme_val
        except Exception:
            pass
        try:
            self._lbl_status.configure(text=t("settings.saved_hint_ok"))
        except Exception:
            pass
        # Track language + theme change untuk restart dialog.
        try:
            self._prev_lang = lang
        except Exception:
            pass
        try:
            self._prev_theme = theme_val
        except Exception:
            pass
        if callable(self._on_save):
            try:
                self._on_save()
            except Exception:
                pass

        # Tampilkan restart dialog kalau language ATAU theme berubah dari
        # nilai awal yang dimuat saat `_load()`. User bisa pilih Restart Now
        # (auto-relaunch via os.execv) atau Restart Later (no-op, default).
        try:
            prev_lang = getattr(self, "_prev_lang_loaded", None)
            prev_theme = getattr(self, "_prev_theme_loaded", None)
            lang_changed = (prev_lang is not None and prev_lang != lang)
            theme_changed = (prev_theme is not None and prev_theme != theme_val)
        except Exception:
            lang_changed = theme_changed = False
        if lang_changed or theme_changed:
            try:
                from frontend.ui.components.restart_dialog import ask_restart_choice
                choice = ask_restart_choice(
                    self,
                    title=t("dialogs.restart.title",
                            default="Restart Required"),
                    message=t("dialogs.restart.body",
                              default="Some changes require a restart to fully apply."),
                )
                if choice == "now":
                    import os as _os, sys as _sys
                    argv = [_sys.executable] + list(_sys.argv)
                    _os.execv(_sys.executable, argv)
            except Exception as exc:
                print(f"[SettingsPanel] restart dialog failed: {exc}")

        # Update baseline after save so subsequent saves compare to latest.
        try:
            self._prev_lang_loaded = lang
            self._prev_theme_loaded = theme_val
        except Exception:
            pass


__all__: list[str] = ["SettingsPanel"]
