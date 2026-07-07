import customtkinter as ctk

from frontend.ui import theme


class ProgressBar(ctk.CTkFrame):
    """Brutalist mono-grey progress bar."""

    def __init__(self, master, height=18, mode="light", color=None, *args, **kwargs):
        tk = theme.tokens_for(mode)
        super().__init__(
            master, height=height,
            fg_color=tk["BG"], corner_radius=theme.CORNER_NONE,
            *args, **kwargs
        )
        self._mode = mode
        self._tk = tk
        self._progress = ctk.CTkProgressBar(
            self, height=height, corner_radius=theme.CORNER_NONE,
            fg_color=tk["BG"], progress_color=color or tk["PROGRESS"],
            border_width=1, border_color=tk["BORDER"]
        )
        self._progress.set(0.0)
        self._progress.pack(fill="both", expand=True)
        self._label = ctk.CTkLabel(
            self, text="0%", font=theme.font(11, bold=True), text_color=tk["FG"]
        )
        self._label.place(relx=0.5, rely=0.5, anchor="center")

    def set(self, value: float, text: str = ""):
        """value: 0-100."""
        self._progress.set(min(100.0, max(0.0, value)) / 100.0)
        self._label.configure(text=text or f"{value:.1f}%")

    def set_color(self, color: str):
        self._progress.configure(progress_color=color)

    def recolor(self, mode: str):
        tk = theme.tokens_for(mode)
        self._tk = tk
        self.configure(fg_color=tk["BG"], border_color=tk["BORDER"])
        self._progress.configure(fg_color=tk["BG"], progress_color=tk["PROGRESS"], border_color=tk["BORDER"])
        self._label.configure(text_color=tk["FG"])
