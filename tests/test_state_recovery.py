"""
Test v1.0.1: state recovery & history persistence.

Memverifikasi:
- mark_completed memindahkan meta ke folder completed/.
- remove_from_history menghapus meta dari completed/.
- delete pada task di completed/ dengan remove_from_history=True berhasil.
"""

import os
import tempfile


from backend.core.metadata_manager import MetadataManager


# UUID-format task_id karena implementasi _is_safe_task_id hanya
# menerima hex + hyphens.
_UUID_A = "aabbccdd-1111-2222-3333-444455556666"
_UUID_B = "eeff1122-3333-4444-5555-6677889900aa"
_UUID_C = "00112233-4455-6677-8899-aabbccddeeff"


def test_mark_completed_moves_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = MetadataManager(queue_dir=tmp)
        meta = mgr.create(
            url="http://example.com/file.zip",
            filename="file.zip",
            save_path=os.path.join(tmp, "file.zip"),
            total_size=10 * 1024 * 1024,
            thread_count=2,
            task_id=_UUID_A,
        )
        tid = meta["id"]
        assert mgr.load(tid)["status"] == "PENDING"
        out = mgr.mark_completed(tid)
        assert out is not None
        assert out["status"] == "COMPLETED"
        assert "completed_at" in out
        assert not os.path.exists(os.path.join(tmp, f"{tid}.json"))
        completed = os.path.join(tmp, "completed", f"{tid}.json")
        assert os.path.exists(completed), \
            f"expected {completed} after mark_completed"


def test_remove_from_history_cleans_completed_folder():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = MetadataManager(queue_dir=tmp)
        meta = mgr.create(
            url="http://example.com/file.zip",
            filename="file.zip",
            save_path=os.path.join(tmp, "file.zip"),
            total_size=10 * 1024 * 1024,
            thread_count=2,
            task_id=_UUID_B,
        )
        tid = meta["id"]
        mgr.mark_completed(tid)
        completed = os.path.join(tmp, "completed", f"{tid}.json")
        assert os.path.exists(completed)
        removed = mgr.remove_from_history(tid)
        assert removed is True
        assert not os.path.exists(completed)


def test_list_history_returns_completed_sorted():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = MetadataManager(queue_dir=tmp)
        ids = []
        for i in range(3):
            tid = f"aabbccdd{i:01d}{'0' * 7}-1111-2222-3333-444455556666"
            meta = mgr.create(
                url=f"http://example.com/file{i}.zip",
                filename=f"file{i}.zip",
                save_path=os.path.join(tmp, f"file{i}.zip"),
                total_size=1024,
                thread_count=1,
                task_id=tid,
            )
            ids.append(meta["id"])
            mgr.mark_completed(meta["id"])
        history = mgr.list_history()
        assert len(history) == 3
        assert all(h["status"] == "COMPLETED" for h in history)


def test_list_all_with_history_merges_active_and_completed():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = MetadataManager(queue_dir=tmp)
        # Active
        active_meta = mgr.create(
            url="http://example.com/a.zip",
            filename="a.zip",
            save_path=os.path.join(tmp, "a.zip"),
            total_size=1024,
            thread_count=1,
            task_id=_UUID_C,
        )
        # Completed
        completed_id1 = mgr.create(
            url="http://example.com/b.zip", filename="b.zip",
            save_path=os.path.join(tmp, "b.zip"),
            total_size=1024, thread_count=1,
            task_id="aa00bb00-cc00-dd00-ee00-ff00aa00bb00",
        )["id"]
        completed_id2 = mgr.create(
            url="http://example.com/c.zip", filename="c.zip",
            save_path=os.path.join(tmp, "c.zip"),
            total_size=1024, thread_count=1,
            task_id="00110011-2233-4455-6677-8899aabbccdd",
        )["id"]
        mgr.mark_completed(completed_id1)
        mgr.mark_completed(completed_id2)

        all_items = mgr.list_all_with_history()
        ids = {item["id"] for item in all_items}
        assert active_meta["id"] in ids
        assert completed_id1 in ids
        assert completed_id2 in ids
