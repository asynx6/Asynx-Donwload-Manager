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
from .parts_dir import get_parts_dir as _get_parts_dir
from .preallocator import (
    preallocate_file,
    preallocate_parts,
    reserve_space,
)
from .mirror_selector import MirrorSelector
from .bandwidth_probe import BandwidthProbe
from .adaptive_thread_controller import AdaptiveThreadController
from .geo_chunk_router import GeoChunkRouter
from .work_stealer import WorkStealer
from .range_fingerprint import RangeFingerprint, verify_range_support
from .resume_integrity import ResumeIntegrityValidator
from .http2_session import Http2Session


# AsynxDL application cache directory under %LOCALAPPDATA%:
# delegated to backend.core.parts_dir (M6: single source of truth).


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
            max_threads: Maksimum thread untuk chunked download (1-16).
            queue_dir: Path ke folder data/queue untuk metadata.
            on_progress: Callback(taskself, dict_progress) dipanggil saat progress update.
        """
        self.url = url
        self._max_threads = min(max(max_threads, 1), 16)
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
        self._fallback_urls: list[str] = []
        self._mirror_selector: MirrorSelector | None = None
        self._bandwidth_probe: BandwidthProbe | None = None
        self._adaptive_controller: AdaptiveThreadController | None = None
        self._mirror_results: list[dict] = []
        # BUG #9: lock for _chunks / _futures shared by chunk threads & adaptive spawn
        self._chunks_lock = threading.Lock()
        # INEFFICIENT #17: cache for metadata fields in _progress_dict
        self._meta_cache: dict = {}
        self._meta_cache_time: float = 0.0
        self._completed_count_cache: int = 0
        self._completed_count_cache_time: float = 0.0

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
        self._session = Http2Session(prefer_http2=True)

        try:
            # 1. Probe URL
            info = probe_url(self.url)
            self._total_size = info["content_length"]
            supports_range = info["supports_range"]
            url_filename = info["filename"]

            # 1b. Range fingerprint: verify the server actually honors Range requests.
            try:
                fp = RangeFingerprint(self.url)
                fp_result = fp.probe()
                if fp_result.get("range_unreliable") or fp_result.get("tamper_detected"):
                    print(f"[DownloadTask] range unreliable/tamper detected for {self.url}; fallback single-thread")
                    supports_range = False
                else:
                    supports_range = fp_result.get("supports_range", supports_range)
            except Exception as exc:
                print(f"[DownloadTask] range fingerprint failed: {exc}")

            # 2. Resolve filename dan path — pakai resolve_filename() deterministik
            filename = resolve_filename(
                self._requested_filename, url_filename, self.url
            )
            filename = sanitize_filename(filename)
            save_folder = self._requested_save_path
            os.makedirs(save_folder, exist_ok=True)
            filename = resolve_duplicate_name(save_folder, filename)
            final_path = normalize_path(os.path.join(save_folder, filename))
            if not is_safe_path(save_folder, final_path):
                self._status = "ERROR"
                self._broadcast_progress()
                return
            self._filename = filename
            self._final_path = final_path

            # Unknown content length: fall back to single-thread streaming.
            unknown_length = self._total_size <= 0
            if unknown_length:
                supports_range = False
                thread_count = 1
            else:
                # 3. Cek disk space (only when size is known)
                if not check_disk_space(final_path, self._total_size):
                    self._status = "ERROR"
                    self._broadcast_progress()
                    return

                # 4. Hitung chunk count secara dinamis berdasarkan ukuran file.
                if not supports_range:
                    thread_count = 1
                else:
                    from .chunk_calculator import auto_chunks_for_size
                    thread_count = auto_chunks_for_size(
                        self._total_size,
                        cap=self._max_threads,
                    )

            parts_dir = _get_parts_dir()

            # FIX: Tulis metadata SEGERA setelah probe — supaya UI langsung
            # tahu total_size dan filename, tanpa nunggu mirror selector
            # + intelligence engine yang bisa makan 5-10 detik.
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
                expected_sha256=info.get("expected_sha256"),
                expected_md5=info.get("expected_md5"),
                etag=info.get("etag"),
                fallback_urls=self._fallback_urls,
            )
            self._broadcast_progress()

            if not unknown_length:
                # 4b. Pre-allocate final file (best-effort)
                try:
                    if not reserve_space(final_path, self._total_size):
                        self._status = "ERROR"
                        self._broadcast_progress()
                        return
                    preallocate_file(final_path, self._total_size, zero_fill=False)
                except Exception:
                    pass

                # 4c + Phase D: Mirror selection + Intelligence — JALAN DI
                # BACKGROUND supaya download bisa mulai segera.
                def _bg_optimize():
                    nonlocal thread_count
                    try:
                        selector = MirrorSelector(self.url, expected_length=self._total_size)
                        best_url, fallbacks = selector.select()
                        self._mirror_results = selector.results()
                        if best_url and best_url != self.url:
                            print(f"[DownloadTask] mirror switch: {self.url} -> {best_url}")
                            self.url = best_url
                        self._fallback_urls = fallbacks[:5]
                    except Exception as exc:
                        print(f"[DownloadTask] mirror selection failed: {exc}")
                    try:
                        from .intelligence import decision_for, Policy
                        import shutil
                        free_disk = shutil.disk_usage(
                            os.path.splitdrive(final_path)[0] or os.path.sep
                        ).free
                        policy = Policy(
                            total_size=self._total_size,
                            max_threads=self._max_threads,
                            supports_range=supports_range,
                            speed_limit_kbps=self._limiter.limit_kbps,
                            is_resume=False,
                            free_disk_bytes=free_disk,
                            filename=filename,
                            url=self.url,
                        )
                        plan = decision_for(policy)
                        if plan.actual_threads and plan.actual_threads != thread_count:
                            thread_count = plan.actual_threads
                        if plan.mirror_url and plan.mirror_url != self.url:
                            try:
                                self.url = plan.mirror_url
                            except Exception:
                                pass
                        if plan.verify_after_merge:
                            self._meta_mgr.update(self._task_id, verify_after_merge=True)
                    except Exception:
                        pass
                threading.Thread(target=_bg_optimize, daemon=True, name="optimize").start()

            # FIX: JANGAN pre-allocate .part files!
            # Pre-allocate sparse file bikin os.path.getsize() report
            # ukuran penuh padahal belum ada data → _update_downloaded_size
            # salah hitung → speed=Infinity, progress=100% palsu.
            # Part file akan dibuat otomatis oleh download_chunk saat
            # pertama kali write dengan mode="wb".

            self._broadcast_progress()

            # 6. Download chunks
            self._download_chunks(metadata, supports_range)

            # 7. Merge jika semua chunk selesai dan tidak di-pause
            if self._status == "DOWNLOADING":
                # For unknown length, total size is now the size of the downloaded part.
                if unknown_length:
                    part_path = os.path.join(parts_dir, f"{self._task_id}.part0")
                    try:
                        self._total_size = os.path.getsize(part_path)
                    except OSError:
                        self._total_size = 0
                    self._meta_mgr.update(self._task_id, total_size=self._total_size)
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
            self._stop_intelligence()

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
        self._stop_intelligence()
        self._broadcast_progress()

    def resume(self):
        """Resume download yang di-pause.

        - Load metadata dari disk (dapatkan byte offset per chunk).
        - Restart thread pool dengan Range yang sudah di-offset.
        - Jika task ERROR dan metadata tidak valid (total_size=0 atau chunk
          placeholder), fallback ke start() untuk re-probe dari awal.
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

        # FIX Bug #3: Jika task ERROR dan metadata tidak valid (total_size=0
        # atau chunk masih placeholder start=0/end=0), re-probe dari awal.
        chunks = metadata.get("chunks", [])
        has_valid_chunks = any(
            c.get("end", 0) > 0 for c in chunks
        )
        if self._status == "ERROR" and (metadata.get("total_size", 0) <= 0 or not has_valid_chunks):
            print(f"[DownloadTask] resume from ERROR with invalid metadata, re-starting")
            self._stop_event.clear()
            self._status = "PENDING"
            self._downloaded_size = 0
            self._total_size = 0
            self._speed_kbps = 0.0
            self.start()
            return

        # Refresh state dari metadata
        self._total_size = metadata.get("total_size", 0)
        self._downloaded_size = metadata.get("downloaded_size", 0)
        self._filename = metadata.get("filename", self._filename)
        self._final_path = metadata.get("save_path", self._final_path)
        self._fallback_urls = metadata.get("fallback_urls", [])

        # Phase 6: resume integrity validation — repair inconsistent chunks.
        try:
            parts_dir = metadata.get("parts_dir", _get_parts_dir())
            validator = ResumeIntegrityValidator(self._task_id, parts_dir, metadata)
            result = validator.validate()
            if result.get("fixed_chunks", 0) > 0:
                print(f"[DownloadTask] resume integrity: fixed {result['fixed_chunks']} chunks")
                metadata = self._meta_mgr.load(self._task_id) or metadata
                metadata["chunks"] = result["chunks"]
                self._meta_mgr.update(self._task_id, chunks=result["chunks"], state_hash=result["state_hash"])
        except Exception as exc:
            print(f"[DownloadTask] resume integrity validation failed: {exc}")

        # Jika ada fallback URLs, coba mirror selection ulang untuk resume.
        if self._fallback_urls:
            try:
                selector = MirrorSelector(self.url, expected_length=self._total_size)
                best_url, fallbacks = selector.select()
                self._mirror_results = selector.results()
                if best_url and best_url != self.url:
                    self.url = best_url
                self._fallback_urls = (fallbacks + self._fallback_urls)[:5]
            except Exception as exc:
                print(f"[DownloadTask] resume mirror selection failed: {exc}")

        self._stop_event.clear()
        self._session = Http2Session(prefer_http2=True)
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
            self._stop_intelligence()

    def set_speed_limit(self, kbps: int):
        """Update speed limit saat runtime (digunakan oleh global scheduler)."""
        if self._limiter:
            self._limiter.limit_kbps = max(0, kbps)
            if self._task_id:
                self._meta_mgr.update(self._task_id, speed_limit_kbps=self._limiter.limit_kbps)

    def cancel(self):
        """Batalkan download dan bersihkan file chunk terkait.

        Status ``CANCELLED`` tetap disimpan ke metadata (folder active)
        supaya history ``data/queue/completed/`` atau active ``list_all``
        masih bisa menampilkannya dan user melihat jejak aksi di UI.
        Metadata active folder JANGAN dihapus di sini—hanya chunk file
        ``.part*`` dan ``.final`` yang dibersihkan.
        """
        self._stop_event.set()
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
            # Hapus file final tujuan jika belum selesai (partial file).
            try:
                if self._final_path and os.path.exists(self._final_path):
                    os.remove(self._final_path)
            except Exception:
                pass

        # Audit-fix M1: broadcast unconditionally supaya WebSocket UI
        # menerima status=CANCELLED terlepas dari old_status.
        self._stop_intelligence()
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

        parts_dir = metadata.get("parts_dir", _get_parts_dir())
        final_path = metadata["save_path"]

        # Phase 2: start bandwidth probe and adaptive controller
        self._chunks = chunks
        self._parts_dir = parts_dir
        try:
            self._bandwidth_probe = BandwidthProbe(
                on_throttle=self._on_throttle_detected
            )
            self._bandwidth_probe.start()
            self._adaptive_controller = AdaptiveThreadController(
                task_id=self._task_id,
                url=self.url,
                parts_dir=parts_dir,
                limiter=self._limiter,
                stop_event=self._stop_event,
                session=self._session,
                max_threads=self._max_threads,
                on_change=self._on_thread_count_change,
            )
            self._adaptive_controller.start(thread_count)
        except Exception as exc:
            print(f"[DownloadTask] intelligence start failed: {exc}")

        # Phase 3: geo-routing untuk chunk jika ada fallback URLs
        router: GeoChunkRouter | None = None
        if self._fallback_urls and supports_range:
            try:
                router = GeoChunkRouter(self.url, self._fallback_urls, expected_length=self._total_size)
                router.probe()
                self._fallback_urls = router.urls()
            except Exception as exc:
                print(f"[DownloadTask] geo-routing probe failed: {exc}")

        with ThreadPoolExecutor(max_workers=max(thread_count, self._max_threads)) as executor:
            self._executor = executor
            self._futures = []

            for chunk in chunks:
                idx = chunk["index"]
                start = chunk["start"] + chunk.get("bytes_done", 0)
                end = chunk["end"]
                if start >= end:
                    # Chunk sudah selesai
                    continue

                chunk_url = router.url_for_chunk(idx, len(chunks)) if router else self.url
                part_path = os.path.join(parts_dir, f"{self._task_id}.part{idx}")
                chunk["part_path"] = part_path
                future = executor.submit(
                    download_chunk,
                    url=chunk_url,
                    start=start,
                    end=end,
                    part_path=part_path,
                    limiter=self._limiter,
                    stop_event=self._stop_event,
                    session=self._session,
                )
                with self._chunks_lock:
                    self._futures.append((future, chunk))

            # Progress flush timer: throttle metadata writes to disk
            self._last_progress_time = time.monotonic()
            self._last_downloaded = self._downloaded_size
            self._last_meta_flush = 0.0

            # Monitor futures sampai semua selesai. as_completed timeout yang
            # pendek digunakan untuk memberi kesempatan progress update; kita
            # abaikan TimeoutError karena download mungkin masih berjalan.
            with self._chunks_lock:
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

                # Phase 2: record failures for adaptive controller
                for future in done:
                    if future.done() and future.exception() is not None:
                        try:
                            if self._adaptive_controller:
                                self._adaptive_controller.record_failure()
                        except Exception:
                            pass
                        print(f"[DownloadTask] chunk failed: {future.exception()}")

                # Phase 3: work-stealing — jika ada thread idle, curi sub-range chunk lambat
                if router and done and not self._stop_event.is_set():
                    try:
                        with self._chunks_lock:
                            active_futures = list(self._futures)
                        stealer = WorkStealer(
                            task_id=self._task_id,
                            base_url=self.url,
                            parts_dir=parts_dir,
                            limiter=self._limiter,
                            stop_event=self._stop_event,
                            session=self._session,
                            chunks=chunks,
                            active_futures=active_futures,
                            executor=executor,
                        )
                        stealer.maybe_steal()
                    except Exception as exc:
                        print(f"[DownloadTask] work-steal attempt failed: {exc}")

                if self._stop_event.is_set():
                    break

                # Hitung total downloaded dari file .part di disk
                self._update_downloaded_size_from_parts(chunks, parts_dir)
                self._compute_speed()
                self._throttled_meta_flush()

            # Tunggu sisa future yang belum selesai (atau cancel)
            with self._chunks_lock:
                futures_snapshot = list(self._futures)
            for future, chunk in futures_snapshot:
                if future.done():
                    continue
                try:
                    future.result(timeout=0)
                except Exception:
                    pass

            self._executor = None
            with self._chunks_lock:
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
            # Phase 2: feed intelligence modules
            try:
                if self._bandwidth_probe:
                    self._bandwidth_probe.feed(self._speed_kbps)
            except Exception:
                pass
            try:
                if self._adaptive_controller:
                    self._adaptive_controller.feed_speed(self._speed_kbps)
            except Exception:
                pass
            self._broadcast_progress()

    def _merge_and_finalize(self, metadata: dict):
        """Gabungkan semua .part, verifikasi, dan pindahkan ke tujuan akhir."""
        if self._stop_event.is_set():
            return

        chunks = metadata.get("chunks", [])
        parts_dir = metadata.get("parts_dir", _get_parts_dir())
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
            expected_sha256=metadata.get("expected_sha256"),
            expected_md5=metadata.get("expected_md5"),
            etag=metadata.get("etag"),
        )

        if success:
            try:
                os.replace(temp_output, final_path)
                self._status = "COMPLETED"
                # FIX: pastikan downloaded_size == total_size saat selesai
                # supaya progress bar dan teks persen = 100%, bukan 97.6%.
                self._downloaded_size = self._total_size
                self._speed_kbps = 0.0
                
                # Antivirus scan
                try:
                    from .antivirus import scan_file
                    scan_res = scan_file(final_path)
                    print(f"[DownloadTask] Antivirus scan result: {scan_res}")
                    self._meta_mgr.update(
                        self._task_id,
                        antivirus_status=scan_res.get("status"),
                        antivirus_message=scan_res.get("message")
                    )
                except Exception as av_exc:
                    print(f"[DownloadTask] Antivirus scan failed: {av_exc}")

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
            now = time.monotonic()
            meta = self._meta_cache if now - self._meta_cache_time < 5.0 else None
            if meta is None:
                meta = self._meta_mgr.load(self._task_id)
                self._meta_cache = meta or {}
                self._meta_cache_time = now
            if meta:
                for key in ("graceful_exit", "speed_limit_kbps", "thread_count",
                            "chunks", "created_at", "updated_at"):
                    if key in meta:
                        info.setdefault(key, meta[key])
        info.setdefault("graceful_exit", True)
        info.setdefault("speed_limit_kbps", 0)
        info.setdefault("thread_count", 1)
        info.setdefault("chunks", [])
        info.setdefault("fallback_urls", self._fallback_urls)
        info.setdefault("mirror_results", self._mirror_results)
        info.setdefault("created_at", "")
        info.setdefault("updated_at", "")
        return info

    def _stop_intelligence(self):
        """Stop bandwidth probe and adaptive controller threads."""
        try:
            if self._bandwidth_probe:
                self._bandwidth_probe.stop()
        except Exception:
            pass
        try:
            if self._adaptive_controller:
                self._adaptive_controller.stop()
        except Exception:
            pass

    def _on_throttle_detected(self, current_speed: float, median_speed: float):
        """Callback saat bandwidth probe mendeteksi throttle."""
        print(
            f"[DownloadTask] throttle detected task={self._task_id}: "
            f"current={current_speed:.1f} KB/s median={median_speed:.1f} KB/s"
        )
        # Prefer fallback mirror if available; otherwise TurboRouter will rotate UA next chunk.
        if self._fallback_urls and self._fallback_urls[0] != self.url:
            new_url = self._fallback_urls.pop(0)
            print(f"[DownloadTask] switching to fallback mirror: {new_url}")
            self.url = new_url
            if self._task_id:
                self._meta_mgr.update(self._task_id, url=new_url)
        elif self._task_id:
            self._meta_mgr.update(self._task_id, throttle_detected=True)

    def _on_thread_count_change(self, new_count: int):
        """Callback saat adaptive controller memutuskan thread baru."""
        if not self._task_id or new_count <= 0:
            return
        print(f"[DownloadTask] adaptive thread count task={self._task_id}: {new_count}")
        self._meta_mgr.update(self._task_id, thread_count=new_count)
        # Actually spawn an extra chunk thread if the pool is still running.
        try:
            if self._executor and self._chunks and not self._stop_event.is_set():
                with self._chunks_lock:
                    self._spawn_extra_chunk(self._chunks, self._executor)
        except Exception as exc:
            print(f"[DownloadTask] spawn extra chunk failed: {exc}")

    def _spawn_extra_chunk(self, chunks: list, executor: ThreadPoolExecutor) -> bool:
        """Split the slowest remaining chunk and submit a new future for the second half."""
        slowest = None
        max_remaining = 0
        for chunk in chunks:
            start = chunk["start"] + chunk.get("bytes_done", 0)
            end = chunk["end"]
            if start >= end:
                continue
            remaining = end - start + 1
            if remaining > max_remaining:
                max_remaining = remaining
                slowest = chunk

        if slowest is None or max_remaining < 2 * 1024 * 1024:
            return False

        idx = slowest["index"]
        start = slowest["start"] + slowest.get("bytes_done", 0)
        end = slowest["end"]
        mid = start + (end - start) // 2
        if mid >= end - 1:
            return False

        slowest["end"] = mid
        part_path = os.path.join(
            self._parts_dir or _get_parts_dir(),
            f"{self._task_id}.part{idx}_split{int(time.time() * 1000)}"
        )
        new_chunk = {
            "index": idx,
            "start": mid + 1,
            "end": end,
            "bytes_done": 0,
            "part_path": part_path,
        }
        chunks.append(new_chunk)

        future = executor.submit(
            download_chunk,
            url=self.url,
            start=new_chunk["start"],
            end=new_chunk["end"],
            part_path=part_path,
            limiter=self._limiter,
            stop_event=self._stop_event,
            session=self._session,
        )
        self._futures.append((future, new_chunk))
        print(f"[DownloadTask] spawned extra chunk: {new_chunk['start']}-{new_chunk['end']}")
        return True
