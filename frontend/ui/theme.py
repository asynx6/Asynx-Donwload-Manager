"""AsynxDL — Brutalist monochromatic theme.

Palet flat-only greys + putih (light & dark). Tidak boleh ada warna ungu, biru,
hijau — semuanya bernuansa grey/white kaku. Semua corner_radius dipaksa 0.

CustomTkinter di Windows sering gagal menerapkan light/dark mode melalui
tuple colors. Maka disediakan ``tokens_for(mode)`` yang mengembalikan warna
literal (bukan tuple) untuk mode tertentu, dan ``repaint(root, mode)`` yang
secara rekursif mengubah warna setiap widget yang sudah dibuat.
"""

from typing import Iterable


# --------------------------------------------------------------------------- #
# Palet tokens
# --------------------------------------------------------------------------- #
PALETTE = {
    "light": {
        "BG":       "#FFFFFF",   # kanvas utama — putih bersih
        "BG2":      "#FFFFFF",   # panel content — putih bersih
        "BG3":      "#FFFFFF",   # kartu download / input field — putih bersih
        "FG":       "#1A1A1A",   # teks primer — near-black
        "FG2":      "#666666",   # teks sekunder / disabled — grey
        "BORDER":   "#CCCCCC",   # garis batas — light grey
        "BORDER2":  "#999999",   # garis batas dip — medium grey
        "SEL_BG":   "#E0E0E0",   # tab aktif / button hover — light grey
        "SEL_FG":   "#1A1A1A",   # tab aktif text — dark
        "SEL_DEEP": "#C0C0C0",   # button pressed — grey
        "ACCENT":   "#333333",   # tombol-tombol primer — dark grey
        "ACCENT_H": "#1A1A1A",   # hover dari accent — near-black
        "PROGRESS": "#666666",   # progressbar fill — grey
        "ERROR":    "#333333",   # error abu pekat
    },
    "dark": {
        "BG":       "#1F1F1F",
        "BG2":      "#2A2A2A",
        "BG3":      "#363636",
        "FG":       "#FFFFFF",
        "FG2":      "#B0B0B0",
        "BORDER":   "#404040",
        "BORDER2":  "#5A5A5A",
        "SEL_BG":   "#606060",
        "SEL_FG":   "#FFFFFF",
        "SEL_DEEP": "#3A3A3A",
        "ACCENT":   "#A0A0A0",
        "ACCENT_H": "#C0C0C0",
        "PROGRESS": "#A0A0A0",
        "ERROR":    "#B0B0B0",
    },
}


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #

def get(mode: str = "light") -> dict:
    """Kembalikan palet untuk mode tertentu; fallback ke light."""
    key = (mode or "light").strip().lower()
    if key not in PALETTE:
        key = "light"
    return PALETTE[key]


def tokens(mode: str = "light") -> dict:
    """Kembalikan palet sebagai tuple (light, dark) untuk CTk compatibility.

    Karena CustomTkinter di Windows terkadang tidak menerapkan switch
    light/dark secara otomatis, sebagian besar UI mengambil warna literal
    dari ``tokens_for(mode)``.
    """
    p = get(mode)
    d = PALETTE["dark"]
    return {
        "BG":       (p["BG"], d["BG"]),
        "BG2":      (p["BG2"], d["BG2"]),
        "BG3":      (p["BG3"], d["BG3"]),
        "FG":       (p["FG"], d["FG"]),
        "FG2":      (p["FG2"], d["FG2"]),
        "BORDER":   (p["BORDER"], d["BORDER"]),
        "BORDER2":  (p["BORDER2"], d["BORDER2"]),
        "SEL_BG":   (p["SEL_BG"], d["SEL_BG"]),
        "SEL_FG":   (p["SEL_FG"], d["SEL_FG"]),
        "SEL_DEEP": (p["SEL_DEEP"], d["SEL_DEEP"]),
        "ACCENT":   (p["ACCENT"], d["ACCENT"]),
        "ACCENT_H": (p["ACCENT_H"], d["ACCENT_H"]),
        "PROGRESS": (p["PROGRESS"], d["PROGRESS"]),
        "ERROR":    (p["ERROR"], d["ERROR"]),
    }


def tokens_for(mode: str = "light") -> dict:
    """Kembalikan palet literal (single color) untuk ``mode``.

    Ini digunakan untuk memaksa warna widget yang sudah dibuat agar sesuai
    mode aktif, karena CTk tuple colors tidak selalu reliable di Windows.
    """
    return get(mode)


def font(size: int, bold: bool = False) -> tuple:
    """Kembali tuple (Arial, size[, bold])."""
    if bold:
        return ("Arial", size, "bold")
    return ("Arial", size)


FONT_FAMILY = "Arial"

CORNER_NONE   = 0
NAVBAR_HEIGHT = 36
TAB_HEIGHT    = 30
BUTTON_HEIGHT = 32
INPUT_HEIGHT  = 30
LIST_ROW_HEIGHT = 92


# --------------------------------------------------------------------------- #
# Runtime repaint helpers
# --------------------------------------------------------------------------- #

_CURRENT_MODE = "light"


def set_mode(mode: str) -> None:
    """Set mode global yang sedang aktif."""
    global _CURRENT_MODE
    _CURRENT_MODE = (mode or "light").strip().lower()


def current_mode() -> str:
    return _CURRENT_MODE


def repaint(root, mode: str | None = None) -> int:
    """Rekursif reconfigure fg_color, text_color, border_color, dll.

    Returns jumlah widget yang di-repaint. Tidak menjamin 100% coverage
    karena CTk internal state tidak sepenuhnya bisa di-mutate ulang,
    tapi cukup untuk memperbaiki masalah light mode yang malah tampil dark.
    """
    if mode is None:
        mode = current_mode()
    tk = tokens_for(mode)
    return _apply_tokens_recursive(root, tk)


def _apply_tokens_recursive(widget, tk: dict) -> int:
    """Reconfigure warna semua widget Brutalist di-subtree."""
    count = 0
    try:
        cfg = widget.configure
    except Exception:
        cfg = None
    if cfg is None:
        pass
    else:
        try:
            widget.configure(fg_color=tk["BG3"])
        except Exception:
            try:
                widget.configure(fg_color=tk["BG2"])
            except Exception:
                pass
        try:
            widget.configure(text_color=tk["FG"])
        except Exception:
            pass
        try:
            widget.configure(border_color=tk["BORDER"])
        except Exception:
            pass
        try:
            widget.configure(placeholder_text_color=tk["FG2"])
        except Exception:
            pass
        try:
            widget.configure(button_color=tk["ACCENT"])
        except Exception:
            pass
        try:
            widget.configure(button_hover_color=tk["ACCENT_H"])
        except Exception:
            pass
        try:
            widget.configure(progress_color=tk["PROGRESS"])
        except Exception:
            pass
        count += 1
    try:
        for child in widget.winfo_children():
            count += _apply_tokens_recursive(child, tk)
    except Exception:
        pass
    return count


def apply_window_geometry(root, width: int = 1080, height: int = 720) -> None:
    """Letakkan root window center-screen; ukuran standarm Brutalist."""
    try:
        sw = root.winfo_screenwidth() or 1920
        sh = root.winfo_screenheight() or 1080
    except Exception:
        sw, sh = 1920, 1080
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(880, 600)


__all__: Iterable[str] = (
    "PALETTE", "get", "tokens", "tokens_for", "font", "set_mode", "current_mode", "repaint",
    "CORNER_NONE", "NAVBAR_HEIGHT", "TAB_HEIGHT", "BUTTON_HEIGHT",
    "INPUT_HEIGHT", "LIST_ROW_HEIGHT", "apply_window_geometry", "FONT_FAMILY",
)
