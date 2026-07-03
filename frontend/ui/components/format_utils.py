
def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_speed(kbps: float) -> str:
    """Format speed in KB/s, MB/s, or B/s for very slow connections."""
    if kbps <= 0:
        return "0 B/s"
    if kbps >= 1024:
        return f"{kbps / 1024:.2f} MB/s"
    if kbps >= 1:
        return f"{kbps:.1f} KB/s"
    # Below 1 KB/s, show bytes per second so 0.4 KB/s becomes 410 B/s
    return f"{int(kbps * 1024)} B/s"


def format_time(seconds: int) -> str:
    if seconds <= 0:
        return "--:--"
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"
