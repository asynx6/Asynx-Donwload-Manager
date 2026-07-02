r"""
AsynxDL — Crash Logger
~~~~~~~~~~~~~~~~~~~~~~
Menangkap exception yang tidak tertangani dan menulisnya ke file log di
%LOCALAPPDATA%\AsynxDL\logs\crash-<timestamp>.log.

Digunakan sebagai lapisan terluar saat aplikasi dijalankan dari .exe,
sehingga user/developer bisa melihat alasan crash tanpa console window.
"""

import datetime
import os
import sys
import traceback


def _log_dir() -> str:
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(base, "AsynxDL", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _write_crash_report(exc_type, exc_value, exc_tb) -> str:
    log_dir = _log_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"crash-{timestamp}.log")

    lines = [
        "AsynxDL Crash Report",
        "=" * 40,
        f"Time (local): {datetime.datetime.now().isoformat()}",
        f"Python executable: {sys.executable}",
        f"Command line: {' '.join(sys.argv)}",
        f"Working directory: {os.getcwd()}",
        "-" * 40,
        "Traceback:",
        traceback.format_exception(exc_type, exc_value, exc_tb),
        "=" * 40,
    ]

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as write_exc:
        # Fallback: tulis ke direktori kerja saat ini
        fallback = os.path.join(os.getcwd(), f"asynxdl-crash-{timestamp}.log")
        try:
            with open(fallback, "w", encoding="utf-8") as f:
                f.write(f"Primary log failed: {write_exc}\n\n")
                f.write("\n".join(lines))
            return fallback
        except Exception:
            return ""

    return log_path


def install_crash_handler():
    """Pasang global exception hook."""
    original_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        log_path = _write_crash_report(exc_type, exc_value, exc_tb)
        if log_path:
            print(f"[CRASH] Aplikasi crash. Log disimpan di: {log_path}")
        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def run_with_crash_logging(target, *args, **kwargs):
    """Jalankan fungsi target dengan crash logging aktif."""
    install_crash_handler()
    try:
        return target(*args, **kwargs)
    except Exception:
        _write_crash_report(*sys.exc_info())
        raise
