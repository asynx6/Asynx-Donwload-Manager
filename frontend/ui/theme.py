"""AsynxDL — Brutalist monochromatic theme.

Palet flat-only greys + putih (light & dark). Tidak boleh ada warna ungu, biru,
hijau — semuanya bernuansa grey/white kaku. Semua corner_radius dipaksa 0.
"""

from typing import Iterable


# --------------------------------------------------------------------------- #
# Palet tokens
# --------------------------------------------------------------------------- #
PALETTE = {
    "light": {
        "BG":       "#E0E0E0",   # kanvas utama
        "BG2":      "#F5F5F5",   # panel content (home / setting)
        "BG3":      "#FFFFFF",   # kartu download / input field
        "FG":       "#000000",   # teks primer
        "FG2":      "#404040",   # teks sekunder / disabled
        "BORDER":   "#C0C0C0",   # garis batas
        "BORDER2":  "#A0A0A0",   # garis batas dip
        "SEL_BG":   "#808080",   # tab aktif / button hover
        "SEL_FG":   "#FFFFFF",   # tab aktif / button hover text
        "SEL_DEEP": "#5A5A5A",   # button pressed
        "ACCENT":   "#404040",   # tombol-tombol primer (grey, bukan warna)
        "ACCENT_H": "#202020",   # hover dari accent
        "PROGRESS": "#606060",   # progressbar fill
        "ERROR":    "#404040",   # error tidak boleh merah; abu pekat
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


def get(mode: str = "light") -> dict:
    """Kembalikan palet untuk mode tertentu; fallback ke light."""
    key = (mode or "light").strip().lower()
    if key not in PALETTE:
        key = "light"
    return PALETTE[key]


def tokens(mode: str = "light") -> dict:
    """Kembalikan palet + versi tuple CTk sebagai dict siap-pakai."""
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
    "PALETTE", "get", "tokens", "font",
    "CORNER_NONE", "NAVBAR_HEIGHT", "TAB_HEIGHT", "BUTTON_HEIGHT",
    "INPUT_HEIGHT", "LIST_ROW_HEIGHT", "apply_window_geometry", "FONT_FAMILY",
)
