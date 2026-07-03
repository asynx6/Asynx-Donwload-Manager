"""
AsynxDL — File Validator Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validasi path, nama file, dan kapasitas disk sebelum download dimulai.
Semua validasi dirancang untuk Windows tetapi kompatibel dengan POSIX via guard.

Fungsi:
    - check_disk_space(save_path, required_bytes) → bool
    - sanitize_filename(name) → str
    - resolve_duplicate_name(folder, filename) → str
    - normalize_path(path) → str
    - is_safe_path(base_dir, target_path) → bool
    - url_basename(url) → str
    - resolve_filename(user_input, url_filename, url) → str
"""

import os
import re
import shutil
from urllib.parse import urlparse, unquote

# Karakter ilegal di Windows: \ / : * ? " < > | dan kontrol karakter 0x00-0x1F
_ILLEGAL_WIN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def check_disk_space(save_path: str, required_bytes: int) -> bool:
    """Cek apakah drive target memiliki cukup ruang kosong (+5% buffer)."""
    drive = os.path.splitdrive(save_path)[0] or os.path.sep
    try:
        usage = shutil.disk_usage(drive)
        free = usage.free
    except OSError:
        return False
    return free >= int(required_bytes * 1.05)


def sanitize_filename(name: str) -> str:
    """Bersihkan nama file dari karakter ilegal Windows.

    Aturan:
        - Karakter ilegal diganti '_'
        - Leading/trailing dots dan spasi di-strip
        - Nama file tidak boleh kosong (fallback "unnamed_file")
        - Panjang maksimum 200 karakter
    """
    if not name or not name.strip():
        return "unnamed_file"
    cleaned = re.sub(_ILLEGAL_WIN, '_', name)
    cleaned = cleaned.strip('. ')
    if not cleaned:
        return "unnamed_file"
    return cleaned[:200]


def resolve_duplicate_name(folder: str, filename: str) -> str:
    """Jika file sudah ada di folder, tambahkan suffix counter."""
    base, ext = os.path.splitext(filename)
    target = os.path.join(folder, filename)
    if not os.path.exists(target):
        return filename
    counter = 1
    while True:
        candidate = f"{base} ({counter}){ext}"
        if not os.path.exists(os.path.join(folder, candidate)):
            return candidate
        counter += 1


def normalize_path(path: str) -> str:
    """Normalisasi path user menjadi path absolut real.

    - Expands environment variables (%USERPROFILE% etc)
    - Expands user home (~)
    - Resolves relative paths to absolute
    - Resolves symlinks
    """
    if not path:
        return os.path.expandvars(os.path.expanduser("~"))
    expanded = os.path.expandvars(os.path.expanduser(path))
    abs_path = os.path.abspath(expanded)
    try:
        return os.path.realpath(abs_path)
    except OSError:
        return abs_path


def is_safe_path(base_dir: str, target_path: str) -> bool:
    """Verifikasi bahwa target_path berada di dalam base_dir.

    Mencegah path traversal (../../) pada file write operations.
    """
    base = os.path.abspath(normalize_path(base_dir))
    target = os.path.abspath(normalize_path(target_path))
    return os.path.commonpath([base, target]) == base


def url_basename(url: str) -> str:
    """Ekstrak nama file dari URL dengan URL-decode (fix bug 'A').

    Contoh:
        'https://x.com/path/Grand%20Theft%20Auto.rar'
            -> 'Grand Theft Auto.rar'
        'https://x.com/file/'                  -> ''
        'https://x.com/file'                   -> 'file'
    """
    if not url:
        return ""
    try:
        path = urlparse(url).path or ""
    except Exception:
        return ""
    name = os.path.basename(path.rstrip("/"))
    if not name:
        return ""
    try:
        return unquote(name)
    except Exception:
        return name


def resolve_filename(user_input: str, url_filename: str, url: str) -> str:
    """Tentukan nama file final yang akan digunakan untuk tampilan & save.

    Urutan prioritas:
        1. ``user_input`` (override eksplisit dari UI / extension)
        2. ``url_filename`` (dari header Content-Disposition server)
        3. ``url_basename(url)`` (dari URL path, URL-decoded)
        4. ``"unnamed_file"`` (fallback sanitized)

    Output sudah di-sanitize supaya aman untuk Windows.

    Catatan: ``download_card.py`` icon lama default-nya huruf ``"A"`` -
    function ini menjamin string yang dikembalikan bukan placeholder
    melainkan nama file asli dari URL / server.
    """
    candidates = [user_input or "", url_filename or "", url_basename(url) or ""]
    for cand in candidates:
        sanitized = sanitize_filename(cand)
        if sanitized and sanitized != "unnamed_file":
            return sanitized
    return "unnamed_file"
