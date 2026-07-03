"""
Test parts_dir helper module.
"""

import os
import tempfile


from backend.core.parts_dir import (
    get_parts_dir,
    purge_all_parts_for,
    purge_all_orphans,
)


def test_get_parts_dir_creates_hidden_dir():
    parts = get_parts_dir()
    assert os.path.isdir(parts)
    # Hidden attribute (0x02) di-set pada Windows; cukup cek ada di disk.
    assert parts.endswith(".parts")


def test_purge_all_parts_for_cleans_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        # Buat {task_id}.part0, .{task_id}.part0, .{task_id}.final
        for name in ("abc.task", ".abc.task123"):
            pass  # biar placeholders
        task_id = "abc-123"
        # Active folder
        active_dir = tmp
        # History folder — berbeda untuk test isolation
        history_dir = os.path.join(tmp, "hidden")
        os.makedirs(history_dir, exist_ok=True)
        # File polos (kompat lama)
        legacy = [
            os.path.join(active_dir, f"{task_id}.part0"),
            os.path.join(active_dir, f"{task_id}.part1"),
            os.path.join(active_dir, f"{task_id}.final"),
        ]
        # File dengan leading dot (konvensi parts_dir)
        hidden = [
            os.path.join(active_dir, f".{task_id}.part0"),
            os.path.join(active_dir, f".{task_id}.final"),
        ]
        for p in legacy + hidden:
            with open(p, "wb") as f:
                f.write(b"x")

        n = purge_all_parts_for(task_id, parts_dir=active_dir)
        assert n >= len(legacy) + len(hidden), (
            f"Got {n} removals; expected at least {len(legacy) + len(hidden)}"
        )
        # Remaining: tidak ada lagi .{task_id}.part* atau {task_id}.part*
        for p in legacy + hidden:
            assert not os.path.exists(p), f"{p} should be removed"


def test_purge_all_orphans_doesnt_touch_recent():
    import time
    with tempfile.TemporaryDirectory() as tmp:
        # Beri satu file baru (max_age_days=14 → tidak dihapus).
        fresh = os.path.join(tmp, ".fresh-id.part0")
        with open(fresh, "wb") as f:
            f.write(b"x")
        # Set mtime ke depan sedikit — dijamin diproses dalam cutoff.
        os.utime(fresh, (time.time(), time.time()))
        n = purge_all_orphans(max_age_days=14, parts_dir=tmp)
        assert n == 0
        assert os.path.exists(fresh)
