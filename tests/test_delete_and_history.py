"""v1.0.2 — Delete UX regression tests (Bug 1 fix).

Three invariants being tested:
1. delete() with task in `_active` juga purge metadata + return meta_removed.
2. delete() dengan remove_from_history=True membersihkan folder completed/.
3. delete() membersihkan part files orphan di disk.

Tidak butuh network atau uvicorn — murni unit test dari state manager.
"""

import json
import os
import shutil
import tempfile

import pytest

from backend.api import state as state_module


@pytest.fixture
def tmp_queue(tmp_path):
    """Setup a temporary queue_dir dengan satu metadata file."""
    queue = tmp_path / "queue"
    queue.mkdir()
    return str(queue)


def _create_meta(queue_dir: str, task_id: str, status: str = "DOWNLOADING") -> str:
    """Bikin metadata file untuk task_id; return full save_path."""
    save_path = os.path.join(tempfile.gettempdir(), f"asynx_test_{task_id}.bin")
    meta = {
        "id": task_id,
        "url": "http://example.com/file.bin",
        "filename": f"file_{task_id}.bin",
        "save_path": save_path,
        "total_size": 102400,
        "downloaded_size": 51200,
        "status": status,
        "graceful_exit": True,
        "thread_count": 4,
        "parts_dir": queue_dir,
        "speed_limit_kbps": 0,
    }
    path = os.path.join(queue_dir, f"{task_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return save_path


def test_delete_active_task_purges_metadata(tmp_queue, monkeypatch):
    """Bug 1 fix: hapus task yang ada di _active juga harus purge metadata file."""
    task_id = "01234567-aaaa-bbbb-cccc-000000000001"
    save_path = _create_meta(tmp_queue, task_id)

    manager = state_module.DownloadManager(queue_dir=tmp_queue)

    # Mock DownloadTask — tidak butuh uvicorn. Pakai __init__ agar tidak
    # tripping Python class-body-scoping (class body LHS mengatakan
    # 'task_id = task_id' yang NameError).
    class _FakeTask:
        def __init__(self, task_id: str):
            self.task_id = task_id
            self.url = "http://example.com/file.bin"
            self.status = "DOWNLOADING"

        def cancel(self):
            pass

        def _progress_dict(self):
            return {
                "id": self.task_id, "status": "DOWNLOADING",
                "filename": "file.bin",
            }

    from backend.core import parts_dir as pd_module
    monkeypatch.setattr(pd_module, "purge_all_parts_for", lambda tid, parts_dir=None: 0)
    monkeypatch.setattr(pd_module, "purge_all_orphans", lambda: 0)

    monkeypatch.setattr(manager, "_active", {task_id: _FakeTask(task_id)})
    result = manager.delete(task_id, delete_parts=False, remove_from_history=False)
    assert result == {"ok": True, "meta_removed": True}
    # Metadata file seharusnya sudah hilang.
    assert not os.path.exists(os.path.join(tmp_queue, f"{task_id}.json"))
    # _active juga sudah dibersihkan.
    assert task_id not in manager._active


def test_delete_with_remove_from_history_clears_completed(tmp_queue):
    """Bug 1 extension: completed task + remove_from_history=True → purged dari history folder."""
    task_id = "01234567-aaaa-bbbb-cccc-000000000002"
    completed_folder = os.path.join(tmp_queue, "completed")
    os.makedirs(completed_folder, exist_ok=True)
    save_path = _create_meta(completed_folder, task_id, status="COMPLETED")
    # Also buat entry di history folder completed/
    history_path = os.path.join(completed_folder, f"{task_id}.json")
    history_meta = dict(json.load(open(history_path)))
    history_meta["status"] = "COMPLETED"
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history_meta, f)

    manager = state_module.DownloadManager(queue_dir=tmp_queue)
    result = manager.delete(task_id, delete_parts=False, remove_from_history=True)
    assert result["ok"]
    # File active metadata + completed/ history masuk cleanup.
    assert not os.path.exists(history_path)


def test_delete_purges_parts_files(tmp_queue):
    """Bug 1: delete() menghapus part files orphan di disk."""
    task_id = "01234567-aaaa-bbbb-cccc-000000000003"
    # Metadata menulis parts_dir = tmp_queue (sama dengan working dir test).
    save_path = _create_meta(tmp_queue, task_id)
    # Buat part0, part1, .final file di tmp_queue (same as parts_dir).
    parts_dir = tmp_queue
    for idx in range(2):
        with open(os.path.join(parts_dir, f"{task_id}.part{idx}"), "wb") as f:
            f.write(b"x" * 1024)
    with open(os.path.join(parts_dir, f"{task_id}.final"), "wb") as f:
        f.write(b"y" * 512)

    # Karena path metadata di-derive dari `tmp_queue`, sama juga dengan
    # parts_dir. patch purge_all_parts_for agar tidak mencari temp global.
    from backend.core import parts_dir as pd_module
    real_purge = pd_module.purge_all_parts_for

    def _local_purge(tid, parts_dir=None):
        # Paksa 使用 parts_dir dari parameter / fallback ke tmp_queue.
        return real_purge(tid, parts_dir=parts_dir if parts_dir else tmp_queue)

    import backend.api.state as state_mod
    original_pd = getattr(state_mod, "__name__", None)

    # Inject langsung import path supaya monkeypatch bekerja.
    import sys
    pd_module_path = "backend.core.parts_dir"
    saved = sys.modules.get(pd_module_path)
    pd_module_mod = sys.modules[pd_module_path]
    pd_module_mod.purge_all_parts_for = staticmethod(_local_purge)
    pd_module_mod.purge_all_orphans = staticmethod(lambda: 0)

    try:
        manager = state_module.DownloadManager(queue_dir=tmp_queue)
        result = manager.delete(task_id, delete_parts=True, remove_from_history=False)
        assert result["ok"]
        # Parts harus hilang.
        assert not os.path.exists(os.path.join(parts_dir, f"{task_id}.part0"))
        assert not os.path.exists(os.path.join(parts_dir, f"{task_id}.part1"))
    finally:
        # Restore
        if saved is not None:
            pd_module_mod.purge_all_parts_for = saved.purge_all_parts_for
            pd_module_mod.purge_all_orphans = saved.purge_all_orphans
