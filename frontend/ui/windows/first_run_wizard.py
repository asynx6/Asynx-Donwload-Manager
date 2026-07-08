"""AsynxDL — FirstRunWizard (Brutalist W98 mono-grey).

Square edges. Step dots: ■ current step / □ upcoming (mono-grey accents).
3 steps: pilih bahasa → tentukan path download + startup → tampilkan token.
"""
import os
import tkinter.filedialog as filedialog

import customtkinter as ctk
from PIL import Image

from backend.system.config import (
    load_config,
    mark_first_run_completed,
    update_config,
)
from frontend.ui import theme
from frontend.ui.i18n import set_language, t


class FirstRunWizard(ctk.CTkToplevel):
    """Brutalist mono-grey setup wizard."""

    def __init__(self, master, on_finish=None, mode: str = "light", **kwargs):
        tk = theme.tokens(mode)
        super().__init__(master, fg_color=tk["BG2"], **kwargs)
        self.title(t("wizard.welcome"))
        self.geometry("640x540")
        self.resizable(False, False)
        self._on_finish = on_finish
        self._mode = mode
        self._config = load_config()
        self._step = 0
        self.configure(fg_color=tk["BG2"])

        # Center on parent (fallback to screen center)
        self.update_idletasks()
        try:
            parent = self.winfo_toplevel()
            if parent.winfo_ismapped():
                px = parent.winfo_x() + (parent.winfo_width() - 640) // 2
                py = parent.winfo_y() + (parent.winfo_height() - 540) // 2
            else:
                px = (self.winfo_screenwidth() - 640) // 2
                py = (self.winfo_screenheight() - 540) // 2
            self.geometry(f"640x540+{px}+{py}")
        except Exception:
            pass

        # Bordered branding bar
        bar = ctk.CTkFrame(self, fg_color=tk["BG3"], corner_radius=theme.CORNER_NONE,
                          border_width=1, border_color=tk["BORDER"])
        bar.pack(fill="x", padx=10, pady=(10, 6))
        bar.grid_columnconfigure(0, weight=0)
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_columnconfigure(2, weight=0)

        # Logo (best-effort load)
        logo_img = self._load_logo(28)
        if logo_img is not None:
            self._logo_label = ctk.CTkLabel(bar, image=logo_img, text="")
            self._logo_label.image = logo_img
        else:
            self._logo_label = ctk.CTkLabel(bar, text="[A]",
                                            font=theme.font(13, bold=True),
                                            text_color=tk["FG"])
        self._logo_label.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=8)

        self._title = ctk.CTkLabel(bar, text=t("wizard.welcome"),
                                  font=theme.font(13, bold=True),
                                  text_color=tk["FG"])
        self._title.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=8)

        # Step dots
        self._dots_frame = ctk.CTkFrame(bar, fg_color="transparent",
                                       corner_radius=theme.CORNER_NONE)
        self._dots_frame.grid(row=0, column=2, sticky="e", padx=(0, 12), pady=8)
        self._dot_labels = []
        for i in range(2):
            lbl = ctk.CTkLabel(self._dots_frame, text="□",
                              font=theme.font(13, bold=True), text_color=tk["FG2"])
            lbl.grid(row=0, column=i, padx=2)
            self._dot_labels.append(lbl)

        # Content body — bordered frame
        self._container = ctk.CTkFrame(self, fg_color=tk["BG3"],
                                      corner_radius=theme.CORNER_NONE,
                                      border_width=1, border_color=tk["BORDER"])
        self._container.pack(fill="both", expand=True, padx=10, pady=6)
        self._container.grid_columnconfigure(0, weight=1)
        self._container.grid_rowconfigure(0, weight=1)

        # Footer — Back + Next
        foot = ctk.CTkFrame(self, fg_color="transparent", corner_radius=theme.CORNER_NONE)
        foot.pack(fill="x", padx=10, pady=(0, 10))
        foot.grid_columnconfigure(0, weight=1)
        foot.grid_columnconfigure(1, weight=0)
        foot.grid_columnconfigure(2, weight=0)
        self._btn_back = ctk.CTkButton(foot, text=t("btn.back", default="Back"),
                                      width=110, height=theme.BUTTON_HEIGHT,
                                      corner_radius=theme.CORNER_NONE,
                                      font=theme.font(11, bold=True),
                                      fg_color="transparent", hover_color=tk["SEL_DEEP"],
                                      text_color=tk["FG"], border_width=1,
                                      border_color=tk["BORDER"],
                                      command=self._back, state="disabled")
        self._btn_back.grid(row=0, column=0, sticky="w")
        self._btn_next = ctk.CTkButton(foot, text=t("btn.continue", default="Continue"),
                                      width=130, height=theme.BUTTON_HEIGHT,
                                      corner_radius=theme.CORNER_NONE,
                                      font=theme.font(11, bold=True),
                                      fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
                                      text_color=tk["SEL_FG"], border_width=1,
                                      border_color=tk["BORDER2"],
                                      command=self._next)
        self._btn_next.grid(row=0, column=2, padx=(8, 0))

        self._render_step()

    # ------------------------------------------------------------------ helpers

    def _load_logo(self, size: int):
        try:
            candidates = [
                os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "icons.png"),
            ]
            for path in candidates:
                if path and os.path.exists(path):
                    return ctk.CTkImage(Image.open(path), size=(size, size))
        except Exception:
            pass
        return None

    def _update_dots(self):
        try:
            tk = theme.tokens(self._mode)
            for i, lbl in enumerate(self._dot_labels):
                if i == self._step:
                    lbl.configure(text="■", text_color=tk["FG"])
                else:
                    lbl.configure(text="□", text_color=tk["FG2"])
        except Exception:
            pass

    def _set_back_enabled(self):
        try:
            if self._step == 0:
                self._btn_back.configure(state="disabled")
            else:
                self._btn_back.configure(state="normal")
        except Exception:
            pass

    def _render_step(self):
        # Reset content area
        for w in self._container.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self._update_dots()
        self._set_back_enabled()
        tk = theme.tokens(self._mode)

        if self._step == 0:
            # Language chooser
            ctk.CTkLabel(self._container, text=t("wizard.language"),
                        font=theme.font(12, bold=True), text_color=tk["FG"],
                        anchor="w").grid(row=0, column=0, sticky="w",
                                         padx=14, pady=(14, 4))
            self._combo_lang = ctk.CTkComboBox(
                self._container,
                values=["English", "Bahasa Indonesia"],
                height=theme.INPUT_HEIGHT,
                corner_radius=theme.CORNER_NONE,
                font=theme.font(11),
                fg_color=tk["BG3"],
                text_color=tk["FG"],
                border_color=tk["BORDER2"],
                button_color=tk["ACCENT"],
                dropdown_fg_color=tk["BG3"],
                dropdown_text_color=tk["FG"],
                dropdown_hover_color=tk["SEL_DEEP"],
            )
            cur_lang = self._config.get("language", "en")
            self._combo_lang.set("English" if cur_lang == "en" else "Bahasa Indonesia")
            self._combo_lang.grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 14))

        elif self._step == 1:
            # Path + startup
            ctk.CTkLabel(self._container, text=t("wizard.download_path"),
                        font=theme.font(12, bold=True), text_color=tk["FG"],
                        anchor="w").grid(row=0, column=0, sticky="w",
                                         padx=14, pady=(14, 4))
            path_frame = ctk.CTkFrame(self._container, fg_color="transparent",
                                     corner_radius=theme.CORNER_NONE)
            path_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 12))
            path_frame.grid_columnconfigure(0, weight=1)
            self._entry_path = ctk.CTkEntry(
                path_frame, height=theme.INPUT_HEIGHT, corner_radius=theme.CORNER_NONE,
                font=theme.font(11), fg_color=tk["BG3"], text_color=tk["FG"],
                border_width=1, border_color=tk["BORDER2"],
            )
            self._entry_path.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            self._entry_path.insert(0, self._config.get("default_download_path", ""))
            ctk.CTkButton(
                path_frame, text=t("btn.browse"), width=82, height=theme.INPUT_HEIGHT,
                corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
                fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
                text_color=tk["SEL_FG"], border_width=1, border_color=tk["BORDER2"],
                command=self._browse,
            ).grid(row=0, column=1)

            ctk.CTkLabel(self._container, text=t("wizard.startup"),
                        font=theme.font(12, bold=True), text_color=tk["FG"],
                        anchor="w").grid(row=2, column=0, sticky="w",
                                         padx=14, pady=(8, 4))
            self._var_startup = ctk.BooleanVar(
                value=self._config.get("run_on_startup", False))
            ctk.CTkCheckBox(
                self._container, text=t("wizard.startup"), variable=self._var_startup,
                font=theme.font(11), fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
                border_color=tk["BORDER2"], text_color=tk["FG"],
                corner_radius=theme.CORNER_NONE,
            ).grid(row=3, column=0, sticky="w", padx=14, pady=(4, 14))

        elif self._step == 1:
            # Final step — show a short "ready" summary
            ctk.CTkLabel(self._container, text=t("wizard.ready_title", default="You're all set"),
                        font=theme.font(12, bold=True), text_color=tk["FG"],
                        anchor="w").grid(row=0, column=0, sticky="w",
                                         padx=14, pady=(14, 4))
            ctk.CTkLabel(self._container, text=t("wizard.ready_desc",
                        default="AsynxDL is ready to use. Click Get Started to open the app."),
                        wraplength=560, justify="left", font=theme.font(10),
                        text_color=tk["FG2"], anchor="w").grid(
                            row=1, column=0, sticky="w", padx=14, pady=(4, 12))
            try:
                self._btn_next.configure(text=t("wizard.finish"))
            except Exception:
                pass

    def _browse(self):
        path = filedialog.askdirectory()
        if path:
            try:
                self._entry_path.delete(0, "end")
                self._entry_path.insert(0, path)
            except Exception:
                pass

    def _copy(self, entry):
        try:
            self.clipboard_clear()
            self.clipboard_append(entry.get())
        except Exception:
            pass

    def _back(self):
        if self._step > 0:
            self._step -= 1
            self._render_step()

    def _next(self):
        try:
            if self._step == 0:
                lang = "en" if self._combo_lang.get() == "English" else "id"
                set_language(lang)
                self._title.configure(text=t("wizard.welcome"))
                self._config["language"] = lang
                update_config(language=lang)
            elif self._step == 1:
                update_config(
                    default_download_path=self._entry_path.get(),
                    run_on_startup=self._var_startup.get(),
                )
                self._config = load_config()
            elif self._step == 2:
                mark_first_run_completed()
                if self._on_finish:
                    try:
                        self._on_finish()
                    except Exception:
                        pass
                self.destroy()
                return
        except Exception:
            pass

        self._step += 1
        self._render_step()
