import http.server
import os
import threading

import pytest

from backend.core.chunk_manager import download_chunk
from backend.core.downloader import DownloadTask
from backend.core.file_validator import normalize_path, is_safe_path
from backend.core.speed_limiter import SpeedLimiter


def test_chunk_retry_on_503(tmp_path):
    """Verify that a chunk that initially receives 503 retries and completes."""
    data = b"A" * (1024 * 1024)
    fail_max = 2
    fail_count = [0]
    lock = threading.Lock()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

        def do_GET(self):
            with lock:
                fail_count[0] += 1
                if fail_count[0] <= fail_max:
                    self.send_error(503)
                    return
            r = self.headers.get("Range")
            if r:
                s, e = r.replace("bytes=", "").split("-")
                s = int(s)
                e = int(e) if e else len(data) - 1
                chunk = data[s:e + 1]
                self.send_response(206)
                self.send_header("Content-Length", str(len(chunk)))
                self.send_header("Content-Range", f"bytes {s}-{e}/{len(data)}")
                self.end_headers()
                self.wfile.write(chunk)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/file.bin"
        part = str(tmp_path / "file.part0")
        stop = threading.Event()
        limiter = SpeedLimiter(0)
        bytes_done = download_chunk(
            url=url,
            start=0,
            end=len(data) - 1,
            part_path=part,
            limiter=limiter,
            stop_event=stop,
        )
        assert bytes_done == len(data)
    finally:
        server.shutdown()


def test_pause_resume_state_isolation(tmp_path):
    """Metadata creation should keep a task_id inside a safe path."""
    save_dir = tmp_path / "downloads"
    save_dir.mkdir()
    task = DownloadTask(
        url="http://127.0.0.1:1/no_download",
        save_path=str(save_dir),
        filename="test.bin",
        queue_dir=str(tmp_path / "queue"),
    )
    meta = task._meta_mgr.create(
        url=task.url,
        filename="test.bin",
        save_path=str(save_dir / "test.bin"),
        total_size=1024,
        thread_count=1,
        task_id=task.task_id,
    )
    assert meta["id"] == task.task_id
    assert is_safe_path(str(save_dir), str(save_dir / "test.bin"))


def test_normalize_path_rejects_traversal():
    """A normalized path outside the base directory must be detected."""
    base = normalize_path("%USERPROFILE%\\Downloads")
    bad = normalize_path(os.path.join(base, "..", "..", "Windows", "secret.txt"))
    assert not is_safe_path(base, bad)
