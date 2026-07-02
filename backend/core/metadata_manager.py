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
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


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
        os.makedirs(self._queue_dir, exist_ok=True)

    def _metadata_path(self, task_id: str) -> Path:
        """Path file metadata untuk task_id tertentu."""
        return self._queue_dir / f"{task_id}.json"

    def create(self, url: str, filename: str, save_path: str,
               total_size: int, thread_count: int,
               speed_limit_kbps: int = 0,
               graceful_exit: bool = False,
               task_id: str | None = None) -> dict:
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
