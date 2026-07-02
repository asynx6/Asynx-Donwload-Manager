"""
AsynxDL — API Shared State
~~~~~~~~~~~~~~~~~~~~~~~~~~
DownloadManager: mengelola task aktif, queue, start/pause/resume/cancel,
dengan progress callback yang dapat di-hook ke WebSocket broadcaster.
"""

import os
import threading
import time
from typing import Callable, Optional

from backend.core.downloader import DownloadTask
from backend.core.metadata_manager import MetadataManager
from backend.system.config import load_config


class DownloadManager:
    """Manajer download task aktif dan recovery."""

    def __init__(self, queue_dir: str = "data/queue"):
        self._queue_dir = os.path.expandvars(os.path.expanduser(queue_dir))
        self._meta_mgr = MetadataManager(queue_dir)
        self._active: dict[str, DownloadTask] = {}
        self._lock = threading.Lock()
        self._progress_callback: Optional[Callable[[dict], None]] = None
        self._max_concurrent = load_config().get("max_concurrent_downloads", 3)

    def set_progress_callback(self, callback: Optional[Callable[[dict], None]]):
        self._progress_callback = callback

    def set_max_concurrent(self, value: int):
        self._max_concurrent = max(1, min(value, 5))

    def _broadcast(self, task: DownloadTask, info: dict):
        if self._progress_callback:
            try:
                self._progress_callback(info)
            except Exception:
                pass

    def start_new(
        self,
        url: str,
        filename: str = "",
        save_path: str = "",
        speed_limit_kbps: int = 0,
    ) -> dict:
        """Tambah download baru ke queue dan mulai download."""
        # Cek duplikat URL yang masih aktif
        with self._lock:
            for task_id, task in self._active.items():
                if task.url == url and task.status in ("PENDING", "DOWNLOADING", "PAUSED"):
                    return {"error": "URL already in queue", "id": task_id}

        # Jika max concurrent tercapai, buat metadata PENDING tapi belum mulai
        config = load_config()
        max_concurrent = self._max_concurrent
        active_count = sum(
            1 for t in self._active.values() if t.status == "DOWNLOADING"
        )

        if save_path:
            save_path = os.path.expandvars(os.path.expanduser(save_path))
        else:
            save_path = os.path.expandvars(
                os.path.expanduser(config.get("default_download_path", "%USERPROFILE%\\Downloads"))
            )

        max_threads = max(1, min(config.get("max_threads_per_download", 8), 8))
        limit = speed_limit_kbps if speed_limit_kbps else config.get("speed_limit_kbps", 0)

        task = DownloadTask(
            url=url,
            save_path=save_path,
            filename=filename,
            speed_limit_kbps=limit,
            max_threads=max_threads,
            queue_dir=self._queue_dir,
            on_progress=self._broadcast,
        )

        # Buat metadata PENDING terlebih dahulu agar task_id tersedia
        task._meta_mgr.create(
            url=url,
            filename=filename,
            save_path=os.path.join(save_path, filename) if filename else "",
            total_size=0,
            thread_count=max_threads,
            speed_limit_kbps=limit,
            graceful_exit=True,
            task_id=task.task_id,
        )
        task._status = "PENDING"

        with self._lock:
            self._active[task.task_id] = task

        self._try_start_pending()

        return self._task_info(task)

    def _task_info(self, task: DownloadTask) -> dict:
        info = task._progress_dict() if hasattr(task, "_progress_dict") else {
            "id": task.task_id,
            "url": task.url,
            "status": task.status,
            "speed_kbps": task.speed_kbps,
            "percent": task.percent,
            "downloaded_size": task._downloaded_size,
            "total_size": task._total_size,
            "eta_seconds": task.eta_seconds,
        }
        # Merge dengan metadata untuk field lengkap (filename, save_path, dll)
        if task.task_id:
            meta = self._meta_mgr.load(task.task_id)
            if meta:
                meta.setdefault("graceful_exit", True)
                meta.setdefault("speed_kbps", 0.0)
                meta.setdefault("eta_seconds", 0)
                meta.setdefault("percent", 0.0)
                for key in ("filename", "save_path", "graceful_exit",
                            "speed_limit_kbps", "thread_count", "chunks",
                            "created_at", "updated_at"):
                    if key not in info and key in meta:
                        info[key] = meta[key]
        return info

    def _try_start_pending(self):
        """Mulai task PENDING jika masih ada slot concurrent."""
        with self._lock:
            active_count = sum(
                1 for t in self._active.values() if t.status == "DOWNLOADING"
            )
            if active_count >= self._max_concurrent:
                return
            pending = [
                t for t in self._active.values()
                if t.status == "PENDING" and t.task_id
            ]
            if not pending:
                return
            task = pending[0]

        def run_task():
            try:
                task.start()
            finally:
                self._try_start_pending()

        threading.Thread(target=run_task, daemon=True).start()

    def get_all(self) -> list[dict]:
        """List semua task aktif + metadata queue."""
        with self._lock:
            active_ids = set(self._active.keys())
            result = [self._task_info(t) for t in self._active.values()]

        # Tambahkan metadata yang belum di-load ke active
        for meta in self._meta_mgr.list_all():
            if meta["id"] not in active_ids:
                result.append(self._meta_to_info(meta))
        return result

    def get_one(self, task_id: str) -> Optional[dict]:
        with self._lock:
            task = self._active.get(task_id)
        if task:
            return self._task_info(task)
        meta = self._meta_mgr.load(task_id)
        if meta:
            return self._meta_to_info(meta)
        return None

    def _meta_to_info(self, meta: dict) -> dict:
        total = meta.get("total_size", 0)
        downloaded = meta.get("downloaded_size", 0)
        percent = (downloaded / total * 100) if total > 0 else 0.0
        return {
            "id": meta.get("id"),
            "url": meta.get("url"),
            "filename": meta.get("filename"),
            "save_path": meta.get("save_path"),
            "total_size": total,
            "downloaded_size": downloaded,
            "status": meta.get("status"),
            "graceful_exit": meta.get("graceful_exit", True),
            "speed_limit_kbps": meta.get("speed_limit_kbps", 0),
            "thread_count": meta.get("thread_count", 1),
            "chunks": meta.get("chunks", []),
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("updated_at"),
            "speed_kbps": 0.0,
            "eta_seconds": 0,
            "percent": round(percent, 1),
        }

    def pause(self, task_id: str) -> dict:
        with self._lock:
            task = self._active.get(task_id)
        if task:
            task.pause()
            return self._task_info(task)
        return {"error": "Task not found"}

    def resume(self, task_id: str) -> dict:
        with self._lock:
            task = self._active.get(task_id)
        if task:
            if task.status in ("PAUSED", "ERROR"):
                def run_task():
                    try:
                        task.resume()
                    finally:
                        self._try_start_pending()
                threading.Thread(target=run_task, daemon=True).start()
            return self._task_info(task)
        # Task hanya ada di metadata; buat DownloadTask baru
        meta = self._meta_mgr.load(task_id)
        if meta:
            task = DownloadTask(
                url=meta["url"],
                save_path=os.path.dirname(meta["save_path"]),
                filename=meta["filename"],
                speed_limit_kbps=meta.get("speed_limit_kbps", 0),
                max_threads=meta.get("thread_count", 8),
                queue_dir=self._queue_dir,
                on_progress=self._broadcast,
            )
            task._task_id = task_id
            task._status = "PAUSED"
            task._total_size = meta.get("total_size", 0)
            task._downloaded_size = meta.get("downloaded_size", 0)
            with self._lock:
                self._active[task_id] = task
            threading.Thread(target=task.resume, daemon=True).start()
            return self._task_info(task)
        return {"error": "Task not found"}

    def delete(self, task_id: str, delete_parts: bool = True) -> dict:
        with self._lock:
            task = self._active.pop(task_id, None)
        if task:
            task.cancel()
            return {"ok": True}
        meta = self._meta_mgr.load(task_id)
        if meta:
            self._meta_mgr.delete(task_id)
            if delete_parts:
                save_path = meta.get("save_path", "")
                for chunk in meta.get("chunks", []):
                    part = f"{save_path}.part{chunk['index']}"
                    try:
                        os.remove(part)
                    except FileNotFoundError:
                        pass
            return {"ok": True}
        return {"error": "Task not found"}

    def recover(self) -> list[dict]:
        """Recovery state saat boot."""
        recovered = self._meta_mgr.recover_crashed_tasks()
        # Load semua task ke active sebagai PAUSED/PENDING
        with self._lock:
            for meta in recovered:
                task_id = meta["id"]
                if task_id not in self._active:
                    task = DownloadTask(
                        url=meta["url"],
                        save_path=os.path.dirname(meta["save_path"]),
                        filename=meta["filename"],
                        speed_limit_kbps=meta.get("speed_limit_kbps", 0),
                        max_threads=meta.get("thread_count", 8),
                        queue_dir=self._queue_dir,
                        on_progress=self._broadcast,
                    )
                    task._task_id = task_id
                    task._status = "PAUSED"
                    task._total_size = meta.get("total_size", 0)
                    task._downloaded_size = meta.get("downloaded_size", 0)
                    self._active[task_id] = task
        return [self._task_info(t) for t in self._active.values()]

    def pause_all(self):
        with self._lock:
            tasks = list(self._active.values())
        for task in tasks:
            if task.status == "DOWNLOADING":
                task.pause()

    def shutdown(self):
        """Graceful shutdown: pause semua download aktif."""
        self.pause_all()
        # Beri waktu state tersimpan
        time.sleep(0.5)


# Singleton instance
manager = DownloadManager()
