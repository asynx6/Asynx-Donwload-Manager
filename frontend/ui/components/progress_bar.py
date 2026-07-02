import customtkinter as ctk


class ProgressBar(ctk.CTkFrame):
    """Progress bar dengan label persentase overlay."""

    def __init__(self, master, height=18, *args, **kwargs):
        super().__init__(master, height=height, *args, **kwargs)
        self._progress = ctk.CTkProgressBar(self, height=height)
        self._progress.set(0.0)
        self._progress.pack(fill="both", expand=True)
        self._label = ctk.CTkLabel(
            self, text="0%", font=("Inter", 11, "bold"), text_color="white"
        )
        self._label.place(relx=0.5, rely=0.5, anchor="center")

    def set(self, value: float, text: str = ""):
        """value: 0-100."""
        self._progress.set(min(100.0, max(0.0, value)) / 100.0)
        self._label.configure(text=text or f"{value:.1f}%")

    def set_color(self, color: str):
        self._progress.configure(progress_color=color)
