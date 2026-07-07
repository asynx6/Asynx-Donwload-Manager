"""AsynxDL — MainWindow.

Kini tanpa sidebar, tanpa pengaturanWindow terpisah. Top: TabManager dengan
tab Home (download list) dan tab Setting (settings panel). Branding: hanya
satu logo kecil di sebelah kiri tab-bar (di-load dari C:\\Users\\asynx\\Downloads\\AsynxDL\\Logo.png
atau fallback ke frontend/ui/assets/icons/logo.png).
"""

import datetime
import os
import threading
from typing import Callable

import customtkinter as ctk
from PIL import Image

from frontend.ui import theme
from frontend.ui.api_client import APIClient
from frontend.ui.i18n import t, set_language, get_language
from frontend.ui.windows.home_panel import HomePanel
from frontend.ui.windows.settings_panel import SettingsPanel


_LOCAL_LOGO_CANDIDATE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "Logo.png")
)
_STATE_HEARTBEAT_INTERVAL_MS = 10_000


def _load_logo_image(size: int = 26):
    candidates = [
        _LOCAL_LOGO_CANDIDATE,
        os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "logo.png"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "logo.jpg"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "tray.png"),
    ]
    for path in candidates:
        try:
            if path and os.path.exists(path):
                img = Image.open(path)
                return ctk.CTkImage(img, size=(size, size))
        except Exception:
            continue
    return None


class MainWindow(ctk.CTkFrame):

    def __init__(self, master, api: APIClient, on_settings_change: Callable | None = None, **kwargs):
        # Determine mode from app config, fall back to "light" for Brutalist W98.
        try:
            from backend.system.config import load_config
            cfg = load_config()
            mode = cfg.get("theme", "light")
            if mode not in ("light", "dark"):
                mode = "light"
        except Exception:
            mode = "light"

        super().__init__(master, fg_color=theme.tokens_for(mode)["BG"], corner_radius=theme.CORNER_NONE, **kwargs)
        self._api = api
        self._mode = mode
        self._on_settings_change = on_settings_change
        self._settings: dict = {}
        self._make_calls: list = []

        tk = theme.tokens_for(mode)
        self.configure(fg_color=tk["BG"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Root host
        self._host = ctk.CTkFrame(self, fg_color=tk["BG"], corner_radius=theme.CORNER_NONE)
        self._host.grid(row=0, column=0, sticky="nsew")
        self._host.grid_columnconfigure(0, weight=1)
        self._host.grid_rowconfigure(1, weight=1)

        # Top branding bar: logo + AsynxDL wordmark + tab-bar (right-aligned)
        brand_bar = ctk.CTkFrame(self._host, fg_color=tk["BG2"], corner_radius=theme.CORNER_NONE,
                                  height=theme.NAVBAR_HEIGHT, border_width=0)
        brand_bar.grid(row=0, column=0, sticky="ew")
        brand_bar.grid_columnconfigure(0, weight=0)   # logo
        brand_bar.grid_columnconfigure(1, weight=1)   # spacer
        brand_bar.grid_columnconfigure(2, weight=0)   # tab-bar
        brand_bar.grid_rowconfigure(0, weight=1)
        brand_bar.grid_propagate(False)

        # logo
        logo_img = _load_logo_image(size=26)
        if logo_img is not None:
            self._logo_label = ctk.CTkLabel(brand_bar, image=logo_img, text="")
            self._logo_label.image = logo_img
        else:
            self._logo_label = ctk.CTkLabel(
                brand_bar, text="[A]",
                font=theme.font(13, bold=True),
                text_color=tk["FG"]
            )
        self._logo_label.grid(row=0, column=0, sticky="w", padx=(12, 6), pady=4)

        ctk.CTkLabel(
            brand_bar, text="AsynxDL",
            font=theme.font(13, bold=True),
            text_color=tk["FG"]
        ).grid(row=0, column=1, sticky="w", padx=(0, 12))

        # Tab bar inline (Home | Setting) — rect buttons, square corners.
        tabs_frame = ctk.CTkFrame(brand_bar, fg_color="transparent", corner_radius=theme.CORNER_NONE)
        tabs_frame.grid(row=0, column=2, sticky="e", padx=(0, 8))
        tabs_frame.grid_rowconfigure(0, weight=1)

        self._tab_buttons: dict[str, ctk.CTkButton] = {}
        for i, (key, label) in enumerate((("home", t("app.tab.home")), ("setting", t("app.tab.setting")))):
            btn = ctk.CTkButton(
                tabs_frame, text=label,
                height=theme.TAB_HEIGHT, width=110,
                corner_radius=theme.CORNER_NONE,
                font=theme.font(11, bold=True),
                fg_color="transparent", text_color=tk["FG"],
                hover_color=tk["SEL_DEEP"],
                border_width=1, border_color=tk["BORDER"],
                command=lambda k=key: self._on_tab_click(k),
            )
            btn.grid(row=0, column=i, sticky="e", padx=(0 if i == 0 else 4, 4 if i < 1 else 0))
            self._tab_buttons[key] = btn

        # Stacked content frame; tab raises the right child.
        self._content = ctk.CTkFrame(self._host, fg_color=tk["BG2"], corner_radius=theme.CORNER_NONE)
        self._content.grid(row=1, column=0, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        self._home_panel = HomePanel(self._content, mode=self._mode)
        self._settings_panel = SettingsPanel(self._content, mode=self._mode)
        for p in (self._home_panel, self._settings_panel):
            p.grid(row=0, column=0, sticky="nsew")

        self._current_tab = "home"
        self._on_tab_click("home")

        self.after(60, self._boot_panels)
        self.after(_STATE_HEARTBEAT_INTERVAL_MS, self._state_heartbeat)

    # ------------------------------------------------------------------ helpers

    def _on_tab_click(self, key: str) -> None:
        if key not in self._tab_buttons:
            return
        tk = theme.tokens_for(self._mode)
        for k, btn in self._tab_buttons.items():
            if k == key:
                btn.configure(
                    fg_color=tk["SEL_BG"],
                    text_color=tk["SEL_FG"],
                    border_color=tk["BORDER2"],
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=tk["FG"],
                    border_color=tk["BORDER"],
                )
        if key == "home":
            self._home_panel.tkraise()
            try:
                self._home_panel.on_show()
            except Exception:
                pass
        elif key == "setting":
            self._settings_panel.tkraise()
            try:
                self._settings_panel.on_show()
            except Exception:
                pass
        self._current_tab = key

    def _boot_panels(self) -> None:
        try:
            self._home_panel.attach(self._api, {})
        except Exception as exc:
            print(f"[MainWindow] home attach failed: {exc}")
        try:
            self._settings_panel.attach(self._api, self._on_settings_saved)
        except Exception as exc:
            print(f"[MainWindow] settings attach failed: {exc}")

    def _on_settings_saved(self) -> None:
        try:
            self._settings = self._api.get_settings()
        except Exception:
            pass
        try:
            self._home_panel.refresh_text(mode=self._settings.get("theme", self._mode))
        except Exception:
            pass
        try:
            self._settings_panel.refresh_text(mode=self._settings.get("theme", self._mode))
        except Exception:
            pass
        if callable(self._on_settings_change):
            try:
                self._on_settings_change(self._settings)
            except Exception:
                pass

    # ------------------------------------------------------------------ public

    def refresh(self) -> None:
        try:
            self._home_panel._load_data()
        except Exception:
            pass

    def open_settings(self) -> None:
        try:
            self._on_tab_click("setting")
        except Exception:
            pass

    # ------------------------------------------------------------------ heartbeat

    def _state_heartbeat(self) -> None:
        def _beat() -> None:
            try:
                log_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AsynxDL", "logs")
                os.makedirs(log_dir, exist_ok=True)
                state_path = os.path.join(log_dir, "state.log")
                root = self.winfo_toplevel()
                state = root.state()
                geom = root.geometry()
                mapped = root.winfo_ismapped()
                with open(state_path, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.datetime.now().isoformat()} state={state} geometry={geom} mapped={mapped}\n")
                # Audit-fix M4: rotate state.log saat >256KB (1 rolling backup).
                try:
                    if os.path.getsize(state_path) > 256 * 1024:
                        bak = state_path + ".1"
                        try:
                            os.replace(state_path, bak)
                        except OSError:
                            pass
                except OSError:
                    pass
            except Exception:
                pass
            try:
                self.after(_STATE_HEARTBEAT_INTERVAL_MS, _beat)
            except Exception:
                return
        try:
            _beat()
        except Exception:
            pass

    def refresh_text(self) -> None:
        """Apply latest language/theme ke seluruh MainWindow dan child panels."""
        try:
            from backend.system.config import load_config
            cfg = load_config()
        except Exception:
            cfg = {}
        try:
            lang = cfg.get("language", get_language())
            set_language(lang)
        except Exception:
            pass
        try:
            mode = cfg.get("theme", self._mode)
            if mode not in ("light", "dark"):
                mode = "light"
            ctk.set_appearance_mode(mode)
            theme.set_mode(mode)
            self._mode = mode
        except Exception:
            pass
        tk = theme.tokens_for(self._mode)
        try:
            self.configure(fg_color=tk["BG"])
        except Exception:
            pass
        try:
            home_btn = self._tab_buttons.get("home")
            if home_btn is not None:
                home_btn.configure(text=t("app.tab.home"), text_color=tk["FG"])
        except Exception:
            pass
        try:
            settings_btn = self._tab_buttons.get("setting")
            if settings_btn is not None:
                settings_btn.configure(text=t("app.tab.setting"), text_color=tk["FG"])
        except Exception:
            pass
        try:
            if self._home_panel is not None:
                self._home_panel.refresh_text(mode=self._mode)
        except Exception:
            pass
        try:
            if self._settings_panel is not None:
                self._settings_panel.refresh_text(mode=self._mode)
        except Exception:
            pass
        try:
            theme.set_mode(self._mode)
            theme.repaint(self, mode=self._mode)
        except Exception:
            pass
        # Re-apply active tab styling after global repaint.
        try:
            self._on_tab_click(self._current_tab)
        except Exception:
            pass


__all__: list[str] = ["MainWindow"]
