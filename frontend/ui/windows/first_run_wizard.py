import os
import tkinter.filedialog as filedialog
import customtkinter as ctk

from backend.system.config import load_config, update_config, mark_first_run_completed
from frontend.ui.i18n import t, set_language


class FirstRunWizard(ctk.CTkToplevel):
    """Wizard setup pertama kali aplikasi dijalankan dengan tampilan modern."""

    ACCENT = "#6366F1"
    ACCENT_HOVER = "#4F46E5"
    BG = ("#FFFFFF", "#18181E")
    TEXT_PRIMARY = ("#111827", "#F9FAFB")
    TEXT_SECONDARY = ("#6B7280", "#9CA3AF")

    def __init__(self, master, on_finish=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title(t("wizard.welcome"))
        self.geometry("620x480")
        self.resizable(False, False)
        self._on_finish = on_finish
        self._config = load_config()
        self._step = 0
        self.configure(fg_color=self.BG)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._header = ctk.CTkFrame(self, fg_color="transparent")
        self._header.grid(row=0, column=0, sticky="ew", padx=36, pady=(36, 8))
        self._header.grid_columnconfigure(0, weight=1)

        self._title = ctk.CTkLabel(
            self._header, text=t("wizard.welcome"), font=("Arial", 22, "bold"),
            text_color=self.TEXT_PRIMARY
        )
        self._title.grid(row=0, column=0, sticky="w")

        self._subtitle = ctk.CTkLabel(
            self._header, text=t("wizard.subtitle"), font=("Arial", 13),
            text_color=self.TEXT_SECONDARY
        )
        self._subtitle.grid(row=1, column=0, sticky="w")

        # Step dots
        self._dots = ctk.CTkFrame(self._header, fg_color="transparent")
        self._dots.grid(row=0, column=1, rowspan=2, sticky="e")
        self._dot_labels = []
        for i in range(3):
            dot = ctk.CTkLabel(self._dots, text="●", font=("Arial", 12), text_color=self.TEXT_SECONDARY)
            dot.grid(row=0, column=i, padx=4)
            self._dot_labels.append(dot)

        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.grid(row=1, column=0, sticky="nsew", padx=36, pady=10)
        self._container.grid_columnconfigure(0, weight=1)

        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_frame.grid(row=2, column=0, sticky="ew", padx=36, pady=(0, 28))
        self._btn_frame.grid_columnconfigure(0, weight=1)

        self._btn_next = ctk.CTkButton(
            self._btn_frame, text=t("btn.continue"), width=130, height=38, corner_radius=10,
            font=("Arial", 13, "bold"), fg_color=self.ACCENT, hover_color=self.ACCENT_HOVER,
            command=self._next
        )
        self._btn_next.grid(row=0, column=1, padx=(8, 0))

        self._render_step()
        self._center_on_parent()

    def _center_on_parent(self):
        self.update_idletasks()
        parent = self.winfo_toplevel()
        px = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _update_dots(self):
        for i, dot in enumerate(self._dot_labels):
            dot.configure(text_color=self.ACCENT if i == self._step else self.TEXT_SECONDARY)

    def _render_step(self):
        for w in self._container.winfo_children():
            w.destroy()
        self._update_dots()

        if self._step == 0:
            ctk.CTkLabel(
                self._container, text=t("wizard.language"), font=("Arial", 14, "bold"),
                text_color=self.TEXT_PRIMARY
            ).grid(row=0, column=0, sticky="w", pady=(0, 8))
            self._combo_lang = ctk.CTkComboBox(
                self._container, values=["English", "Bahasa Indonesia"], height=38, corner_radius=10,
                font=("Arial", 13)
            )
            self._combo_lang.set("English" if self._config.get("language", "en") == "en" else "Bahasa Indonesia")
            self._combo_lang.grid(row=1, column=0, sticky="ew")

        elif self._step == 1:
            ctk.CTkLabel(
                self._container, text=t("wizard.download_path"), font=("Arial", 14, "bold"),
                text_color=self.TEXT_PRIMARY
            ).grid(row=0, column=0, sticky="w", pady=(0, 8))
            path_frame = ctk.CTkFrame(self._container, fg_color="transparent")
            path_frame.grid(row=1, column=0, sticky="ew", pady=(0, 16))
            path_frame.grid_columnconfigure(0, weight=1)
            self._entry_path = ctk.CTkEntry(
                path_frame, height=38, corner_radius=10, font=("Arial", 13)
            )
            self._entry_path.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            self._entry_path.insert(0, self._config.get("default_download_path", ""))
            ctk.CTkButton(
                path_frame, text=t("btn.browse"), width=90, height=36, corner_radius=10,
                font=("Arial", 12), command=self._browse
            ).grid(row=0, column=1)

            ctk.CTkLabel(
                self._container, text=t("wizard.startup"), font=("Arial", 14, "bold"),
                text_color=self.TEXT_PRIMARY
            ).grid(row=2, column=0, sticky="w", pady=(12, 8))
            self._var_startup = ctk.BooleanVar(value=self._config.get("run_on_startup", False))
            ctk.CTkCheckBox(
                self._container, text=t("wizard.startup"), variable=self._var_startup,
                font=("Arial", 13), text_color=self.TEXT_PRIMARY
            ).grid(row=3, column=0, sticky="w")

        elif self._step == 2:
            token = self._config.get("api_secret_token", "")
            ctk.CTkLabel(
                self._container, text=t("wizard.token_title"), font=("Arial", 14, "bold"),
                text_color=self.TEXT_PRIMARY
            ).grid(row=0, column=0, sticky="w", pady=(0, 8))
            ctk.CTkLabel(
                self._container, text=t("wizard.token_desc"), wraplength=520, justify="left",
                font=("Arial", 12), text_color=self.TEXT_SECONDARY
            ).grid(row=1, column=0, sticky="w", pady=(0, 12))
            entry = ctk.CTkEntry(
                self._container, height=38, corner_radius=10, font=("Arial", 12)
            )
            entry.grid(row=2, column=0, sticky="ew", pady=(0, 12))
            entry.insert(0, token)
            entry.configure(state="readonly")
            ctk.CTkButton(
                self._container, text="Copy", width=90, height=34, corner_radius=10,
                font=("Arial", 12), command=lambda: self._copy(entry)
            ).grid(row=3, column=0, sticky="w")
            self._btn_next.configure(text=t("wizard.finish"))

    def _browse(self):
        path = filedialog.askdirectory()
        if path:
            self._entry_path.delete(0, "end")
            self._entry_path.insert(0, path)

    def _copy(self, entry):
        self.clipboard_clear()
        self.clipboard_append(entry.get())

    def _next(self):
        if self._step == 0:
            lang = "en" if self._combo_lang.get() == "English" else "id"
            set_language(lang)
            self._title.configure(text=t("wizard.welcome"))
            self._subtitle.configure(text=t("wizard.subtitle"))
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
                self._on_finish()
            self.destroy()
            return

        self._step += 1
        self._render_step()
