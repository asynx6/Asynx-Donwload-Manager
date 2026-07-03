"""AsynxDL — Brutalist tab switcher.

Hanya dua tab (Home / Setting). Pakai tkraise di antara stacked CTkFrame
children sehingga tidak ada window baru yang dilahirkan.
"""

from typing import Callable, Dict, Iterable

import customtkinter as ctk

from frontend.ui import theme


class TabBar(ctk.CTkFrame):
    """Baris tab horizontal — tikus Windows 98: dua tombol kotak."""

    def __init__(self, master, tabs: Iterable[tuple], on_select: Callable[[str], None], mode: str = "light", **kw):
        super().__init__(master, fg_color=theme.tokens(mode)["BG2"],
                         corner_radius=theme.CORNER_NONE,
                         height=theme.NAVBAR_HEIGHT,
                         **kw)
        self._mode = mode
        self._on_select = on_select
        self._current = None
        self._buttons: Dict[str, ctk.CTkButton] = {}

        tk = theme.tokens(mode)
        self.grid_columnconfigure(len(tuple(tabs)), weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_propagate(False)

        for i, (key, label) in enumerate(tabs):
            btn = ctk.CTkButton(
                self,
                text=label,
                height=theme.TAB_HEIGHT,
                corner_radius=theme.CORNER_NONE,
                font=theme.font(12, bold=True),
                fg_color="transparent",
                text_color=tk["FG"],
                hover_color=tk["SEL_DEEP"],
                border_width=1,
                border_color=tk["BORDER"],
                command=lambda k=key: self._on_select(k),
            )
            btn.grid(row=0, column=i, sticky="nsew", padx=(0, 1))
            self._buttons[key] = btn

        if self._buttons:
            first = next(iter(self._buttons))
            self.set_active(first)

    def set_active(self, key: str) -> None:
        if key == self._current:
            return
        tk = theme.tokens(self._mode)
        for k, btn in self._buttons.items():
            if k == key:
                btn.configure(
                    fg_color=tk["SEL_BG"],
                    text_color=tk["SEL_FG"],
                    hover_color=tk["SEL_DEEP"],
                    border_color=tk["BORDER2"],
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=tk["FG"],
                    hover_color=tk["SEL_DEEP"],
                    border_color=tk["BORDER"],
                )
        self._current = key
        self._on_select(key)


class TabManager(ctk.CTkFrame):
    """Host parent untuk banyak TabContent di-stacked.

    Anak-anak di-stacked di lokasi grid yang sama (row=0,col=0,sticky=nsew)
    dan di-tkraise sesuai tab aktif.
    """

    def __init__(self, master, tabs: Iterable[tuple], content_factory: Callable[[ctk.CTkFrame, str], ctk.CTkFrame], mode: str = "light", **kw):
        """tabs: iterable of (key, label).
        content_factory(parent_frame, mode) -> CTkFrame instance."""
        super().__init__(master, fg_color=theme.tokens(mode)["BG2"],
                         corner_radius=theme.CORNER_NONE, **kw)
        self._mode = mode
        self._content_factory = content_factory
        self._panes: Dict[str, ctk.CTkFrame] = {}
        self._current: str | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self._tabbar = TabBar(self, tabs, self._on_tab_selected, mode=mode)
        self._tabbar.grid(row=0, column=0, sticky="ew")

        self._stack = ctk.CTkFrame(self, fg_color="transparent", corner_radius=theme.CORNER_NONE)
        self._stack.grid(row=1, column=0, sticky="nsew")
        self._stack.grid_columnconfigure(0, weight=1)
        self._stack.grid_rowconfigure(0, weight=1)

        for key, _label in tabs:
            pane = content_factory(self._stack, self._mode)
            pane.grid(row=0, column=0, sticky="nsew")
            self._panes[key] = pane

        # initial active
        if self._panes:
            self._on_tab_selected(next(iter(self._panes)))

    def _on_tab_selected(self, key: str) -> None:
        if self._current == key:
            return
        pane = self._panes.get(key)
        if pane is None:
            return
        pane.tkraise()
        self._current = key
        # notify content dengan hook on_show jika tersedia
        on_show = getattr(pane, "on_show", None)
        if callable(on_show):
            try:
                on_show()
            except Exception:
                pass

    def get(self, key: str):
        return self._panes.get(key)


__all__: Iterable[str] = ("TabBar", "TabManager",)
