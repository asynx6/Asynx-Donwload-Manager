import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from .chunk_manager import (
    download_chunk,
    probe_url,
    _get_content_length,
    _supports_range,
    _build_retry_session,
)
from .file_validator import (
    check_disk_space,
    is_safe_path,
    normalize_path,
    sanitize_filename,
    resolve_duplicate_name,
    resolve_filename,
)
from .merger import merge_parts
from .metadata_manager import MetadataManager
from .speed_limiter import SpeedLimiter


# AsynxDL application cache directory under %LOCALAPPDATA%
_APP_LOCAL_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AsynxDL"
)


def _ensure_app_local_dir() -> str:
    os.makedirs(_APP_LOCAL_DIR, exist_ok=True)
    return _APP_LOCAL_DIR


def _get_parts_dir(task_id: str) -> str:
    r"""Return the hidden parts directory for this task.

    Parts are stored in %LOCALAPPDATA%\AsynxDL\.parts so they do not clutter the
    user's download folder. The directory is marked hidden on Windows.
    """
    _ensure_app_local_dir()
    parts_dir = os.path.join(_APP_LOCAL_DIR, ".parts")
    os.makedirs(parts_dir, exist_ok=True)
    # Mark the directory hidden on Windows
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(parts_dir, 0x02)
    except Exception:
        pass
    return parts_dir


class DownloadTask:
    """Orchestrator untuk satu download task.

    Satu instance = satu file. Mendukung:
        - Multi-thread chunked download (hingga 8 thread)
        - Single-thread fallback jika server tidak mendukung Range
        - Pause / Resume dengan state persistence
        - Auto-reconnect (via chunk_manager retry)
        - Speed limiting

    Thread safety: stop_event digunakan untuk koordinasi antar thread.
    MetadataManager memiliki lock internal sendiri.
    """

    def __init__(
        self,
        url: str,
        save_path: str = "",
        filename: str = "",
        speed_limit_kbps: int = 0,
        max_threads: int = 8,
        queue_dir: str = "data/queue",
        on_progress=None,
    ):
        """Inisialisasi DownloadTask.

        Args:
            url: URL file yang akan diunduh.
            save_path: Path folder tempat menyimpan file (default: %USERPROFILE%\\Downloads).
            filename: Nama file output (opsional, diambil dari URL jika kosong).
            speed_limit_kbps: Batas kecepatan download (0 = unlimited).
            max_threads: Maksimum thread untuk chunked download (1-8).
            queue_dir: Path ke folder data/queue untuk metadata.
            on_progress: Callback(taskself, dict_progress) dipanggil saat progress update.
        """
        self.url = url
        self._max_threads = min(max(max_threads, 1), 8)
        self._on_progress = on_progress

        # Metadata manager
        self._meta_mgr = MetadataManager(queue_dir)

        # Speed limiter (shared antar chunk thread)
        self._limiter = SpeedLimiter(speed_limit_kbps)

        # Control flags
        self._stop_event = threading.Event()
        self._executor: ThreadPoolExecutor | None = None
        self._futures: list = []
        self._task_id: str = str(uuid.uuid4())
        self._status = "PENDING"

        # Paths (di-resolve saat start())
        if not save_path:
            save_path = os.path.expandvars("%USERPROFILE%\\Downloads")
        self._requested_save_path = normalize_path(save_path)
        self._requested_filename = filename

        # Session HTTP (reuse connection pool)
        self._session = None

        # Internal state
        self._downloaded_size = 0
        self._total_size = 0
        self._last_progress_time = time.monotonic()
        self._last_downloaded = 0
        self._speed_kbps = 0.0
        self._filename = filename
        self._final_path = ""

    # ── Properties ──────────────────────────────────────────────

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def status(self) -> str:
        return self._status

    @property
    def speed_kbps(self) -> float:
        return self._speed_kbps

    @property
    def percent(self) -> float:
        if self._total_size <= 0:
            return 0.0
        return min(100.0, (self._downloaded_size / self._total_size) * 100.0)

    @property
    def eta_seconds(self) -> int:
        if self._speed_kbps <= 0:
            return 0
        remaining = self._total_size - self._downloaded_size
        return int(remaining / (self._speed_kbps * 1024))

    # ── Public Methods ──────────────────────────────────────────

    def start(self):
        """Mulai download.

        Alur:
            1. Probe URL (HEAD request) → content_length, supports_range, filename
            2. Validasi: disk space, filename, duplicate
            3. Hitung chunk config dan buat metadata
            4. Spawn thread pool untuk download chunk
            5. Merge setelah semua chunk selesai

        Method ini berjalan sinkron (blocking) — panggil dari thread
        terpisah jika ingin non-blocking.
        """
        if self._status not in ("PENDING", "PAUSED"):
            return

        self._stop_event.clear()
        self._status = "DOWNLOADING"
        self._session = _build_retry_session()

        try:
            # 1. Probe URL
            info = probe_url(self.url)
            self._total_size = info["content_length"]
            supports_range = info["supports_range"]
            url_filename = info["filename"]

            if self._total_size <= 0:
                self._status = "ERROR"
                self._broadcast_progress()
                return

            # 2. Resolve filename dan path — pakai resolve_filename() deterministik
            # supaya URL dengan %20 / karakter encoded tampil benar sejak detik
            # pertama di UI (bukan "A" atau "unnamed_file").
            filename = resolve_filename(
                self._requested_filename, url_filename, self.url
            )
            filename = sanitize_filename(filename)
            save_folder = self._requested_save_path
            os.makedirs(save_folder, exist_ok=True)
            filename = resolve_duplicate_name(save_folder, filename)
            final_path = normalize_path(os.path.join(save_folder, filename))
            # Keamanan: file final harus berada di dalam folder yang diminta
            if not is_safe_path(save_folder, final_path):
                self._status = "ERROR"
                self._broadcast_progress()
                return
            self._filename = filename
            self._final_path = final_path

            # 3. Cek disk space
            if not check_disk_space(final_path, self._total_size):
                self._status = "ERROR"
                self._broadcast_progress()
                return

            # 4. Hitung chunk count secara dinamis berdasarkan ukuran file
            #    (lihat chunk_calculator.auto_chunks_for_size). Default static
            #    ``max_threads_per_download`` jadi upper-cap.
            if not supports_range:
                thread_count = 1
            else:
                from .chunk_calculator import auto_chunks_for_size
                thread_count = auto_chunks_for_size(
                    self._total_size,
                    cap=self._max_threads,
                )

            parts_dir = _get_parts_dir(self._task_id)

            # 5. Buat metadata
            metadata = self._meta_mgr.create(
                url=self.url,
                filename=filename,
                save_path=final_path,
                total_size=self._total_size,
                thread_count=thread_count,
                speed_limit_kbps=self._limiter.limit_kbps,
                graceful_exit=False,
                task_id=self._task_id,
                parts_dir=parts_dir,
            )

            self._broadcast_progress()

            # 6. Download chunks
            self._download_chunks(metadata, supports_range)

            # 7. Merge jika semua chunk selesai dan tidak di-pause
            if self._status == "DOWNLOADING":
                self._merge_and_finalize(metadata)

        except Exception as exc:
            self._status = "ERROR"
            if self._task_id:
                self._meta_mgr.update(self._task_id, status="ERROR")
            self._broadcast_progress()
            raise

        finally:
            self._shutdown_executor()
            if self._session:
                self._session.close()
                self._session = None

    def pause(self):
        """Pause download yang sedang berjalan.

        - Set stop_event → semua thread chunk berhenti setelah buffer saat ini.
        - Update metadata dengan status PAUSED dan graceful_exit=True.
        - Shutdown executor (tunggu thread selesai, max 10 detik).
        """
        if self._status != "DOWNLOADING":
            return
        self._stop_event.set()
        self._status = "PAUSED"

        if self._task_id:
            self._meta_mgr.update(
                self._task_id,
                status="PAUSED",
                graceful_exit=True,
                downloaded_size=self._downloaded_size,
            )

        self._shutdown_executor()
        self._broadcast_progress()

    def resume(self):
        """Resume download yang di-pause.

        - Load metadata dari disk (dapatkan byte offset per chunk).
        - Restart thread pool dengan Range yang sudah di-offset.
        """
        if self._status not in ("PAUSED", "ERROR"):
            return
        if not self._task_id:
            return

        metadata = self._meta_mgr.load(self._task_id)
        if not metadata:
            self._status = "ERROR"
            self._broadcast_progress()
            return

        # Refresh state dari metadata
        self._total_size = metadata.get("total_size", 0)
        self._downloaded_size = metadata.get("downloaded_size", 0)
        self._filename = metadata.get("filename", self._filename)
        self._final_path = metadata.get("save_path", self._final_path)

        self._stop_event.clear()
        self._session = _build_retry_session()
        self._status = "DOWNLOADING"
        self._meta_mgr.update(
            self._task_id,
            status="DOWNLOADING",
            graceful_exit=False,
        )
        self._broadcast_progress()

        try:
            supports_range = self._total_size > 0 and _supports_range(self.url)
            self._download_chunks(metadata, supports_range)

            if self._status == "DOWNLOADING":
                self._merge_and_finalize(metadata)

        except Exception as exc:
            self._status = "ERROR"
            if self._task_id:
                self._meta_mgr.update(self._task_id, status="ERROR")
            self._broadcast_progress()
            raise

        finally:
            self._shutdown_executor()
            if self._session:
                self._session.close()
                self._session = None

    def cancel(self):
        """Batalkan download dan bersihkan file chunk terkait.

        Status ``CANCELLED`` tetap disimpan ke metadata (folder active)
        supaya history ``data/queue/completed/`` atau active ``list_all``
        masih bisa menampilkannya dan user melihat jejak aksi di UI.
        Metadata active folder JANGAN dihapus di sini—hanya chunk file
        ``.part*`` dan ``.final`` yang dibersihkan.
        """
        self._stop_event.set()
        old_status = self._status
        self._status = "CANCELLED"

        if self._task_id:
            metadata = self._meta_mgr.load(self._task_id)
            if metadata:
                self._meta_mgr.update(
                    self._task_id,
                    status="CANCELLED",
                    graceful_exit=True,
                )
            # Hapus .part dan .final dari parts directory.
            # Imports lokal agar tidak ada lingkaran import.
            try:
                from backend.core.parts_dir import purge_all_parts_for
                purge_all_parts_for(self._task_id)
            except Exception:
                pass

        if old_status == "DOWNLOADING":
            self._broadcast_progress()

    # ── Internal Methods ────────────────────────────────────────

    def _download_chunks(self, metadata: dict, supports_range: bool):
        """Spawning thread pool dan jalankan download chunk.

        Untuk setiap chunk, gunakan download_chunk(). Progress di-update
        via _flush_progress yang dipanggil dari dalam loop chunk.
        """
        chunks = metadata.get("chunks", [])
        thread_count = len(chunks)
        if thread_count == 0:
            self._status = "ERROR"
            return

        parts_dir = metadata.get("parts_dir", _get_parts_dir(self._task_id))
        final_path = metadata["save_path"]

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            self._executor = executor
            self._futures = []

            for chunk in chunks:
                idx = chunk["index"]
                start = chunk["start"] + chunk.get("bytes_done", 0)
                end = chunk["end"]
                if start >= end:
                    # Chunk sudah selesai
                    continue

                part_path = os.path.join(parts_dir, f"{self._task_id}.part{idx}")
                future = executor.submit(
                    download_chunk,
                    url=self.url,
                    start=start,
                    end=end,
                    part_path=part_path,
                    limiter=self._limiter,
                    stop_event=self._stop_event,
                    session=self._session,
                )
                self._futures.append((future, chunk))

            # Progress flush timer: throttle metadata writes to disk
            self._last_progress_time = time.monotonic()
            self._last_downloaded = self._downloaded_size
            self._last_meta_flush = 0.0

            # Monitor futures sampai semua selesai. as_completed timeout yang
            # pendek digunakan untuk memberi kesempatan progress update; kita
            # abaikan TimeoutError karena download mungkin masih berjalan.
            pending = {f for f, _ in self._futures}
            while pending and not self._stop_event.is_set():
                done = set()
                try:
                    for done_future in as_completed(pending, timeout=1.0):
                        done.add(done_future)
                        break  # process one completed future per iteration
                except Exception as exc:
                    # TimeoutError / concurrent.futures.TimeoutError: tidak ada
                    # chunk yang selesai dalam 1 detik terakhir. Lanjutkan loop.
                    if "futures unfinished" not in str(exc) and not isinstance(exc, TimeoutError):
                        print(f"[DownloadTask] as_completed error: {exc}")

                pending -= done

                if self._stop_event.is_set():
                    break

                # Hitung total downloaded dari file .part di disk
                self._update_downloaded_size_from_parts(chunks, parts_dir)
                self._compute_speed()
                self._throttled_meta_flush()

            # Tunggu sisa future yang belum selesai (atau cancel)
            for future, chunk in self._futures:
                if future.done():
                    continue
                try:
                    future.result(timeout=0)
                except Exception:
                    pass

            self._executor = None
            self._futures = []

    def _update_downloaded_size_from_parts(self, chunks: list, parts_dir: str):
        """Hitung total byte terdownload dari ukuran file .part di disk.

        Lebih akurat daripada tracking in-memory, terutama untuk resume.
        Throttled ke 1s supaya 8 thread tidak spam os.path.getsize
        tiap iterasi event loop (RAM 4GB + slow network = panggilan
        tiap chunk tiap detik menjadi mahal).
        """
        now = time.monotonic()
        last = getattr(self, "_last_size_poll_at", 0.0)
        if now - last < 1.0:
            return
        self._last_size_poll_at = now
        total = 0
        for chunk in chunks:
            part_path = os.path.join(parts_dir, f"{self._task_id}.part{chunk['index']}")
            try:
                if os.path.exists(part_path):
                    total += os.path.getsize(part_path)
            except OSError:
                pass
        self._downloaded_size = total

    def _throttled_meta_flush(self):
        """Write metadata to disk at most once per second to avoid I/O stalls."""
        if not self._task_id:
            return
        now = time.monotonic()
        if now - self._last_meta_flush < 1.0:
            return
        self._last_meta_flush = now
        self._meta_mgr.update(
            self._task_id, downloaded_size=self._downloaded_size
        )

    def _compute_speed(self):
        """Hitung kecepatan download dalam KB/s."""
        now = time.monotonic()
        elapsed = now - self._last_progress_time
        if elapsed >= 0.5:  # Update setiap ~500ms
            delta_bytes = self._downloaded_size - self._last_downloaded
            self._speed_kbps = (delta_bytes / elapsed) / 1024.0 if elapsed > 0 else 0.0
            self._last_progress_time = now
            self._last_downloaded = self._downloaded_size
            self._broadcast_progress()

    def _merge_and_finalize(self, metadata: dict):
        """Gabungkan semua .part, verifikasi, dan pindahkan ke tujuan akhir."""
        if self._stop_event.is_set():
            return

        chunks = metadata.get("chunks", [])
        parts_dir = metadata.get("parts_dir", _get_parts_dir(self._task_id))
        final_path = metadata["save_path"]
        temp_output = os.path.join(parts_dir, f"{self._task_id}.final")
        part_files = [
            os.path.join(parts_dir, f"{self._task_id}.part{c['index']}")
            for c in sorted(chunks, key=lambda x: x["index"])
        ]

        # Pastikan folder tujuan akhir ada
        final_dir = os.path.dirname(final_path)
        if final_dir:
            os.makedirs(final_dir, exist_ok=True)

        success = merge_parts(
            part_files=part_files,
            output_path=temp_output,
            expected_size=self._total_size,
        )

        if success:
            try:
                os.replace(temp_output, final_path)
                self._status = "COMPLETED"
                # History persistence: pindahkan metadata ke completed/ folder
                # alih-alih menghapusnya seperti sebelumnya. Dengan begitu,
                # tab "Done" pada UI terus menampilkan file yang selesai di
                # download sampai user memilih "Hapus dari Riwayat".
                try:
                    self._meta_mgr.mark_completed(self._task_id)
                except Exception as exc:
                    print(f"[DownloadTask] mark_completed failed: {exc}")
            except OSError as exc:
                self._status = "ERROR"
                print(f"[ERROR] DownloadTask: failed to move final file: {exc}")
                if self._task_id:
                    self._meta_mgr.update(self._task_id, status="ERROR")
        else:
            self._status = "ERROR"
            if self._task_id:
                self._meta_mgr.update(self._task_id, status="ERROR")

        self._broadcast_progress()

    def _shutdown_executor(self):
        """Shutdown thread pool executor dengan grace period."""
        if self._executor:
            try:
                self._executor.shutdown(wait=True, cancel_futures=True)
            except Exception:
                self._executor.shutdown(wait=True)
        self._executor = None
        self._futures.clear()

    def _broadcast_progress(self):
        """Kirim progress ke callback listener (WebSocket/UI)."""
        if self._on_progress:
            try:
                self._on_progress(self, self._progress_dict())
            except Exception:
                pass

    def _progress_dict(self) -> dict:
        """Build dict progress untuk broadcast."""
        info = {
            "id": self._task_id,
            "url": self.url,
            "filename": self._filename,
            "save_path": self._final_path,
            "status": self._status,
            "speed_kbps": round(self._speed_kbps, 1),
            "percent": round(self.percent, 1),
            "downloaded_size": self._downloaded_size,
            "total_size": self._total_size,
            "eta_seconds": self.eta_seconds,
        }
        if self._task_id:
            meta = self._meta_mgr.load(self._task_id)
            if meta:
                for key in ("graceful_exit", "speed_limit_kbps", "thread_count",
                            "chunks", "created_at", "updated_at"):
                    if key in meta:
                        info.setdefault(key, meta[key])
        info.setdefault("graceful_exit", True)
        info.setdefault("speed_limit_kbps", 0)
        info.setdefault("thread_count", 1)
        info.setdefault("chunks", [])
        info.setdefault("created_at", "")
        info.setdefault("updated_at", "")
        return info
