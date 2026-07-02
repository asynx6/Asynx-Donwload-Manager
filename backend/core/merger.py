"""
AsynxDL — File Merger Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Gabungkan file .part hasil download multi-thread menjadi file output final.
Dilengkapi verifikasi ukuran akhir.

Fungsi:
    - merge_parts(part_files, output_path, expected_size)
"""

import os


# Ukuran buffer untuk operasi baca/tulis saat merge (1 MB)
_MERGE_BUFFER = 1024 * 1024  # 1 MB — dioptimalkan untuk SSD dan RAM 4GB


def merge_parts(part_files: list[str], output_path: str,
                expected_size: int) -> bool:
    """Gabungkan semua file .part menjadi satu file output final.

    Proses:
        1. Buka file output dalam mode write binary.
        2. Loop setiap .part, baca dalam chunk 1MB, tulis ke output.
        3. Setelah semua tertulis, verifikasi ukuran final.
        4. Jika ukuran cocok, hapus semua file .part.
        5. Jika ukuran tidak cocok, file output tetap ada (untuk diagnosis)
           tapi .part tidak dihapus.

    Args:
        part_files: List path ke file .part, dalam urutan index.
        output_path: Path file output final.
        expected_size: Ukuran total yang diharapkan (byte).

    Returns:
        True jika merge berhasil dan verifikasi lolos, False jika ukuran
        tidak cocok atau error I/O.
    """
    if not part_files:
        return False

    # Normalisasi dan keamanan path
    output_path = os.path.abspath(os.path.expandvars(os.path.expanduser(output_path)))
    out_dir = os.path.dirname(output_path)
    if not out_dir:
        return False
    os.makedirs(out_dir, exist_ok=True)

    # Pastikan semua part file berada dalam folder yang sama (atau subfolder)
    safe_base = os.path.abspath(out_dir)
    for part_file in part_files:
        part_abs = os.path.abspath(os.path.expandvars(os.path.expanduser(part_file)))
        if not part_abs.startswith(safe_base + os.sep) and part_abs != safe_base:
            print(f"[ERROR] Merger: part file outside output directory: {part_file}")
            return False

    try:
        total_written = 0
        with open(output_path, "wb") as out:
            for part_file in part_files:
                part_abs = os.path.abspath(os.path.expandvars(os.path.expanduser(part_file)))
                try:
                    with open(part_abs, "rb") as src:
                        while True:
                            chunk = src.read(_MERGE_BUFFER)
                            if not chunk:
                                break
                            out.write(chunk)
                            total_written += len(chunk)
                except FileNotFoundError:
                    raise IOError(
                        f"File part tidak ditemukan: {part_file}"
                    ) from None

        # Verifikasi ukuran akhir
        if expected_size > 0 and total_written != expected_size:
            # Ukuran tidak cocok — jangan hapus .part
            print(
                f"[WARN] Merger: ukuran final {total_written} != "
                f"expected {expected_size}. File .part tidak dihapus."
            )
            return False

        # Hapus semua file .part setelah berhasil
        for part_file in part_files:
            try:
                os.remove(part_file)
            except OSError:
                pass  # best-effort — file mungkin sudah dihapus

        return True

    except OSError as exc:
        print(f"[ERROR] Merger: gagal menulis file output: {exc}")
        return False
