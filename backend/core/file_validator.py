"""
AsynxDL — File Validator Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validasi path, nama file, dan kapasitas disk sebelum download dimulai.
Semua validasi dirancang untuk Windows tetapi kompatibel dengan POSIX via guard.

Fungsi:
    - check_disk_space(save_path, required_bytes) → bool
    - sanitize_filename(name) → str
    - resolve_duplicate_name(folder, filename) → str
"""

import os
import re
import shutil

# Karakter ilegal di Windows: \ / : * ? " < > | dan kontrol karakter 0x00-0x1F
_ILLEGAL_WIN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def check_disk_space(save_path: str, required_bytes: int) -> bool:
    """Cek apakah drive target memiliki cukup ruang kosong (+5% buffer).

    Args:
        save_path: Path absolut file yang akan disimpan.
        required_bytes: Ukuran file yang akan diunduh (byte).

    Returns:
        True jika cukup, False jika tidak cukup.
    """
    drive = os.path.splitdrive(save_path)[0] or os.path.sep
    try:
        usage = shutil.disk_usage(drive)
        free = usage.free
    except OSError:
        # Drive tidak bisa diakses (mis. network drive terputus)
        return False
    # Buffer 5% untuk filesystem overhead dan metadata .json/.part
    return free >= int(required_bytes * 1.05)


def sanitize_filename(name: str) -> str:
    """Bersihkan nama file dari karakter ilegal Windows.

    Aturan:
        - Karakter ilegal diganti '_'
        - Leading/trailing dots dan spasi di-strip
        - Nama file tidak boleh kosong (fallback "unnamed_file")
        - Panjang maksimum 200 karakter

    Args:
        name: Nama file mentah (dari URL atau user input).

    Returns:
        Nama file yang sudah dibersihkan.
    """
    if not name or not name.strip():
        return "unnamed_file"
    cleaned = re.sub(_ILLEGAL_WIN, '_', name)
    # Strip dots dan spasi di awal/akhir
    cleaned = cleaned.strip('. ')
    if not cleaned:
        return "unnamed_file"
    return cleaned[:200]


def resolve_duplicate_name(folder: str, filename: str) -> str:
    """Jika file sudah ada di folder, tambahkan suffix counter.

    Contoh: file.zip → file (1).zip → file (2).zip

    Args:
        folder: Path folder tujuan.
        filename: Nama file yang diinginkan.

    Returns:
        Nama file yang belum ada di folder (tanpa konflik).
    """
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
