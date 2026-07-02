import threading
import customtkinter as ctk

from frontend.ui.api_client import APIClient
from frontend.ui.components.download_card import DownloadCard
from frontend.ui.i18n import t
from frontend.ui.windows.add_download_window import AddDownloadWindow
from frontend.ui.windows.settings_window import SettingsWindow


class MainWindow(ctk.CTkFrame):
    """Window utama aplikasi AsynxDL."""

    def __init__(self, master, api: APIClient, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._api = api
        self._cards: dict[str, DownloadCard] = {}
        self._filter = "all"
        self._search = ""
        self._settings = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar
        self._toolbar = ctk.CTkFrame(self, height=50, fg_color=("#FFFFFF", "#2A2A2A"), corner_radius=12)
        self._toolbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        self._toolbar.grid_columnconfigure(0, weight=1)
        self._toolbar.grid_columnconfigure(1, weight=0)
        self._toolbar.grid_columnconfigure(2, weight=0)
        self._toolbar.grid_propagate(False)

        self._title_label = ctk.CTkLabel(
            self._toolbar, text=f"⬇  {t('app.title')} {t('app.version')}",
            font=("Inter", 16, "bold")
        )
        self._title_label.grid(row=0, column=0, sticky="w", padx=12, pady=10)

        self._entry_search = ctk.CTkEntry(
            self._toolbar, placeholder_text=t("toolbar.search_placeholder"), width=200
        )
        self._entry_search.grid(row=0, column=1, padx=6, pady=10)
        self._entry_search.bind("<KeyRelease>", lambda e: self._on_search())

        self._btn_add = ctk.CTkButton(self._toolbar, text="+ " + t("btn.add"), width=90, command=self._show_add)
        self._btn_add.grid(row=0, column=2, padx=6, pady=10)

        self._btn_settings = ctk.CTkButton(self._toolbar, text="⚙ " + t("btn.settings"), width=100, command=self._show_settings)
        self._btn_settings.grid(row=0, column=3, padx=(6, 12), pady=10)

        # Filter tabs
        self._tabs = ctk.CTkFrame(self, fg_color="transparent")
        self._tabs.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        self._tab_buttons = {}
        for i, key in enumerate(["all", "downloading", "paused", "completed"]):
            btn = ctk.CTkButton(
                self._tabs, text=t(f"filter.{key}"), width=90, height=28,
                command=lambda k=key: self._set_filter(k)
            )
            btn.grid(row=0, column=i, padx=(0, 8))
            self._tab_buttons[key] = btn
        self._set_filter("all")

        # Scrollable list
        self._list_frame = ctk.CTkScrollableFrame(self, fg_color=("#F5F5F5", "#1C1C1C"), corner_radius=12)
        self._list_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._list_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Empty label
        self._empty_label = ctk.CTkLabel(
            self._list_frame, text="No downloads", font=("Inter", 14), text_color=("#6B6B6B", "#9E9E9E")
        )
        self._empty_label.grid(row=0, column=0, pady=40)

        # WebSocket progress callback
        self._api.set_progress_callback(self._on_progress)
        self._api.start_ws()

        # Load initial data
        self._load_data()
        self._load_settings()

        # Auto refresh fallback (jika WS gagal)
        self._poll()

    def _load_data(self):
        def do_load():
            try:
                data = self._api.list_downloads()
                self.after(0, lambda: self._render(data))
            except Exception as exc:
                print(f"[MainWindow] load failed: {exc}")
        threading.Thread(target=do_load, daemon=True).start()

    def _poll(self):
        self._load_data()
        self.after(2000, self._poll)

    def _on_progress(self, data: dict):
        task_id = data.get("id")
        if not task_id:
            return
        if task_id in self._cards:
            self.after(0, lambda d=data: self._cards[d["id"]].update_view(d))
        else:
            self._load_data()

    def _on_search(self):
        self._search = self._entry_search.get().strip().lower()
        self._apply_filter()

    def _set_filter(self, key: str):
        self._filter = key
        for k, btn in self._tab_buttons.items():
            if k == key:
                btn.configure(fg_color=("#5B6BF8", "#7B8BFF"))
            else:
                btn.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        self._apply_filter()

    def _render(self, items: list[dict]):
        # Update existing cards or create new ones
        for item in items:
            task_id = item.get("id")
            if not task_id:
                continue
            if task_id in self._cards:
                self._cards[task_id].update_view(item)
            else:
                card = DownloadCard(self._list_frame, self._api, item, on_change=self._load_data)
                self._cards[task_id] = card
        self._apply_filter()

    def _apply_filter(self):
        visible = 0
        row = 1
        for task_id, card in self._cards.items():
            status = card._status.lower()
            name = card._filename.lower()
            show = (self._filter == "all" or self._filter == status) and (self._search in name)
            if show:
                card.grid(row=row, column=0, sticky="ew", padx=8, pady=6)
                row += 1
                visible += 1
            else:
                card.grid_forget()
        if visible == 0:
            self._empty_label.grid(row=0, column=0, pady=40)
        else:
            self._empty_label.grid_forget()
        self.update_idletasks()

    def _show_add(self):
        path = self._settings.get("default_download_path", "")
        win = AddDownloadWindow(self, self._api, on_added=self._load_data, default_path=path)
        win.grab_set()

    def _show_settings(self):
        win = SettingsWindow(self, self._api, on_save=self._load_settings)
        win.grab_set()

    def _load_settings(self):
        def do_load():
            try:
                self._settings = self._api.get_settings()
            except Exception as exc:
                print(f"[MainWindow] settings load failed: {exc}")
        threading.Thread(target=do_load, daemon=True).start()

    def refresh(self):
        self._load_data()
