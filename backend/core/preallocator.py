"""AsynxDL — Pre-allocation & Sequential Write Utilities.

Menyediakan pre-allocate disk untuk file final dan .part files.
Tujuannya:
    1. Mencegah fragmentasi disk.
    2. Mendeteksi dini kalau disk space tidak cukup.
    3. Mempercepat sequential write karena OS tidak perlu alokasi on-the-fly.

Windows: gunakan sparse file + seek-to-end (atau zero-fill untuk file kecil).
POSIX  : gunakan fallocate jika tersedia; fallback seek-to-end.
"""

import os
import platform


def _preallocate_posix(path: str, size: int) -> bool:
    """Best-effort POSIX fallocate."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o644)
        try:
            os.posix_fallocate(fd, 0, size)
            return True
        except (OSError, AttributeError):
            # posix_fallocate tidak tersedia atau gagal
            with os.fdopen(fd, "wb", closefd=False) as f:
                f.seek(size - 1)
                f.write(b"\0")
            return True
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
    except Exception as exc:
        print(f"[Preallocator] posix preallocate failed: {exc}")
        return False


def _preallocate_windows(path: str, size: int, zero_fill: bool = False) -> bool:
    """Best-effort Windows preallocate.

    Untuk file kecil (< 100 MB) default zero-fill supaya konten benar-benar
    dialokasikan. Untuk file besar, gunakan sparse file + SetFileValidData
    tidak tersedia tanpa priviledge, jadi fallback ke seek-to-end + sparse.
    """
    try:
        if zero_fill or size < 100 * 1024 * 1024:
            # FIX #18: chunked writes to avoid large memory allocation
            chunk = b"\0" * (1024 * 1024)  # 1 MB
            with open(path, "wb") as f:
                remaining = size
                while remaining > 0:
                    f.write(chunk[:min(1024 * 1024, remaining)])
                    remaining -= 1024 * 1024
            return True
        # Sparse / seek-to-end untuk file besar
        with open(path, "wb") as f:
            f.seek(size - 1)
            f.write(b"\0")
        return True
    except Exception as exc:
        print(f"[Preallocator] windows preallocate failed: {exc}")
        return False


def preallocate_file(path: str, size: int, zero_fill: bool = False) -> bool:
    """Pre-allocate file sebesar ``size`` bytes.

    Returns:
        True jika berhasil, False jika gagal. Caller tetap bisa lanjut
        download tanpa preallocate; ini hanya best-effort.
    """
    if size <= 0:
        return False
    try:
        dir_name = os.path.dirname(os.path.abspath(path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        system = platform.system().lower()
        if system == "windows":
            return _preallocate_windows(path, size, zero_fill=zero_fill)
        return _preallocate_posix(path, size)
    except Exception as exc:
        print(f"[Preallocator] failed: {exc}")
        return False


def preallocate_parts(parts_dir: str, task_id: str, count: int, chunk_sizes: list[int] | None = None) -> bool:
    """Pre-allocate semua .part files untuk satu task.

    Args:
        parts_dir: folder tempat .part disimpan.
        task_id: UUID task.
        count: jumlah part file.
        chunk_sizes: list ukuran per chunk (opsional). Jika None, tiap part
                     di-preallocate sebesar total_size / count.

    Returns:
        True jika semua part berhasil di-preallocate, False sebaliknya.
    """
    if count <= 0:
        return False
    success = True
    for i in range(count):
        part_path = os.path.join(parts_dir, f"{task_id}.part{i}")
        size = chunk_sizes[i] if chunk_sizes and i < len(chunk_sizes) else 0
        if size > 0:
            if not preallocate_file(part_path, size):
                success = False
    return success


def reserve_space(path: str, size: int) -> bool:
    """Cek apakah drive tempat ``path`` punya space >= size + 5% margin."""
    try:
        abs_path = os.path.abspath(path)
        drive = os.path.splitdrive(abs_path)[0] or os.path.sep
        usage = os.statvfs(drive) if hasattr(os, "statvfs") else None
        if usage:
            free = usage.f_bavail * usage.f_frsize
        else:
            import shutil
            free = shutil.disk_usage(drive).free
        return free >= int(size * 1.05)
    except Exception as exc:
        print(f"[Preallocator] reserve_space check failed: {exc}")
        return True  # best-effort: biarkan download jalan


__all__ = ("preallocate_file", "preallocate_parts", "reserve_space")
