"""AsynxDL — Resume Integrity Validator.

Saat resume, validasi bahwa metadata dan file .part masih konsisten:
    - Setiap .part file ada.
    - Ukuran .part cocok dengan `bytes_done` yang tersimpan.
    - Jika mismatch, reset chunk tersebut (download ulang).
    - Hitung state hash untuk deteksi tamper eksternal pada metadata.
"""

import hashlib
import json
import os


class ResumeIntegrityValidator:
    """Validasi konsistensi metadata dan file .part sebelum resume."""

    def __init__(self, task_id: str, parts_dir: str, metadata: dict):
        self.task_id = task_id
        self.parts_dir = parts_dir
        self.metadata = metadata

    def _state_hash(self) -> str:
        """Hitung hash dari data resume (chunks + total_size + downloaded_size)."""
        payload = {
            "chunks": self.metadata.get("chunks", []),
            "total_size": self.metadata.get("total_size", 0),
            "downloaded_size": self.metadata.get("downloaded_size", 0),
            "url": self.metadata.get("url", ""),
            "etag": self.metadata.get("etag", ""),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def validate(self) -> dict:
        """Return dict {'valid': bool, 'fixed_chunks': int, 'state_hash': str}."""
        chunks = list(self.metadata.get("chunks", []))
        fixed = 0
        valid = True
        for chunk in chunks:
            idx = chunk.get("index", 0)
            part_path = os.path.join(self.parts_dir, f"{self.task_id}.part{idx}")
            if os.path.exists(part_path):
                actual_size = os.path.getsize(part_path)
                expected = chunk.get("bytes_done", 0)
                if actual_size < expected:
                    # File part lebih kecil dari yang tercatat → corrupt / truncated
                    chunk["bytes_done"] = actual_size
                    fixed += 1
                elif actual_size > expected:
                    # File part lebih besar (misal server mengembalikan extra) → reset
                    chunk["bytes_done"] = 0
                    try:
                        os.remove(part_path)
                    except OSError:
                        pass
                    fixed += 1
                    valid = False
            else:
                # Part file hilang → reset chunk
                chunk["bytes_done"] = 0
                fixed += 1
                valid = False

        self.metadata["chunks"] = chunks
        self.metadata["state_hash"] = self._state_hash()
        return {
            "valid": valid,
            "fixed_chunks": fixed,
            "state_hash": self.metadata["state_hash"],
            "chunks": chunks,
        }


__all__ = ("ResumeIntegrityValidator",)
