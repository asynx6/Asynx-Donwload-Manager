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
from urllib.parse import urlparse, unquote

from backend.core.downloader import DownloadTask
from backend.core.metadata_manager import MetadataManager
from backend.core.file_validator import resolve_filename
from backend.system.config import load_config


def _guess_filename_from_url(url: str) -> str:
    """Legacy: kept for backwards compatibility; prefer resolve_filename()."""
    return resolve_filename("", "", url)


class DownloadManager:
    """Manajer download task aktif dan recovery."""

    def __init__(self, queue_dir: str = "data/queue"):
        self._queue_dir = os.path.expandvars(os.path.expanduser(queue_dir))
        self._meta_mgr = MetadataManager(self._queue_dir)
        self._active: dict[str, DownloadTask] = {}
        self._lock = threading.Lock()
        self._progress_callback: Optional[Callable[[dict], None]] = None
        self._completed_count_cache = 0
        self._completed_count_cache_at = 0.0
        config = load_config()
        self._max_concurrent = config.get("max_concurrent_downloads", 3)
        from backend.core.download_scheduler import get_scheduler
        get_scheduler().set_global_limit(config.get("speed_limit_kbps", 0))

    def set_progress_callback(self, callback: Optional[Callable[[dict], None]]):
        self._progress_callback = callback

    def set_max_concurrent(self, value: int):
        self._max_concurrent = max(1, min(value, 5))

    def update_global_speed_limit(self, limit_kbps: int):
        from backend.core.download_scheduler import get_scheduler
        get_scheduler().set_global_limit(limit_kbps)
        self._apply_scheduler_limits()

    def _apply_scheduler_limits(self):
        from backend.core.download_scheduler import get_scheduler
        scheduler = get_scheduler()
        with self._lock:
            for task_id, t in self._active.items():
                if t.status == "DOWNLOADING":
                    limit = scheduler.limit_for_task(task_id)
                    t.set_speed_limit(limit)

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
        try:
            # Validasi URL scheme (http dan https saja)
            try:
                parsed = urlparse(url)
                if parsed.scheme.lower() not in ("http", "https"):
                    return {"error": "Only HTTP and HTTPS protocols are supported"}
            except Exception:
                return {"error": "Invalid URL format"}

            # Cek duplikat URL yang masih aktif.
            # - PENDING/DOWNLOADING → blokir (benar-benar sedang aktif)
            # - PAUSED → auto-resume (user mau download URL yang sama)
            # - ERROR/CANCELLED/COMPLETED → cleanup task lama, izinkan re-add
            with self._lock:
                for task_id, task in list(self._active.items()):
                    if task.url != url:
                        continue
                    if task.status in ("PENDING", "DOWNLOADING"):
                        return {"error": "URL already in queue", "id": task_id}
                    if task.status == "PAUSED":
                        # Auto-resume task yang sudah ada
                        try:
                            self.resume(task_id)
                        except Exception:
                            pass
                        return self._task_info(task)
                    if task.status in ("ERROR", "CANCELLED", "COMPLETED"):
                        # Cleanup task lama supaya user bisa re-add
                        try:
                            del self._active[task_id]
                        except KeyError:
                            pass

            config = load_config()
            if save_path:
                save_path = os.path.expandvars(os.path.expanduser(save_path))
            else:
                save_path = os.path.expandvars(
                    os.path.expanduser(config.get("default_download_path", "%USERPROFILE%\\Downloads"))
                )
            max_threads = max(1, min(config.get("max_threads_per_download", 8), 8))
            limit = speed_limit_kbps if speed_limit_kbps else config.get("speed_limit_kbps", 0)

            # Jika slot concurrent penuh, tetap buat metadata PENDING;
            # _try_start_pending akan menjalankannya begitu slot kosong.
            max_concurrent = max(1, self._max_concurrent)
            active_downloading = sum(
                1 for t in self._active.values() if t.status == "DOWNLOADING"
            )
            queued = active_downloading >= max_concurrent

            task = DownloadTask(
                url=url,
                save_path=save_path,
                filename=filename,
                speed_limit_kbps=limit,
                max_threads=max_threads,
                queue_dir=self._queue_dir,
                on_progress=self._broadcast,
            )
            # Kalau queued, jangan langsung start meskipun _try_start_pending dipanggil.
            task._queued = queued

            # Resolve filename deterministik sebelum metadata create.
            display_filename = resolve_filename(filename, "", url)
            full_save_path = os.path.join(save_path, display_filename) if display_filename else ""
            # FIX Bug #1: set filename SEGERA supaya UI langsung tampil nama file.
            # start() di background thread akan resolve ulang nanti.
            task._filename = display_filename

            try:
                self._meta_mgr.create(
                    url=url,
                    filename=display_filename,
                    save_path=full_save_path,
                    total_size=0,
                    thread_count=max_threads,
                    speed_limit_kbps=limit,
                    graceful_exit=True,
                    task_id=task.task_id,
                )
                task._status = "PENDING"
            except Exception as exc:
                print(f"[DownloadManager] metadata create failed: {exc}")
                task._status = "ERROR"

            with self._lock:
                self._active[task.task_id] = task

            self._try_start_pending()
            return self._task_info(task)
        except Exception as exc:
            print(f"[DownloadManager] start_new fatal: {exc}")
            return {"error": str(exc)}

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

    def _try_start_pending(self) -> bool:
        """Mulai task PENDING jika masih ada slot concurrent.

        Menggunakan Shortest-Job-First (SJF) ordering: task dengan total_size
        terkecil didahulukan, lalu task yang sudah lama pending (created_at).

        Returns:
            True jika sebuah task berhasil di-start, False jika tidak.
        """
        with self._lock:
            active_count = sum(
                1 for t in self._active.values() if t.status == "DOWNLOADING"
            )
            if active_count >= self._max_concurrent:
                return False
            pending = [
                t for t in self._active.values()
                if t.status == "PENDING" and t.task_id
            ]
            if not pending:
                return False

            # SJF: urutkan berdasarkan total_size (kecil dulu), tie-break created_at.
            def _sort_key(t):
                meta = self._meta_mgr.load(t.task_id) or {}
                size = meta.get("total_size", 0) or 0
                created = meta.get("created_at", "")
                # task yang tidak di-queued diutamakan sedikit
                queued = 1 if getattr(t, "_queued", False) else 0
                return (queued, size, created)

            pending.sort(key=_sort_key)
            task = pending[0]
            task._queued = False

        def run_task():
            try:
                from backend.core.download_scheduler import get_scheduler
                meta = self._meta_mgr.load(task.task_id) or {}
                priority = meta.get("priority", 5)
                get_scheduler().register_task(task.task_id, priority=priority)
                self._apply_scheduler_limits()
                task.start()
            except Exception as exc:
                print(f"[DownloadManager] task {task.task_id} failed: {exc}")
                import traceback; traceback.print_exc()
            finally:
                from backend.core.download_scheduler import get_scheduler
                get_scheduler().unregister_task(task.task_id)
                self._apply_scheduler_limits()
                self._try_start_pending()

        threading.Thread(target=run_task, daemon=True).start()
        return True

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
            from backend.core.download_scheduler import get_scheduler
            get_scheduler().unregister_task(task_id)
            self._apply_scheduler_limits()
            return self._task_info(task)
        # 404 fix: kalau sudah COMPLETED, kembalikan info saja tanpa error
        meta = self._meta_mgr.load(task_id)
        if meta and meta.get("status") in ("COMPLETED", "ERROR", "CANCELLED"):
            return self._meta_to_info(meta)
        completed_meta = self._completed_load(task_id)
        if completed_meta:
            return completed_meta
        return {"error": "Task not found"}

    def resume(self, task_id: str) -> dict:
        with self._lock:
            task = self._active.get(task_id)
        if task:
            if task.status in ("PAUSED", "ERROR"):
                def run_task():
                    try:
                        from backend.core.download_scheduler import get_scheduler
                        meta = self._meta_mgr.load(task_id) or {}
                        priority = meta.get("priority", 5)
                        get_scheduler().register_task(task_id, priority=priority)
                        self._apply_scheduler_limits()
                        task.resume()
                    finally:
                        from backend.core.download_scheduler import get_scheduler
                        get_scheduler().unregister_task(task_id)
                        self._apply_scheduler_limits()
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

            def run_task():
                try:
                    from backend.core.download_scheduler import get_scheduler
                    priority = meta.get("priority", 5)
                    get_scheduler().register_task(task_id, priority=priority)
                    self._apply_scheduler_limits()
                    task.resume()
                finally:
                    from backend.core.download_scheduler import get_scheduler
                    get_scheduler().unregister_task(task_id)
                    self._apply_scheduler_limits()
                    self._try_start_pending()
            threading.Thread(target=run_task, daemon=True).start()
            return self._task_info(task)
        completed_meta = self._completed_load(task_id)
        if completed_meta:
            # Sudah selesai, tidak ada state yang bisa di-resume.
            return completed_meta
        return {"error": "Task not found"}

    def _completed_load(self, task_id: str) -> Optional[dict]:
        """Loader tambahan untuk history folder completed/ (kalau aktif
        tapi sudah pernah di-mark_complete sebelum di-restart)."""
        try:
            history = self._meta_mgr.list_history()
        except Exception:
            return None
        for meta in history:
            if meta.get("id") == task_id:
                return self._meta_to_info(meta)
        return None

    def delete(self, task_id: str, delete_parts: bool = True,
               remove_from_history: bool = False) -> dict:
        meta_removed = False
        with self._lock:
            task = self._active.pop(task_id, None)
        if task:
            task.cancel()
            from backend.core.download_scheduler import get_scheduler
            get_scheduler().unregister_task(task_id)
            self._apply_scheduler_limits()
            # Bug-1 fix: extract metadata BEFORE deleting file supaya kita
            # bisa dapat parts_dir + chunks untuk membersihkan part files di
            # lokasi yang benar (bukan default AsynxDL/.parts).
            existing_meta = self._meta_mgr.load(task_id) or {}
            parts_dir = existing_meta.get(
                "parts_dir",
                os.path.dirname(existing_meta.get("save_path", "")),
            )
            chunks = existing_meta.get("chunks", []) or []
            if self._meta_mgr.delete(task_id):
                meta_removed = True
            # Bersihkan parts di parts_dir yang benar dari metadata.
            try:
                from backend.core.parts_dir import purge_all_parts_for, purge_all_orphans
                purge_all_parts_for(task_id, parts_dir=parts_dir)
                purge_all_orphans()
            except Exception:
                pass
            if delete_parts and chunks and parts_dir:
                import glob
                for part in glob.glob(os.path.join(parts_dir, f"{task_id}.part*")):
                    try:
                        os.remove(part)
                    except FileNotFoundError:
                        pass
                final_temp = os.path.join(parts_dir, f"{task_id}.final")
                try:
                    os.remove(final_temp)
                except FileNotFoundError:
                    pass
            if remove_from_history:
                self._meta_mgr.remove_from_history(task_id)
            return {"ok": True, "meta_removed": meta_removed}
        meta = self._meta_mgr.load(task_id)
        if not meta:
            # 404 fix: kalau tidak ada di folder active tapi ada di history,
            # user mungkin meminta remove_from_history - arahkan ke sana.
            if remove_from_history:
                return self.remove_history(task_id, delete_parts=delete_parts)
            return {"error": "Task not found"}
        # Hapus metadata dari active folder
        self._meta_mgr.delete(task_id)
        # Bersihkan semua .part dan .final di parts_dir
        try:
            from backend.core.parts_dir import purge_all_parts_for, purge_all_orphans
            purge_all_parts_for(task_id)
            purge_all_orphans()
        except Exception:
            pass
        if delete_parts and meta.get("chunks"):
            parts_dir = meta.get("parts_dir", os.path.dirname(meta.get("save_path", "")))
            for chunk in meta.get("chunks", []):
                part = os.path.join(parts_dir, f"{task_id}.part{chunk['index']}")
                try:
                    os.remove(part)
                except FileNotFoundError:
                    pass
            try:
                final_temp = os.path.join(parts_dir, f"{task_id}.final")
                if os.path.exists(final_temp):
                    os.remove(final_temp)
            except FileNotFoundError:
                pass
        # 404 fix: kalau remove_from_history=True, hapus juga dari completed/
        if remove_from_history:
            self._meta_mgr.remove_from_history(task_id)
        return {"ok": True}

    def remove_history(self, task_id: str, delete_parts: bool = True) -> dict:
        """Hapus permanen task dari history completed/ + bersihkan parts.

        FIX Bug #4: juga hapus dari _active kalau masih ada (task ERROR/
        COMPLETED/CANCELLED yang belum di-cleanup).
        """
        # Hapus dari _active jika ada (supaya hilang dari UI list)
        with self._lock:
            task = self._active.pop(task_id, None)
        if task:
            try:
                task.cancel()
            except Exception:
                pass
            from backend.core.download_scheduler import get_scheduler
            get_scheduler().unregister_task(task_id)
            self._apply_scheduler_limits()

        parts_dir = None
        meta = self._meta_mgr.load(task_id)
        if meta:
            parts_dir = meta.get("parts_dir")
        if not parts_dir:
            for h in self._meta_mgr.list_history():
                if h.get("id") == task_id:
                    parts_dir = h.get("parts_dir")
                    break
        if delete_parts and parts_dir:
            part_glob = os.path.join(parts_dir, f"{task_id}.part*")
            import glob
            for part in glob.glob(part_glob):
                try:
                    os.remove(part)
                except FileNotFoundError:
                    pass
            final_part = os.path.join(parts_dir, f"{task_id}.final")
            try:
                os.remove(final_part)
            except FileNotFoundError:
                pass
        # Hapus dari active metadata folder
        self._meta_mgr.delete(task_id)
        removed = self._meta_mgr.remove_from_history(task_id)
        return {"ok": True, "removed": removed}

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

    def sjf_order(self) -> list[str]:
        """Strategy #8 — Shortest-Job-First queue order.

        Urutkan task PENDING/PAUSED berdasarkan ``total_size`` ascending.
        Dipakai otomatis saat ``max_concurrent_downloads`` slot tersedia.
        Caller boleh disable via config flag ``sjf_enabled=False``.
        """
        with self._lock:
            pending = [
                t for t in self._active.values()
                if t.status in ("PENDING", "PAUSED") and t.total_size > 0
            ]
        pending.sort(key=lambda t: getattr(t, "_total_size", 0) or 0)
        return [t.task_id for t in pending]  # type: ignore[attr-defined]

    def enqueue_sjf(self) -> int:
        """Jalankan SJF ordering & start; return jumlah task dimulai."""
        started = 0
        for _ in self.sjf_order():
            if self._try_start_pending():
                started += 1
            else:
                break
        return started

    def get_metrics(self) -> dict:
        """Export ringkasan metrics download."""
        import shutil
        active_count = len(self._active)
        downloading_count = 0
        paused_count = 0
        pending_count = 0
        failed_count = 0
        total_speed_kbps = 0.0
        
        with self._lock:
            for task in self._active.values():
                if task.status == "DOWNLOADING":
                    downloading_count += 1
                    total_speed_kbps += getattr(task, "_speed_kbps", 0.0)
                elif task.status == "PAUSED":
                    paused_count += 1
                elif task.status == "PENDING":
                    pending_count += 1
                elif task.status == "ERROR":
                    failed_count += 1

        now = time.monotonic()
        completed_count = self._completed_count_cache
        if now - self._completed_count_cache_at > 30.0:
            try:
                completed_count = len(self._meta_mgr.list_history())
                self._completed_count_cache = completed_count
                self._completed_count_cache_at = now
            except Exception:
                pass

        config = load_config()
        save_path = config.get("default_download_path", "%USERPROFILE%\\Downloads")
        save_path = os.path.expandvars(os.path.expanduser(save_path))
        free_space_bytes = 0
        try:
            drive = os.path.splitdrive(save_path)[0] or os.path.sep
            free_space_bytes = shutil.disk_usage(drive).free
        except Exception:
            pass

        return {
            "active_tasks": active_count,
            "downloading_tasks": downloading_count,
            "paused_tasks": paused_count,
            "pending_tasks": pending_count,
            "failed_tasks": failed_count,
            "completed_tasks": completed_count,
            "total_speed_kbps": round(total_speed_kbps, 1),
            "free_space_bytes": free_space_bytes,
        }

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
