import customtkinter as ctk

from backend.system.config import load_config, update_config, mark_first_run_completed
from frontend.ui.i18n import t, set_language


class FirstRunWizard(ctk.CTkToplevel):
    """Wizard setup pertama kali aplikasi dijalankan."""

    def __init__(self, master, on_finish=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title(t("wizard.welcome"))
        self.geometry("560x400")
        self.resizable(False, False)
        self._on_finish = on_finish
        self._config = load_config()
        self._step = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._title = ctk.CTkLabel(self, text=t("wizard.welcome"), font=("Inter", 18, "bold"))
        self._title.grid(row=0, column=0, pady=(20, 10))

        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.grid(row=1, column=0, sticky="nsew", padx=30, pady=10)
        self._container.grid_columnconfigure(0, weight=1)

        self._btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=(0, 20))
        self._btn_frame.grid_columnconfigure(0, weight=1)

        self._btn_next = ctk.CTkButton(self._btn_frame, text=t("btn.continue"), command=self._next)
        self._btn_next.grid(row=0, column=1, padx=(8, 0))

        self._render_step()

    def _render_step(self):
        # Clear container
        for w in self._container.winfo_children():
            w.destroy()

        if self._step == 0:
            ctk.CTkLabel(self._container, text=t("wizard.language"), font=("Inter", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
            self._combo_lang = ctk.CTkComboBox(self._container, values=["English", "Bahasa Indonesia"])
            self._combo_lang.set("English" if self._config.get("language", "en") == "en" else "Bahasa Indonesia")
            self._combo_lang.grid(row=1, column=0, sticky="ew")

        elif self._step == 1:
            import tkinter.filedialog as filedialog
            ctk.CTkLabel(self._container, text=t("wizard.download_path"), font=("Inter", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
            path_frame = ctk.CTkFrame(self._container, fg_color="transparent")
            path_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
            path_frame.grid_columnconfigure(0, weight=1)
            self._entry_path = ctk.CTkEntry(path_frame)
            self._entry_path.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            self._entry_path.insert(0, self._config.get("default_download_path", ""))
            ctk.CTkButton(path_frame, text=t("btn.browse"), width=80, command=self._browse).grid(row=0, column=1)

            ctk.CTkLabel(self._container, text=t("wizard.startup"), font=("Inter", 12, "bold")).grid(row=2, column=0, sticky="w", pady=(12, 6))
            self._var_startup = ctk.BooleanVar(value=self._config.get("run_on_startup", False))
            ctk.CTkCheckBox(self._container, text=t("wizard.startup"), variable=self._var_startup).grid(row=3, column=0, sticky="w")

        elif self._step == 2:
            token = self._config.get("api_secret_token", "")
            ctk.CTkLabel(self._container, text=t("wizard.token_title"), font=("Inter", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
            ctk.CTkLabel(self._container, text=t("wizard.token_desc"), wraplength=480, justify="left").grid(row=1, column=0, sticky="w", pady=(0, 10))
            entry = ctk.CTkEntry(self._container)
            entry.grid(row=2, column=0, sticky="ew", pady=(0, 10))
            entry.insert(0, token)
            entry.configure(state="readonly")
            ctk.CTkButton(self._container, text="Copy", command=lambda: self._copy(entry)).grid(row=3, column=0, sticky="w")
            self._btn_next.configure(text=t("wizard.finish"))

    def _browse(self):
        import tkinter.filedialog as filedialog
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
