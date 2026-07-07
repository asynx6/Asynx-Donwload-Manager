"""AsynxDL — AddDownloadWindow (Brutalist W98 mono-grey).

Minimal add-download dialog: URL + speed limit + Start Download button.
"""

import threading
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


def _encode_url(url: str) -> str:
    """Pastikan URL aman untuk requests: encode spasi dan karakter non-ASCII.

    Banyak user paste URL dari browser yang masih mengandung spasi literal.
    requests akan error kalau URL mengandung spasi; kita encode path-nya.
    """
    try:
        from urllib.parse import urlparse, urlunparse, quote
        parsed = urlparse(url)
        safe_path = quote(parsed.path, safe="/")
        safe_params = quote(parsed.params, safe="/")
        safe_query = quote(parsed.query, safe="&=")
        safe_fragment = quote(parsed.fragment, safe="")
        return urlunparse((
            parsed.scheme, parsed.netloc, safe_path,
            safe_params, safe_query, safe_fragment,
        ))
    except Exception:
        return url


class AddDownloadWindow(ctk.CTkToplevel):
    """Brutalist ‘Add Download’ modal dengan validasi langsung."""

    def __init__(self, master, api: APIClient, on_added=None,
                 default_path: str = "", mode: str = "light", **kwargs):
        tk = theme.tokens_for(mode)
        super().__init__(master, fg_color=tk["BG2"], **kwargs)
        self.title(t("add.title"))
        self.geometry("480x360")
        self.minsize(400, 320)
        self._api = api
        self._on_added = on_added
        self._default_path = default_path
        self._mode = mode
        self._valid_url = False
        self._result: dict = {}
        self.configure(fg_color=tk["BG2"])

        try:
            self.transient(self.winfo_toplevel())
        except Exception:
            pass
        self.after(80, self._center_safe)
        self.after(120, self._focus_url)

        self._build_ui()

    def _center_safe(self) -> None:
        """Re-center jendela SETELAH mapped, dengan clamp ke monitor."""
        try:
            self.update_idletasks()
            W, H = 480, 340
            try:
                parent = self.winfo_toplevel()
                pw, ph = parent.winfo_width(), parent.winfo_height()
                px, py = parent.winfo_x(), parent.winfo_y()
                if px < 0 or py < 0 or pw < 100 or ph < 100:
                    raise ValueError("bad parent")
                cx = px + (pw - W) // 2
                cy = py + (ph - H) // 2
            except Exception:
                cx, cy = None, None

            if cx is None:
                try:
                    sw = self.winfo_screenwidth()
                    sh = self.winfo_screenheight()
                    cx = (sw - W) // 2
                    cy = (sh - H) // 2
                except Exception:
                    cx, cy = 80, 80

            try:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                cx = max(0, min(int(cx), int(sw - W)))
                cy = max(0, min(int(cy), int(sh - H)))
            except Exception:
                pass

            self.geometry(f"{W}x{H}+{cx}+{cy}")
            self.lift()
            self.update_idletasks()
        except Exception:
            pass

    def _focus_url(self) -> None:
        """Focus ke URL field SETELAH window sudah mapped & centered."""
        try:
            self._entry_url.focus_force()
        except Exception:
            pass

    def _build_ui(self) -> None:
        tk = theme.tokens_for(self._mode)

        # Footer — primary full-width "Start Download" button + status label.
        foot = ctk.CTkFrame(self, fg_color=tk["BG3"],
                            corner_radius=theme.CORNER_NONE,
                            border_width=1, border_color=tk["BORDER"])
        foot.pack(fill="x", side="bottom", padx=10, pady=(6, 10))
        foot.pack_propagate(False)
        foot.configure(height=76)

        self._lbl_status = ctk.CTkLabel(
            foot, text="", font=theme.font(10), text_color=tk["FG2"]
        )
        self._lbl_status.pack(side="top", fill="x", padx=8, pady=(4, 0))

        self._btn_download = ctk.CTkButton(
            foot,
            text=t("btn.start", default="⬇ Start Download"),
            height=42,
            corner_radius=theme.CORNER_NONE,
            font=theme.font(12, bold=True),
            fg_color=tk["ACCENT"], hover_color=tk["ACCENT_H"],
            text_color=tk["SEL_FG"], border_width=1,
            border_color=tk["BORDER2"],
            command=self._start,
        )
        self._btn_download.pack(side="top", fill="x", expand=True,
                                padx=8, pady=(4, 6))
        # Disable awal sampai URL valid.
        self._set_button_enabled(False)

        # Body container
        body = ctk.CTkFrame(self, fg_color="transparent",
                            corner_radius=theme.CORNER_NONE)
        body.pack(fill="both", expand=True, padx=10, pady=6)
        body.grid_columnconfigure(0, weight=1)

        # URL field
        self._entry_url = self._make_row(body, 0, t("add.url"),
                                         placeholder="https://...")
        self._entry_url.bind("<KeyRelease>",
                             lambda _e: self._on_url_changed())
        self._entry_url.bind("<<Paste>>",
                             lambda _e: self.after(10, self._on_url_changed))

        # Speed limit field
        self._entry_speed_limit = self._make_row(
            body, 1, t("add.speed_limit"), placeholder="0", current="0")

        # Esc / Enter shortcut
        self.bind("<Return>", lambda _e: self._start())
        self.bind("<Escape>", lambda _e: self.destroy())

        self._entry_url.focus()

    def _make_row(self, master, rowidx, label, placeholder: str = "",
                  current: str = ""):
        tk = theme.tokens_for(self._mode)
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

    def _on_url_changed(self) -> None:
        """Auto-validate URL setiap ketukan — active/disable primary button."""
        tk = theme.tokens_for(self._mode)
        url = self._get_url()
        valid = _is_valid_url(url)
        self._valid_url = valid

        if valid:
            try:
                self._entry_url.configure(border_color=tk["BORDER2"],
                                          border_width=1)
            except Exception:
                pass
            self._set_status("")
            self._set_button_enabled(True)
        else:
            try:
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
        tk = theme.tokens_for(self._mode)
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

    def _set_status(self, message: str) -> None:
        try:
            self._lbl_status.configure(text=message)
        except Exception:
            pass

    def _start(self):
        if not self._valid_url:
            return
        url = self._get_url()
        if not _is_valid_url(url):
            self._on_url_changed()
            return
        try:
            limit = int(self._entry_speed_limit.get() or 0)
        except ValueError:
            limit = 0

        self._set_button_enabled(False)
        self._set_status(t("add.starting", default="Starting..."))

        def do_add():
            try:
                encoded_url = _encode_url(url)
                result = self._api.add_download(encoded_url, "", self._default_path, limit)
                self._result = result
                if result.get("error"):
                    self.after(0, lambda: self._set_status(
                        t("add.error", default="Failed: {0}").format(result["error"])
                    ))
                    self.after(0, lambda: self._set_button_enabled(True))
                    return
                if self._on_added:
                    try:
                        self._on_added()
                    except Exception:
                        pass
                self.after(0, self.destroy)
            except Exception as exc:
                self.after(0, lambda: self._set_status(
                    t("add.error", default="Failed: {0}").format(exc)
                ))
                self.after(0, lambda: self._set_button_enabled(True))

        threading.Thread(target=do_add, daemon=True).start()


__all__: list[str] = ["AddDownloadWindow"]
