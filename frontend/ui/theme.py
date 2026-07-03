"""AsynxDL shared UI theme tokens.

Centralized colors and typography so every window/component stays consistent.
"""

# Windows modern font; CustomTkinter falls back gracefully if it is unavailable.
FONT_FAMILY = "Arial"


def font(size=13, bold=False):
    """Return a Tkinter/CustomTkinter font tuple."""
    weight = "bold" if bold else "normal"
    return (FONT_FAMILY, size, weight)


# ── Colors ─────────────────────────────────────────────────────────
# Tuples are (light_mode, dark_mode)
ACCENT = ("#6366F1", "#818CF8")
ACCENT_HOVER = ("#4F46E5", "#A5B4FC")
BG = ("#F4F5F7", "#0B0B0F")
SIDEBAR_BG = ("#FFFFFF", "#141419")
CARD_BG = ("#FFFFFF", "#18181E")
CARD_BORDER = ("#E5E7EB", "#27272A")
TEXT_PRIMARY = ("#111827", "#F9FAFB")
TEXT_SECONDARY = ("#6B7280", "#9CA3AF")
SUCCESS = ("#10B981", "#34D399")
WARNING = ("#F59E0B", "#FBBF24")
ERROR = ("#EF4444", "#F87171")

# Progress bar colors
PROGRESS_BG = ("#E5E7EB", "#27272A")
PROGRESS_FG = ("#6366F1", "#818CF8")
