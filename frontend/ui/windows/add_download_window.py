"""AsynxDL — AddDownloadWindow (Brutalist W98 mono-grey).

Kotak kaku: square edges (CORNER_NONE), mono-grey palette via theme.tokens,
no rounded corners. Theme-aware via mode parameter.
"""
import threading
import tkinter.filedialog as filedialog

import customtkinter as ctk

from frontend.ui import theme
from frontend.ui.api_client import APIClient
from frontend.ui.i18n import t


class AddDownloadWindow(ctk.CTkToplevel):
    """Brutalist 'Add Download' modal."""

    def __init__(self, master, api: APIClient, on_added=None, default_path: str = "",
                 mode: str = "light", **kwargs):
        tk = theme.tokens(mode)
        super().__init__(master, fg_color=tk["BG2"], **kwargs)
        self.title(t("add.title"))
        self.geometry("540x440")
        self.resizable(False, False)
        self._api = api
        self._on_added = on_added
        self._default_path = default_path
        self._mode = mode
        self.configure(fg_color=tk["BG2"])

        # Center on parent
        self.update_idletasks()
        try:
            parent = self.winfo_toplevel()
            px = parent.winfo_x() + (parent.winfo_width() - 540) // 2
            py = parent.winfo_y() + (parent.winfo_height() - 440) // 2
            self.geometry(f"540x440+{px}+{py}")
        except Exception:
            pass

        # Title bar — bordered
        bar = ctk.CTkFrame(self, fg_color=tk["BG3"], corner_radius=theme.CORNER_NONE,
                          border_width=1, border_color=tk["BORDER"])
        bar.pack(fill="x", padx=10, pady=(10, 6))
        ctk.CTkLabel(bar, text=t("add.title"), font=theme.font(13, bold=True),
                    text_color=tk["FG"]).pack(side="left", padx=12, pady=10)

        # Body container
        body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=theme.CORNER_NONE)
        body.pack(fill="both", expand=True, padx=10, pady=6)
        body.grid_columnconfigure(0, weight=1)

        # URL field
        self._entry_url = self._make_row(body, 0, t("add.url"), placeholder="https://...")
        # Filename field
        self._entry_filename = self._make_row(body, 1, t("add.filename"),
                                             placeholder="optional")
        # Save path with browse button (custom variant)
        self._make_path_row(body, 2, t("add.save_path"), current=default_path)
        # Speed limit
        self._entry_speed_limit = self._make_row(body, 3, t("add.speed_limit"),
                                                placeholder="0", current="0")
        # Hint
        ctk.CTkLabel(body, text=t("add.speed_hint"), font=theme.font(10),
                    text_color=tk["FG2"], anchor="w", justify="left",
                    wraplength=480).grid(row=4, column=0, sticky="w", pady=(0, 6))

        # Footer — secondary [Close] + primary [Start]
        foot = ctk.CTkFrame(self, fg_color="transparent", corner_radius=theme.CORNER_NONE)
        foot.pack(fill="x", padx=10, pady=(0, 10))
        foot.grid_columnconfigure(0, weight=1)
        foot.grid_columnconfigure(1, weight=0)
        foot.grid_columnconfigure(2, weight=0)
        ctk.CTkLabel(foot, text="", fg_color="transparent").grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(foot, text=t("btn.close"), width=110, height=theme.BUTTON_HEIGHT,
                     corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
                     fg_color="transparent", hover_color=tk["SEL_DEEP"],
                     text_color=tk["FG"], border_width=1, border_color=tk["BORDER"],
                     command=self.destroy).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(foot, text=t("btn.start"), width=110, height=theme.BUTTON_HEIGHT,
                     corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
                     fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
                     text_color=tk["SEL_FG"], border_width=1, border_color=tk["BORDER2"],
                     command=self._start).grid(row=0, column=2)

        self._entry_url.focus()

    # ------------------------------------------------------------------ row helpers

    def _make_row(self, master, rowidx, label, placeholder: str = "", current: str = ""):
        """Square bordered form-row. Returns the entry widget."""
        tk = theme.tokens(self._mode)
        wrap = ctk.CTkFrame(master, fg_color=tk["BG3"], corner_radius=theme.CORNER_NONE,
                           border_width=1, border_color=tk["BORDER"])
        wrap.grid(row=rowidx, column=0, sticky="ew", pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text=label, font=theme.font(11),
                    text_color=tk["FG"]).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
        entry = ctk.CTkEntry(wrap, height=theme.INPUT_HEIGHT, corner_radius=theme.CORNER_NONE,
                            font=theme.font(11), fg_color=tk["BG3"],
                            text_color=tk["FG"], border_width=1, border_color=tk["BORDER2"],
                            placeholder_text=placeholder, placeholder_text_color=tk["FG2"])
        entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 10))
        if current:
            entry.insert(0, current)
        return entry

    def _make_path_row(self, master, rowidx, label, current: str = ""):
        """Variant of _make_row dengan tombol Browse."""
        tk = theme.tokens(self._mode)
        wrap = ctk.CTkFrame(master, fg_color=tk["BG3"], corner_radius=theme.CORNER_NONE,
                           border_width=1, border_color=tk["BORDER"])
        wrap.grid(row=rowidx, column=0, sticky="ew", pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text=label, font=theme.font(11),
                    text_color=tk["FG"]).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
        sub = ctk.CTkFrame(wrap, fg_color="transparent", corner_radius=theme.CORNER_NONE)
        sub.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 10))
        sub.grid_columnconfigure(0, weight=1)
        self._entry_path = ctk.CTkEntry(sub, height=theme.INPUT_HEIGHT,
                                       corner_radius=theme.CORNER_NONE, font=theme.font(11),
                                       fg_color=tk["BG3"], text_color=tk["FG"],
                                       border_width=1, border_color=tk["BORDER2"])
        self._entry_path.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entry_path.insert(0, current)
        ctk.CTkButton(sub, text=t("btn.browse"), width=82, height=theme.INPUT_HEIGHT,
                     corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
                     fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
                     text_color=tk["SEL_FG"], border_width=1, border_color=tk["BORDER2"],
                     command=self._browse).grid(row=0, column=1)

    def _browse(self):
        path = filedialog.askdirectory()
        if path:
            try:
                self._entry_path.delete(0, "end")
                self._entry_path.insert(0, path)
            except Exception:
                pass

    def _start(self):
        tk = theme.tokens(self._mode)
        url = self._entry_url.get().strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            try:
                # Brutalist warning: thicker border, mono-grey accent, no red fill.
                self._entry_url.configure(border_color=tk["BORDER2"], border_width=2)
            except Exception:
                pass
            return
        filename = self._entry_filename.get().strip()
        save_path = self._entry_path.get().strip() or self._default_path
        try:
            limit = int(self._entry_speed_limit.get() or 0)
        except ValueError:
            limit = 0

        def do_add():
            try:
                self._api.add_download(url, filename, save_path, limit)
                if self._on_added:
                    try:
                        self._on_added()
                    except Exception:
                        pass
            except Exception as exc:
                print(f"[AddDownloadWindow] failed: {exc}")
            try:
                self.after(0, self.destroy)
            except Exception:
                try:
                    self.destroy()
                except Exception:
                    pass

        threading.Thread(target=do_add, daemon=True).start()
