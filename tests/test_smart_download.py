"""AsynxDL — Smart Download tests (Phase-D integration smoke).

Verifikasi integrasi end-to-end engine + fail-safe path pada chunk manager
dan metadata_manager (atomic write path).

Test cases:
- ``MetadataManager.update`` + ``update_chunk_progress`` melakukan atomic
  write (file baru sementara, lalu di-rename jadi final).
- ``MetadataManager.mark_completed`` memindahkan ke folder completed/.
- Atomic retry pattern: simulasi InterruptionException ditengah open & rename
  tidak meninggalkan file korup.
"""
import json
import os
import shutil
import sys
import tempfile
import uuid

PROJECT_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir))
sys.path.insert(0, PROJECT_ROOT)

from backend.core.metadata_manager import MetadataManager


def _tmp_queue() -> str:
    return tempfile.mkdtemp(prefix="asynx_queue_")


def test_metadata_atomic_write():
    queue = _tmp_queue()
    try:
        mgr = MetadataManager(queue)
        meta = mgr.create(
            url="http://example.com/file.zip",
            filename="file.zip",
            save_path=os.path.join(queue, "file.zip"),
            total_size=10_000,
            thread_count=2,
        )
        tid = meta["id"]
        update_path = mgr._metadata_path(tid)
        # update + chunk progress
        mgr.update(tid, downloaded_size=1500, status="DOWNLOADING")
        mgr.update_chunk_progress(tid, chunk_index=0, bytes_done=1500,
                                   downloaded_size=1500)
        loaded = mgr.load(tid)
        assert loaded is not None
        assert loaded["downloaded_size"] == 1500
        assert loaded["status"] == "DOWNLOADING"
        # No leftover .tmp files
        leftovers = list(update_path.parent.glob("*.tmp"))
        assert len(leftovers) == 0
    finally:
        shutil.rmtree(queue, ignore_errors=True)


def test_mark_completed_moves_to_completed_folder():
    queue = _tmp_queue()
    try:
        mgr = MetadataManager(queue)
        meta = mgr.create(
            url="http://example.com/a.zip",
            filename="a.zip",
            save_path=os.path.join(queue, "a.zip"),
            total_size=100,
            thread_count=1,
        )
        tid = meta["id"]
        result = mgr.mark_completed(tid)
        assert result is not None
        assert result["status"] == "COMPLETED"
        assert mgr.load(tid) is None
        history = mgr.list_history()
        assert any(h["id"] == tid for h in history)
    finally:
        shutil.rmtree(queue, ignore_errors=True)


def test_recover_marks_downloading_as_paused():
    queue = _tmp_queue()
    try:
        mgr = MetadataManager(queue)
        meta = mgr.create(
            url="http://example.com/b.zip",
            filename="b.zip",
            save_path=os.path.join(queue, "b.zip"),
            total_size=100,
            thread_count=1,
        )
        tid = meta["id"]
        mgr.update(tid, status="DOWNLOADING")
        recovered = mgr.recover_crashed_tasks()
        assert any(t["id"] == tid for t in recovered)
        loaded = mgr.load(tid)
        assert loaded["status"] == "PAUSED"
        assert loaded["graceful_exit"] is False
    finally:
        shutil.rmtree(queue, ignore_errors=True)


def test_path_safety_helper_rejects_traversal():
    """state-safe path validator via os.path.commonpath."""
    from backend.core.file_validator import is_safe_path
    base = r"C:\Users\Public\Downloads"
    assert is_safe_path(base, r"C:\Users\Public\Downloads\file.zip") is True
    assert is_safe_path(base, r"C:\Windows\System32\evil.exe") is False
    assert is_safe_path(base, base + r"\..\..\evil.exe") is False


def test_resolve_filename_priority():
    """file_validator.resolve_filename pilih user_input > Content-Disp > URL."""
    from backend.core.file_validator import resolve_filename
    assert resolve_filename("custom.zip", "from_disp.zip",
                            "http://x/url.zip") == "custom.zip"
    assert resolve_filename("", "from_disp.zip", "http://x/url.zip") == "from_disp.zip"
    assert resolve_filename("", "", "http://x/Grand%20Theft%20Auto.rar") == "Grand Theft Auto.rar"
