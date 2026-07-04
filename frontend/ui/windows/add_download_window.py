"""AsynxDL — AddDownloadWindow (Brutalist W98 mono-grey).

Kotak kaku untuk menambahkan unduhan baru. Spesifikasi v1.1.0:
- Primary button “⬇ Unduh” (idiomatic) awalnya DISABLED sampai URL valid.
- Inline URL error label (errors.invalid_url) — bukan modal crash.
- Live validation: <KeyRelease> di URL field → auto-enable tombol.
- Tidak ada tombol “Tutup” karena destruktor otomatis setelah add.
"""

import threading
import tkinter.filedialog as filedialog
from urllib.parse import urlparse

import customtkinter as ctk

from frontend.ui import theme
from frontend.ui.api_client import APIClient
from frontend.ui.i18n import t


def _is_valid_url(url: str) -> bool:
    """Validasi URL dengan urlparse — http(s) + minimal host."""
    try:
        if not url:
            return False
        if not (url.startswith("http://") or url.startswith("https://")):
            return False
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme)
    except Exception:
        return False


class AddDownloadWindow(ctk.CTkToplevel):
    """Brutalist ‘Add Download’ modal dengan validasi langsung."""

    def __init__(self, master, api: APIClient, on_added=None,
                 default_path: str = "", mode: str = "light", **kwargs):
        tk = theme.tokens(mode)
        super().__init__(master, fg_color=tk["BG2"], **kwargs)
        self.title(t("add.title"))
        self.geometry("540x460")
        self.resizable(False, False)
        self._api = api
        self._on_added = on_added
        self._default_path = default_path
        self._mode = mode
        self._valid_url = False
        self.configure(fg_color=tk["BG2"])

        # Center on parent
        self.update_idletasks()
        try:
            parent = self.winfo_toplevel()
            px = parent.winfo_x() + (parent.winfo_width() - 540) // 2
            py = parent.winfo_y() + (parent.winfo_height() - 460) // 2
            self.geometry(f"540x460+{px}+{py}")
        except Exception:
            pass

        # Title bar — bordered
        bar = ctk.CTkFrame(self, fg_color=tk["BG3"], corner_radius=theme.CORNER_NONE,
                           border_width=1, border_color=tk["BORDER"])
        bar.pack(fill="x", padx=10, pady=(10, 6))
        ctk.CTkLabel(bar, text=t("add.title"), font=theme.font(13, bold=True),
                     text_color=tk["FG"]).pack(side="left", padx=12, pady=10)

        # Body container
        body = ctk.CTkFrame(self, fg_color="transparent",
                            corner_radius=theme.CORNER_NONE)
        body.pack(fill="both", expand=True, padx=10, pady=6)
        body.grid_columnconfigure(0, weight=1)

        # URL field (with live error label)
        self._entry_url = self._make_row(body, 0, t("add.url"),
                                         placeholder="https://...")
        self._entry_url.bind("<KeyRelease>",
                             lambda _e: self._on_url_changed())
        # Paste juga harus memvalidasi
        self._entry_url.bind("<<Paste>>",
                             lambda _e: self.after(10, self._on_url_changed))

        # Inline URL error label (tersembunyi sampai invalid)
        self._url_error = ctk.CTkLabel(
            body, text="", font=theme.font(10),
            text_color=tk["ERROR"], anchor="w",
        )
        self._url_error.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 6))

        # Filename field
        self._entry_filename = self._make_row(
            body, 2, t("add.filename"), placeholder="optional")

        # Save path with browse
        self._make_path_row(body, 3, t("add.save_path"), current=default_path)

        # Speed limit
        self._entry_speed_limit = self._make_row(
            body, 4, t("add.speed_limit"), placeholder="0", current="0")

        # Hint
        ctk.CTkLabel(body, text=t("add.speed_hint"), font=theme.font(10),
                     text_color=tk["FG2"], anchor="w", justify="left",
                     wraplength=480).grid(row=5, column=0, sticky="w",
                                          pady=(0, 6))

        # Footer - primary [⬇ Unduh] only (auto-destructive)
        foot = ctk.CTkFrame(self, fg_color="transparent",
                            corner_radius=theme.CORNER_NONE)
        foot.pack(fill="x", padx=10, pady=(0, 10))
        foot.grid_columnconfigure(0, weight=1)
        foot.grid_columnconfigure(1, weight=0)

        # Spacer kiri
        ctk.CTkLabel(foot, text="", fg_color="transparent").grid(
            row=0, column=0, sticky="ew")

        self._btn_download = ctk.CTkButton(
            foot, text=t("btn.download", default="⬇ Unduh"),
            width=170, height=theme.BUTTON_HEIGHT,
            corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
            fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
            text_color=tk["SEL_FG"], border_width=1,
            border_color=tk["BORDER2"], command=self._start,
        )
        self._btn_download.grid(row=0, column=1)
        # Disable awal sampai URL valid.
        self._set_button_enabled(False)

        # Esc / Enter shortcut
        self.bind("<Return>", lambda _e: self._start())
        self.bind("<Escape>", lambda _e: self.destroy())

        self._entry_url.focus()

    # ------------------------------------------------------------------
    # Row helpers (unchanged behaviour)
    # ------------------------------------------------------------------

    def _make_row(self, master, rowidx, label, placeholder: str = "",
                  current: str = ""):
        tk = theme.tokens(self._mode)
        wrap = ctk.CTkFrame(master, fg_color=tk["BG3"],
                            corner_radius=theme.CORNER_NONE,
                            border_width=1, border_color=tk["BORDER"])
        wrap.grid(row=rowidx, column=0, sticky="ew", pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text=label, font=theme.font(11),
                     text_color=tk["FG"]).grid(row=0, column=0, sticky="w",
                                                padx=10, pady=(10, 0))
        entry = ctk.CTkEntry(wrap, height=theme.INPUT_HEIGHT,
                             corner_radius=theme.CORNER_NONE,
                             font=theme.font(11), fg_color=tk["BG3"],
                             text_color=tk["FG"], border_width=1,
                             border_color=tk["BORDER2"],
                             placeholder_text=placeholder,
                             placeholder_text_color=tk["FG2"])
        entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 10))
        if current:
            entry.insert(0, current)
        return entry

    def _make_path_row(self, master, rowidx, label, current: str = ""):
        tk = theme.tokens(self._mode)
        wrap = ctk.CTkFrame(master, fg_color=tk["BG3"],
                            corner_radius=theme.CORNER_NONE,
                            border_width=1, border_color=tk["BORDER"])
        wrap.grid(row=rowidx, column=0, sticky="ew", pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text=label, font=theme.font(11),
                     text_color=tk["FG"]).grid(row=0, column=0, sticky="w",
                                                padx=10, pady=(10, 0))
        sub = ctk.CTkFrame(wrap, fg_color="transparent",
                           corner_radius=theme.CORNER_NONE)
        sub.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 10))
        sub.grid_columnconfigure(0, weight=1)
        self._entry_path = ctk.CTkEntry(
            sub, height=theme.INPUT_HEIGHT, corner_radius=theme.CORNER_NONE,
            font=theme.font(11), fg_color=tk["BG3"], text_color=tk["FG"],
            border_width=1, border_color=tk["BORDER2"])
        self._entry_path.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        if current:
            self._entry_path.insert(0, current)
        ctk.CTkButton(
            sub, text=t("btn.browse"), width=82, height=theme.INPUT_HEIGHT,
            corner_radius=theme.CORNER_NONE, font=theme.font(11, bold=True),
            fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
            text_color=tk["SEL_FG"], border_width=1,
            border_color=tk["BORDER2"], command=self._browse).grid(
                row=0, column=1)

    def _browse(self):
        path = filedialog.askdirectory()
        if path:
            try:
                self._entry_path.delete(0, "end")
                self._entry_path.insert(0, path)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Validation flow
    # ------------------------------------------------------------------

    def _on_url_changed(self) -> None:
        """Auto-validate URL setiap ketukan — active/disable primary button."""
        tk = theme.tokens(self._mode)
        url = self._get_url()
        valid = _is_valid_url(url)
        self._valid_url = valid

        if valid:
            try:
                self._url_error.configure(text="")
                self._entry_url.configure(border_color=tk["BORDER2"],
                                          border_width=1)
            except Exception:
                pass
            self._set_button_enabled(True)
        else:
            msg = t("errors.invalid_url", default="URL tidak valid")
            try:
                self._url_error.configure(text=msg if url else "")
                # tebalkan border field untuk sinyal visual (tetap abu2).
                if url:
                    self._entry_url.configure(border_color=tk["BORDER2"],
                                              border_width=2)
                else:
                    self._entry_url.configure(border_color=tk["BORDER"],
                                              border_width=1)
            except Exception:
                pass
            self._set_button_enabled(False)

    def _get_url(self) -> str:
        try:
            return self._entry_url.get().strip()
        except Exception:
            return ""

    def _set_button_enabled(self, enabled: bool) -> None:
        """Disable button aria: fg jadi SEL_BG (disabled-look) dan
        state internal ke disabled supaya command callback tak fire."""
        tk = theme.tokens(self._mode)
        try:
            if enabled:
                self._btn_download.configure(
                    fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
                    text_color=tk["SEL_FG"], border_color=tk["BORDER2"],
                    state="normal")
            else:
                self._btn_download.configure(
                    fg_color=tk["SEL_BG"], hover_color=tk["SEL_BG"],
                    text_color=tk["SEL_FG"], border_color=tk["BORDER"],
                    state="disabled")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Download submission
    # ------------------------------------------------------------------

    def _start(self):
        # Extra safety: jika somehow _valid_url False,
        # jangan fire (CTk state=disabled sudah block keyboard tapi
        # shortcut Enter mungkin masih tembus).
        if not self._valid_url:
            return
        url = self._get_url()
        if not _is_valid_url(url):
            self._on_url_changed()
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


__all__: list[str] = ["AddDownloadWindow"]
