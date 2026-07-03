"""
AsynxDL — Metadata Manager Module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CRUD untuk file metadata .json di data/queue/.
Thread-safe via threading.Lock() — beberapa chunk thread bisa update
metadata secara bersamaan.

Fungsi/Kelas:
    - MetadataManager: class utama untuk operasi metadata.
"""

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _is_safe_task_id(task_id: str) -> bool:
    """Validate task_id as a UUID or simple alphanumeric-safe identifier.

    This prevents path traversal or arbitrary file creation via malicious
    task_id values.
    """
    if not task_id or len(task_id) > 80:
        return False
    return bool(re.fullmatch(r"[a-fA-F0-9\-]{8,80}", task_id))


class MetadataManager:
    """Thread-safe manager untuk file metadata JSON per download task.

    Setiap download task memiliki satu file .json di data/queue/
    yang menyimpan state lengkapnya. Manager ini menyediakan operasi
    CRUD dengan locking untuk konsistensi multi-thread.
    """

    _lock = threading.Lock()

    def __init__(self, queue_dir: str = "data/queue"):
        """Inisialisasi MetadataManager.

        Args:
            queue_dir: Path relatif/absolut ke folder metadata (data/queue/).
        """
        self._queue_dir = Path(os.path.expandvars(os.path.expanduser(queue_dir)))
        self._completed_dir = self._queue_dir / "completed"
        os.makedirs(self._queue_dir, exist_ok=True)
        os.makedirs(self._completed_dir, exist_ok=True)

    def _metadata_path(self, task_id: str) -> Path:
        """Path file metadata untuk task_id tertentu (folder active)."""
        if not task_id or not _is_safe_task_id(task_id):
            raise ValueError("Invalid task_id")
        return self._queue_dir / f"{task_id}.json"

    def _completed_path(self, task_id: str) -> Path:
        """Path file metadata untuk task_id tertentu di folder completed/."""
        if not task_id or not _is_safe_task_id(task_id):
            raise ValueError("Invalid task_id")
        return self._completed_dir / f"{task_id}.json"

    def mark_completed(self, task_id: str, **extra) -> dict | None:
        """Pindahkan metadata ke ``data/queue/completed/`` (persist history).

        Task dihapus dari folder active agar tidak muncul lagi di ``list_all``
        aktif. Task tetap direcover saat boot lewat ``list_history``.

        Returns dict yang dipindahkan, atau None jika tidak ditemukan.
        """
        src = self._metadata_path(task_id)
        dst = self._completed_path(task_id)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            try:
                with open(src, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return None
            data["status"] = "COMPLETED"
            data["completed_at"] = now
            data["updated_at"] = now
            data.update(extra)
            try:
                # atomic move: write to dst then remove src
                tmp = dst.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, dst)
                try:
                    os.remove(src)
                except FileNotFoundError:
                    pass
            except OSError as exc:
                # Fallback: keep at src so state isn't lost
                self.update(task_id, status="COMPLETED", completed_at=now, **extra)
                return self.load(task_id)
        return data

    def remove_from_history(self, task_id: str) -> bool:
        """Hapus permanen dari folder completed/. Return True jika ada yang dihapus."""
        path = self._completed_path(task_id)
        with self._lock:
            try:
                os.remove(path)
                return True
            except FileNotFoundError:
                return False

    def list_history(self) -> list[dict]:
        """List semua task di folder completed/, urut updated_at desc."""
        results = []
        for path in self._completed_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        results.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
        return results

    def list_all_with_history(self, status_filter: list[str] | None = None) -> list[dict]:
        """Gabungkan list_all (active) + list_history (completed) jadi satu output."""
        active = self.list_all(status_filter=status_filter)
        history = self.list_history()
        # History items yang berstatus selain yang ada di status_filter tetap tampilkan
        if status_filter is None:
            return active + history
        history_filtered = [h for h in history if h.get("status") in status_filter]
        return active + history_filtered

    def create(self, url: str, filename: str, save_path: str,
               total_size: int, thread_count: int,
               speed_limit_kbps: int = 0,
               graceful_exit: bool = False,
               task_id: str | None = None,
               parts_dir: str | None = None) -> dict:
        """Buat metadata baru untuk download task.

        Args:
            url: URL sumber file.
            filename: Nama file output.
            save_path: Path absolut penyimpanan final.
            total_size: Ukuran total file (byte).
            thread_count: Jumlah thread yang akan digunakan.
            speed_limit_kbps: Batas kecepatan (0 = unlimited).
            graceful_exit: Flag exit (default False saat dibuat).
            task_id: Optional task ID (dibuat baru jika tidak diberikan).
            parts_dir: Optional directory for temporary .part files.

        Returns:
            Dict metadata lengkap yang sudah disimpan.
        """
        task_id = task_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if thread_count <= 0:
            thread_count = 1
        chunk_size = (total_size + thread_count - 1) // thread_count

        chunks = []
        for i in range(thread_count):
            start = i * chunk_size
            end = min(start + chunk_size - 1, max(total_size - 1, 0))
            if start > end:
                end = start
            chunks.append({
                "index": i,
                "start": start,
                "end": end,
                "bytes_done": 0
            })

        metadata = {
            "id": task_id,
            "url": url,
            "filename": filename,
            "save_path": save_path,
            "total_size": total_size,
            "downloaded_size": 0,
            "status": "PENDING",
            "graceful_exit": graceful_exit,
            "speed_limit_kbps": speed_limit_kbps,
            "thread_count": thread_count,
            "chunks": chunks,
            "created_at": now,
            "updated_at": now
        }
        if parts_dir:
            metadata["parts_dir"] = parts_dir

        with self._lock:
            with open(self._metadata_path(task_id), "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

        return metadata

    def load(self, task_id: str) -> dict | None:
        """Muat metadata dari disk.

        Args:
            task_id: UUID task download.

        Returns:
            Dict metadata atau None jika file tidak ditemukan.
        """
        path = self._metadata_path(task_id)
        if not path.exists():
            return None
        with self._lock:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None

    def update(self, task_id: str, **kwargs):
        """Update satu atau lebih field metadata.

        Field yang di-update langsung di-merge ke dict yang ada.
        'updated_at' otomatis diperbarui ke timestamp saat ini.

        Args:
            task_id: UUID task download.
            **kwargs: Field yang akan di-update (status, downloaded_size, chunks, dll).
        """
        path = self._metadata_path(task_id)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._lock:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return

            data.update(kwargs)
            data["updated_at"] = now

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

    def delete(self, task_id: str):
        """Hapus file metadata untuk task tertentu.

        Args:
            task_id: UUID task download.
        """
        path = self._metadata_path(task_id)
        with self._lock:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def list_all(self, status_filter: list[str] | None = None) -> list[dict]:
        """List semua metadata task di queue.

        Args:
            status_filter: Jika diberikan, hanya return task dengan status
                          dalam list ini. Contoh: ["PENDING", "PAUSED"].

        Returns:
            List of dict metadata.
        """
        results = []
        for path in sorted(self._queue_dir.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if status_filter is None or data.get("status") in status_filter:
                    results.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def update_chunk_progress(self, task_id: str, chunk_index: int,
                              bytes_done: int, downloaded_size: int):
        """Update progress satu chunk sekaligus total downloaded_size.

        Ini adalah optimized path yang meng-update chunk bytes_done
        dan total downloaded_size dalam satu operasi untuk mengurangi
        jumlah write ke disk.

        Args:
            task_id: UUID task download.
            chunk_index: Index chunk (0-based).
            bytes_done: Total byte yang sudah diunduh untuk chunk ini.
            downloaded_size: Total byte yang sudah diunduh untuk semua chunk.
        """
        path = self._metadata_path(task_id)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        with self._lock:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return

            if 0 <= chunk_index < len(data.get("chunks", [])):
                data["chunks"][chunk_index]["bytes_done"] = bytes_done
            data["downloaded_size"] = downloaded_size
            data["updated_at"] = now

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

    def recover_crashed_tasks(self) -> list[dict]:
        """Saat boot: temukan task yang belum selesai dan tandai crash.

        - Task dengan status "DOWNLOADING" → ubah ke "PAUSED", set
          graceful_exit = false (artinya app crash sebelumnya).
        - Task dengan status "PENDING" atau "PAUSED" tidak diubah statusnya,
          tapi tetap di-return untuk di-restore ke UI.

        Returns:
            List of dict metadata untuk task yang perlu di-restore.
        """
        active_statuses = ["DOWNLOADING", "PAUSED", "PENDING"]
        tasks = self.list_all(status_filter=active_statuses)
        recovered = []

        for task in tasks:
            if task.get("status") == "DOWNLOADING":
                # App crash — tandai sebagai PAUSED dengan flag crash
                self.update(task["id"],
                            status="PAUSED",
                            graceful_exit=False)
                task["status"] = "PAUSED"
                task["graceful_exit"] = False
            recovered.append(task)

        return recovered
