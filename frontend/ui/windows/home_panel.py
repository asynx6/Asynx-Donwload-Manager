"""AsynxDL — HomePanel (tab "Home" di MainWindow).

Mono-grey Brutalist. Toolbar kecil di atas: search box + tombol Add. Bawahnya:
filter chips All/Active/Paused/Done. Bawahnya lagi: scrollable list kartu
download. Outside tahu tidak ada — MainWindow hanya mem-package() TabManager.
"""

import os
import queue
import threading
from typing import Callable

import customtkinter as ctk

from frontend.ui import theme
from frontend.ui.api_client import APIClient
from frontend.ui.components.download_card import DownloadCard
from frontend.ui.i18n import t


_FILTERS = [
    ("all",        "tb.home.filter.all"),
    ("downloading","tb.home.filter.active"),
    ("paused",     "tb.home.filter.paused"),
    ("completed",  "tb.home.filter.done"),
]


class HomePanel(ctk.CTkFrame):
    """Tab 'Home' — muka depan AsynxDL setelah Brutalist rebuild."""

    def __init__(self, master, mode: str = "light", **kw):
        super().__init__(master, fg_color="transparent", corner_radius=theme.CORNER_NONE, **kw)
        self._mode = mode
        self._api: APIClient | None = None
        self._cards: dict[str, DownloadCard] = {}
        self._filter = "all"
        self._search = ""
        self._settings: dict = {}
        self._ui_queue: queue.Queue = queue.Queue()

        tk = theme.tokens(mode)
        self.configure(fg_color=tk["BG2"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._filter_chip_row: ctk.CTkFrame | None = None
        self._filter_buttons: dict[str, ctk.CTkButton] = {}

        self._build_toolbar()
        self._build_filter_row()
        self._build_list()

        self._empty_label = ctk.CTkLabel(
            self._list_frame,
            text=t("empty.no_downloads"),
            font=theme.font(13),
            text_color=tk["FG2"],
        )
        self._empty_label.grid(row=0, column=0, pady=80, sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

        self._process_ui_queue()

    # ------------------------------------------------------------------ API bootstrap

    def attach(self, api: APIClient, settings: dict) -> None:
        """Hook dari MainWindow setelah APIClient siap."""
        self._api = api
        self._settings = settings or {}
        self._api.set_progress_callback(lambda d: self._schedule_ui(lambda x=d: self._on_progress(x)))
        try:
            self._api.start_ws()
        except Exception:
            pass
        self.after(120, self._load_data)
        self.after(220, self._poll)
        self.after(160, self._load_settings)

    def on_show(self) -> None:
        # dipanggil TabManager ketika tab ini di-tkraise ke depan.
        self._load_data()

    # ------------------------------------------------------------------ UI build

    def _build_toolbar(self) -> None:
        tk = theme.tokens(self._mode)
        toolbar = ctk.CTkFrame(self, fg_color=tk["BG2"], corner_radius=theme.CORNER_NONE)
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        toolbar.grid_columnconfigure(0, weight=1)
        toolbar.grid_columnconfigure(2, minsize=132)

        self._entry_search = ctk.CTkEntry(
            toolbar,
            placeholder_text=t("toolbar.search_placeholder"),
            height=theme.INPUT_HEIGHT,
            corner_radius=theme.CORNER_NONE,
            font=theme.font(12),
            fg_color=tk["BG3"],
            text_color=tk["FG"],
            border_width=1,
            border_color=tk["BORDER"],
            placeholder_text_color=tk["FG2"],
        )
        self._entry_search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entry_search.bind("<KeyRelease>", lambda _e: self._on_search())

        # spacer
        ctk.CTkLabel(toolbar, text="", width=6, fg_color="transparent").grid(row=0, column=1)

        self._btn_add = ctk.CTkButton(
            toolbar,
            text=f"+ {t('btn.add')}",
            width=130, height=theme.BUTTON_HEIGHT,
            corner_radius=theme.CORNER_NONE,
            font=theme.font(12, bold=True),
            fg_color=tk["ACCENT"],
            hover_color=tk["ACCENT_H"],
            text_color=tk["SEL_FG"],
            border_width=1,
            border_color=tk["BORDER2"],
            command=self._show_add,
        )
        self._btn_add.grid(row=0, column=2, sticky="e")

    def _build_filter_row(self) -> None:
        tk = theme.tokens(self._mode)
        row = ctk.CTkFrame(self, fg_color=tk["BG2"], corner_radius=theme.CORNER_NONE)
        row.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        for i in range(len(_FILTERS)):
            row.grid_columnconfigure(i, weight=1)
        self._filter_chip_row = row

        for i, (key, label_key) in enumerate(_FILTERS):
            btn = ctk.CTkButton(
                row, text=t(label_key),
                height=theme.BUTTON_HEIGHT - 2,
                corner_radius=theme.CORNER_NONE,
                font=theme.font(11, bold=True),
                fg_color="transparent",
                text_color=tk["FG"],
                hover_color=tk["SEL_DEEP"],
                border_width=1,
                border_color=tk["BORDER"],
                command=lambda k=key: self._set_filter(k),
            )
            btn.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 4 if i < len(_FILTERS)-1 else 0))
            self._filter_buttons[key] = btn

        self._set_filter("all")

    def _build_list(self) -> None:
        tk = theme.tokens(self._mode)
        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color=tk["BG2"], corner_radius=theme.CORNER_NONE
        )
        self._list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._list_frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------ state

    def _set_filter(self, key: str) -> None:
        if key not in self._filter_buttons:
            return
        self._filter = key
        tk = theme.tokens(self._mode)
        for k, btn in self._filter_buttons.items():
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
        self._apply_filter()

    def _on_search(self) -> None:
        try:
            self._search = (self._entry_search.get() or "").strip().lower()
        except Exception:
            self._search = ""
        self._apply_filter()

    def _show_add(self) -> None:
        from frontend.ui.windows.add_download_window import AddDownloadWindow
        if not self._api:
            return
        path = (self._settings or {}).get("default_download_path", "") or os.path.expandvars("%USERPROFILE%\\Downloads")
        win = AddDownloadWindow(
            self, self._api,
            on_added=self._load_data,
            default_path=path,
            mode=self._mode,
        )
        try:
            win.grab_set()
        except Exception:
            pass

    # ------------------------------------------------------------------ data plumbing

    def _load_data(self) -> None:
        if not self._api:
            return
        def _do() -> None:
            try:
                items = self._api.list_downloads()
                self._schedule_ui(lambda it=items: self._render(it))
            except Exception as exc:
                print(f"[HomePanel] load failed: {exc}")
        threading.Thread(target=_do, daemon=True).start()

    def _poll(self) -> None:
        try:
            self._load_data()
            self.after(2000, self._poll)
        except Exception:
            pass

    def _load_settings(self) -> None:
        if not self._api:
            return
        def _do() -> None:
            try:
                self._settings = self._api.get_settings()
            except Exception as exc:
                print(f"[HomePanel] settings load failed: {exc}")
        threading.Thread(target=_do, daemon=True).start()

    def _on_progress(self, data: dict) -> None:
        task_id = data.get("id")
        if not task_id:
            return
        if task_id in self._cards:
            try:
                self.after(0, lambda d=data, tid=task_id: self._cards[tid].update_view(d))
            except Exception:
                pass
        else:
            self._load_data()

    def _render(self, items: list[dict]) -> None:
        received_ids: set[str] = set()
        for item in items:
            tid = item.get("id")
            if not tid:
                continue
            received_ids.add(tid)
            existing = self._cards.get(tid)
            if existing is not None:
                try:
                    existing.update_view(item)
                except Exception:
                    pass
            else:
                try:
                    new_card = DownloadCard(self._list_frame, self._api, item, on_change=self._load_data)
                    self._cards[tid] = new_card
                except Exception as exc:
                    print(f"[HomePanel] failed to create card: {exc}")

        # discard orphans
        stale = [tid for tid in list(self._cards.keys()) if tid not in received_ids]
        for tid in stale:
            card = self._cards.pop(tid, None)
            if card is not None:
                try:
                    card.destroy()
                except Exception:
                    pass

        self._apply_filter()

    def _apply_filter(self) -> None:
        visible = 0
        row = 1
        for tid, card in list(self._cards.items()):
            status = (getattr(card, "_status", "") or "").lower()
            name   = (getattr(card, "_filename", "") or "").lower()
            show = (
                (self._filter == "all" or self._filter == status)
                and (self._search in name)
            )
            if show:
                try:
                    card.grid(row=row, column=0, sticky="ew", pady=6, padx=0)
                    visible += 1
                    row += 1
                except Exception:
                    pass
            else:
                try:
                    card.grid_forget()
                except Exception:
                    pass

        if visible == 0:
            try:
                self._empty_label.grid(row=0, column=0, pady=80, sticky="nsew")
            except Exception:
                pass
        else:
            try:
                self._empty_label.grid_forget()
            except Exception:
                pass

    # ------------------------------------------------------------------ ui queue

    def _schedule_ui(self, callback: Callable) -> None:
        self._ui_queue.put(callback)

    def _process_ui_queue(self) -> None:
        try:
            while True:
                cb = self._ui_queue.get_nowait()
                try:
                    cb()
                except Exception as exc:
                    print(f"[HomePanel] UI callback error: {exc}")
        except queue.Empty:
            pass
        try:
            self.after(80, self._process_ui_queue)
        except Exception:
            pass


__all__: list[str] = ["HomePanel"]
