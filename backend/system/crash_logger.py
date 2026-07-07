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
import threading


def _log_dir() -> str:
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(base, "AsynxDL", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _write_crash_report(exc_type, exc_value, exc_tb) -> str:
    log_dir = _log_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"crash-{timestamp}.log")

    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    lines = [
        "AsynxDL Crash Report",
        "=" * 40,
        f"Time (local): {datetime.datetime.now().isoformat()}",
        f"Python executable: {sys.executable}",
        f"Command line: {' '.join(sys.argv)}",
        f"Working directory: {os.getcwd()}",
        "-" * 40,
        "Traceback:",
        tb_text,
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
    """Jalankan fungsi target dengan crash logging aktif.

    Audit-fix M3: simpan sys.excepthook sementara dan kembalikan ke default
    sebelum raise, supaya exception propagation ke atas tidak memanggil
    hook lagi (yang akan menyebabkan double-log ke file crash yang sama).
    """
    install_crash_handler()
    try:
        return target(*args, **kwargs)
    except Exception:
        # Restore default hook supaya raise di bawah tidak memicu log ganda.
        prev_hook = sys.excepthook
        sys.excepthook = sys.__excepthook__
        try:
            _write_crash_report(*sys.exc_info())
        finally:
            sys.excepthook = prev_hook
        raise


class _LogStream:
    """Wrapper sederhana untuk mengalihkan stdout/stderr ke file log."""

    def __init__(self, path: str, original):
        self._path = path
        self._original = original
        self._lock = threading.Lock()
        self._file = None
        try:
            self._file = open(self._path, "a", encoding="utf-8", buffering=1)
        except Exception:
            self._file = None

    def _write_line(self, line: str):
        try:
            with self._lock:
                if self._file is None:
                    return
                self._file.write(line)
                if not line.endswith("\n"):
                    self._file.write("\n")
        except Exception:
            pass

    def write(self, data: str):
        try:
            self._original.write(data)
        except Exception:
            pass
        try:
            with self._lock:
                if self._file is not None:
                    self._file.write(data)
        except Exception:
            pass

    def flush(self):
        try:
            with self._lock:
                if self._file is not None:
                    self._file.flush()
            self._original.flush()
        except Exception:
            pass

    def close(self):
        try:
            self.flush()
        except Exception:
            pass
        try:
            with self._lock:
                if self._file is not None:
                    self._file.close()
                    self._file = None
        except Exception:
            pass

    def __getattr__(self, name):
        if self._original is None:
            if name == "isatty":
                return lambda: False
            if name in ("fileno", "seekable", "readable", "writable"):
                return lambda *args, **kwargs: False
            raise AttributeError(name)
        return getattr(self._original, name)


def redirect_streams_to_log():
    """Alihkan stdout dan stderr ke file log persisten."""
    log_dir = _log_dir()
    log_path = os.path.join(log_dir, "app.log")
    try:
        sys.stdout = _LogStream(log_path, sys.stdout)
        sys.stderr = _LogStream(log_path, sys.stderr)
    except Exception:
        pass
