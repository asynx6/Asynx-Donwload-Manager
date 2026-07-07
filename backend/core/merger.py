"""
AsynxDL — File Merger Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Gabungkan file .part hasil download multi-thread menjadi file output final.
Dilengkapi verifikasi ukuran akhir dan checksum (SHA-256 / MD5 / ETag).

Fungsi:
    - merge_parts(part_files, output_path, expected_size,
                  expected_sha256=None, expected_md5=None, etag=None)
"""

import hashlib
import os


# Ukuran buffer untuk operasi baca/tulis saat merge (1 MB)
_MERGE_BUFFER = 1024 * 1024  # 1 MB — dioptimalkan untuk SSD dan RAM 4GB


def _hash_file(path: str, algo: str) -> str:
    """Hitung hash heksadesimal untuk file di ``path`` dengan algoritma ``algo``."""
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_MERGE_BUFFER)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _normalize_etag(etag: str) -> str:
    """Strip quotes dan weakness prefix dari ETag."""
    if not etag:
        return ""
    etag = etag.strip()
    if etag.startswith("W/"):
        etag = etag[2:]
    return etag.strip('"')


def merge_parts(part_files: list[str], output_path: str,
                expected_size: int,
                expected_sha256: str | None = None,
                expected_md5: str | None = None,
                etag: str | None = None) -> bool:
    """Gabungkan semua file .part menjadi satu file output final.

    Proses:
        1. Buka file output dalam mode write binary.
        2. Loop setiap .part, baca dalam chunk 1MB, tulis ke output.
        3. Setelah semua tertulis, verifikasi ukuran final dan checksum.
        4. Jika verifikasi lolos, hapus semua file .part.
        5. Jika verifikasi gagal, file output tetap ada (untuk diagnosis)
           tapi .part tidak dihapus.

    Args:
        part_files: List path ke file .part, dalam urutan index.
        output_path: Path file output final.
        expected_size: Ukuran total yang diharapkan (byte).
        expected_sha256: Optional SHA-256 yang diharapkan (hex).
        expected_md5: Optional MD5 yang diharapkan (hex).
        etag: Optional ETag header untuk verifikasi (MD5 dari konten).

    Returns:
        True jika merge berhasil dan verifikasi lolos, False jika ukuran
        tidak cocok, checksum mismatch, atau error I/O.
    """
    if not part_files:
        return False

    # Normalisasi dan keamanan path
    output_path = os.path.abspath(os.path.expandvars(os.path.expanduser(output_path)))
    out_dir = os.path.dirname(output_path)
    if not out_dir:
        return False
    os.makedirs(out_dir, exist_ok=True)

    # Pastikan semua part file ada
    for part_file in part_files:
        part_abs = os.path.abspath(os.path.expandvars(os.path.expanduser(part_file)))
        if not os.path.exists(part_abs):
            print(f"[ERROR] Merger: part file missing: {part_file}")
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
            print(
                f"[WARN] Merger: ukuran final {total_written} != "
                f"expected {expected_size}. File .part tidak dihapus."
            )
            return False

        # Verifikasi checksum jika server menyediakan
        if expected_sha256:
            actual = _hash_file(output_path, "sha256")
            if actual.lower() != expected_sha256.lower().strip():
                print(
                    f"[WARN] Merger: SHA-256 mismatch. expected={expected_sha256}, "
                    f"actual={actual}. File .part tidak dihapus."
                )
                return False

        if expected_md5:
            actual = _hash_file(output_path, "md5")
            if actual.lower() != expected_md5.lower().strip():
                print(
                    f"[WARN] Merger: MD5 mismatch. expected={expected_md5}, "
                    f"actual={actual}. File .part tidak dihapus."
                )
                return False

        if etag:
            norm = _normalize_etag(etag)
            # ETag sering berupa MD5 konten; coba bandingkan.
            if len(norm) == 32:
                actual = _hash_file(output_path, "md5")
                if actual.lower() != norm.lower():
                    print(
                        f"[WARN] Merger: ETag mismatch. expected={norm}, "
                        f"actual={actual}. File .part tidak dihapus."
                    )
                    return False

        # Hapus semua file .part setelah berhasil
        for part_file in part_files:
            try:
                os.remove(part_file)
            except OSError as exc:
                # FIX #27: log instead of silent pass
                print(f"[WARN] Merger: failed to remove part file {part_file}: {exc}")

        return True

    except OSError as exc:
        print(f"[ERROR] Merger: gagal menulis file output: {exc}")
        return False
