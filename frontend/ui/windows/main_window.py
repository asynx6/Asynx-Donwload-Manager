import os
import queue
import threading
import datetime
import customtkinter as ctk
from PIL import Image

from frontend.ui.api_client import APIClient
from frontend.ui.components.download_card import DownloadCard
from frontend.ui.i18n import t
from frontend.ui.windows.add_download_window import AddDownloadWindow
from frontend.ui.windows.settings_window import SettingsWindow


def _load_logo_image(size=40):
    """Load the user-provided Logo.png (or generated logo.png) as a CTkImage."""
    try:
        for logo_name in ("logo.png", "tray.png"):
            logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icons", logo_name)
            if os.path.exists(logo_path):
                img = Image.open(logo_path)
                return ctk.CTkImage(img, size=(size, size))
    except Exception:
        pass
    return None


class MainWindow(ctk.CTkFrame):
    """Window utama aplikasi AsynxDL dengan layout dashboard modern."""

    # Design tokens
    BG = ("#F4F5F7", "#0F0F13")
    SIDEBAR_BG = ("#FFFFFF", "#141419")
    CARD_BG = ("#FFFFFF", "#18181E")
    TEXT_PRIMARY = ("#111827", "#F9FAFB")
    TEXT_SECONDARY = ("#6B7280", "#9CA3AF")
    ACCENT = "#6366F1"
    ACCENT_HOVER = "#4F46E5"

    def __init__(self, master, api: APIClient, **kwargs):
        super().__init__(master, fg_color=self.BG, **kwargs)
        self._api = api
        self._cards: dict[str, DownloadCard] = {}
        self._filter = "all"
        self._search = ""
        self._settings = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = self._build_sidebar()
        self._sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 0), pady=0)

        # Main content
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(1, weight=1)

        # Toolbar
        self._toolbar = self._build_toolbar()
        self._toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        # Scrollable list
        self._list_frame = ctk.CTkScrollableFrame(
            self._content, fg_color="transparent", corner_radius=0
        )
        self._list_frame.grid(row=1, column=0, sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

        self._empty_label = ctk.CTkLabel(
            self._list_frame,
            text=t("empty.no_downloads"),
            font=("Arial", 14),
            text_color=self.TEXT_SECONDARY,
        )
        self._empty_label.grid(row=0, column=0, pady=60)

        self._set_filter("all")

        # WebSocket progress callback
        self._api.set_progress_callback(lambda data: self._schedule_ui(lambda d=data: self._on_progress(d)))
        self._api.start_ws()

        # Thread-safe UI update queue
        self._ui_queue: queue.Queue = queue.Queue()
        self._process_ui_queue()

        self.after(100, self._load_data)
        self.after(200, self._load_settings)
        self._poll()
        self._start_state_heartbeat()

    def _build_sidebar(self) -> ctk.CTkFrame:
        sidebar = ctk.CTkFrame(self, width=220, fg_color=self.SIDEBAR_BG, corner_radius=0)
        sidebar.grid_rowconfigure(2, weight=1)
        sidebar.grid_propagate(False)

        # Brand
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 16))
        brand.grid_columnconfigure(0, weight=0)
        brand.grid_columnconfigure(1, weight=1)
        logo_img = _load_logo_image(size=40)
        if logo_img:
            logo = ctk.CTkLabel(brand, image=logo_img, text="")
            logo.image = logo_img  # keep reference
            logo.grid(row=0, column=0, sticky="w")
        else:
            logo = ctk.CTkLabel(
                brand, text="📥", font=("Arial", 24, "bold"), text_color=self.ACCENT
            )
            logo.grid(row=0, column=0, sticky="w")
        title = ctk.CTkLabel(
            brand, text=t("app.title"), font=("Arial", 18, "bold"),
            text_color=self.TEXT_PRIMARY
        )
        title.grid(row=0, column=1, sticky="w", padx=(12, 0))

        version = ctk.CTkLabel(
            sidebar, text=t("app.version"), font=("Arial", 11),
            text_color=self.TEXT_SECONDARY
        )
        version.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        # Filter tabs
        tabs = ctk.CTkFrame(sidebar, fg_color="transparent")
        tabs.grid(row=2, column=0, sticky="nsew", padx=14, pady=8)
        tabs.grid_columnconfigure(0, weight=1)

        self._tab_buttons = {}
        tab_keys = [
            ("all", "All"),
            ("downloading", "Active"),
            ("paused", "Paused"),
            ("completed", "Done"),
        ]
        for i, (key, icon) in enumerate(tab_keys):
            btn = ctk.CTkButton(
                tabs,
                text=f"{icon}  {t(f'filter.{key}')}",
                anchor="w",
                height=38,
                corner_radius=10,
                font=("Arial", 13),
                fg_color="transparent",
                text_color=self.TEXT_SECONDARY,
                hover_color=("#E5E7EB", "#27272A"),
                command=lambda k=key: self._set_filter(k),
            )
            btn.grid(row=i, column=0, sticky="ew", pady=4)
            self._tab_buttons[key] = btn

        # Bottom actions
        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=14, pady=(8, 20))
        bottom.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            bottom,
            text=f"{t('btn.settings')}",
            anchor="w",
            height=38,
            corner_radius=10,
            font=("Arial", 13),
            fg_color="transparent",
            text_color=self.TEXT_SECONDARY,
            hover_color=("#E5E7EB", "#27272A"),
            command=self._show_settings,
        ).grid(row=0, column=0, sticky="ew", pady=4)

        return sidebar

    def _build_toolbar(self) -> ctk.CTkFrame:
        toolbar = ctk.CTkFrame(self._content, fg_color="transparent")
        toolbar.grid_columnconfigure(0, weight=1)

        # Title + subtitle
        header = ctk.CTkFrame(toolbar, fg_color="transparent")
        header.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=t("toolbar.my_downloads"),
            font=("Arial", 22, "bold"),
            text_color=self.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=t("toolbar.manage_downloads"),
            font=("Arial", 12),
            text_color=self.TEXT_SECONDARY,
        ).grid(row=1, column=0, sticky="w")

        # Right side controls
        right = ctk.CTkFrame(toolbar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        self._entry_search = ctk.CTkEntry(
            right,
            placeholder_text=t("toolbar.search_placeholder"),
            width=220,
            height=38,
            corner_radius=10,
            font=("Arial", 12),
            border_width=1,
        )
        self._entry_search.grid(row=0, column=0, padx=(0, 10))
        self._entry_search.bind("<KeyRelease>", lambda e: self._on_search())

        self._btn_add = ctk.CTkButton(
            right,
            text=f"+  {t('btn.add')}",
            width=130,
            height=38,
            corner_radius=10,
            font=("Arial", 13, "bold"),
            fg_color=self.ACCENT,
            hover_color=self.ACCENT_HOVER,
            command=self._show_add,
        )
        self._btn_add.grid(row=0, column=1)

        return toolbar

    def _set_filter(self, key: str):
        self._filter = key
        for k, btn in self._tab_buttons.items():
            if k == key:
                btn.configure(
                    fg_color=self.ACCENT,
                    text_color="white",
                    hover_color=self.ACCENT_HOVER,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=self.TEXT_SECONDARY,
                    hover_color=("#E5E7EB", "#27272A"),
                )
        self._apply_filter()

    def _on_search(self):
        self._search = self._entry_search.get().strip().lower()
        self._apply_filter()

    def _load_data(self):
        def do_load():
            try:
                data = self._api.list_downloads()
                self._schedule_ui(lambda: self._render(data))
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

    def _render(self, items: list[dict]):
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
                card.grid(row=row, column=0, sticky="ew", pady=8)
                row += 1
                visible += 1
            else:
                card.grid_forget()
        if visible == 0:
            self._empty_label.grid(row=0, column=0, pady=60)
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

    def _schedule_ui(self, callback):
        self._ui_queue.put(callback)

    def _process_ui_queue(self):
        try:
            while True:
                callback = self._ui_queue.get_nowait()
                try:
                    callback()
                except Exception as exc:
                    print(f"[MainWindow] UI callback error: {exc}")
        except queue.Empty:
            pass
        self.after(100, self._process_ui_queue)

    def _start_state_heartbeat(self):
        def _beat():
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
            except Exception as exc:
                print(f"[MainWindow] state heartbeat failed: {exc}")
            self.after(1000, _beat)
        self.after(1000, _beat)

    def refresh(self):
        self._load_data()
