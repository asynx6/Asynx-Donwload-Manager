"""AsynxDL — ``_MEI*`` cleanup runtime hook regression test (Phase-H).

Verifies fungsi ``_wipe_stale_meipass`` di runtime hook
``runtime_hook_meipass.py`` menghapus orphan ``_MEI*`` dirs dan
MENYISAKAN ``sys._MEIPASS`` current + dirs yang baru di-create
(< 2 detik).
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time

import pytest


def _load_hook_module():
    """Import ``build/runtime_hook_meipass.py`` secara manual supaya
    ``main()`` otomatis-terpanggil tidak ikut."""
    spec = importlib.util.spec_from_file_location(
        "runtime_hook_meipass",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "build", "runtime_hook_meipass.py",
        ),
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Prevent main() from running auto-call (file-level).
    # Module has ``main()`` explicitly but def file calls ``main()`` at end.
    # We exec into a temp module name & intercept or skip the ``main()`` call.
    sys.modules["runtime_hook_meipass"] = mod
    return mod, spec.loader


def test_wipe_removes_orphan_dirs():
    from build import runtime_hook_meipass as rht

    with tempfile.TemporaryDirectory() as tmp:
        # Make 3 orphans with old mtime.
        for i in range(3):
            d = os.path.join(tmp, f"_MEI{i:08d}")
            os.makedirs(d)
            # Force old mtime.
            t = time.time() - 60
            os.utime(d, (t, t))
        # Make 1 fresh(current process) — DON'T delete.
        fresh = os.path.join(tmp, "_MEIfresh")
        os.makedirs(fresh)
        # Keep its real mtime (recent).

        saved_meipass = getattr(sys, "_MEIPASS", None)
        sys._MEIPASS = fresh  # so it's treated as "self"
        try:
            # Only delete orphans (older than 2s); NEW is younger than 2s.
            # Difference: orphans set mtime 60s ago (>2s grace); fresh just now.
            removed = rht._wipe_stale_meipass(tmp)
        finally:
            if saved_meipass is None:
                try:
                    del sys._MEIPASS
                except AttributeError:
                    pass
            else:
                sys._MEIPASS = saved_meipass

        # 3 orphans should be removed.
        assert removed == 3
        assert not os.path.exists(os.path.join(tmp, "_MEI00000000"))
        assert not os.path.exists(os.path.join(tmp, "_MEI00000001"))
        assert not os.path.exists(os.path.join(tmp, "_MEI00000002"))
        # Fresh self MUST be alive.
        assert os.path.isdir(fresh)


def test_wipe_skips_recent_meipass():
    """Dirs yang di-create baru (mtime < 2 detik) BUKAN orphan, skip."""
    from build import runtime_hook_meipass as rht

    with tempfile.TemporaryDirectory() as tmp:
        # 1 orphan (60s old)
        old = os.path.join(tmp, "_MEIold0000")
        os.makedirs(old)
        os.utime(old, (time.time() - 60, time.time() - 60))
        # 1 fresh (just created by "bootloader" hypothetically)
        recent = os.path.join(tmp, "_MEIrecent01")
        os.makedirs(recent)
        os.utime(recent, (time.time(), time.time()))

        saved = getattr(sys, "_MEIPASS", None)
        sys._MEIPASS = None  # so rht does NOT protect any dir as "self"
        try:
            removed = rht._wipe_stale_meipass(tmp)
        finally:
            if saved is None:
                try:
                    del sys._MEIPASS
                except AttributeError:
                    pass
            else:
                sys._MEIPASS = saved

        # Orphan (old) should be removed (mtime > 2s ago).
        assert not os.path.exists(old)
        # Recent should be untouched (< 2s grace window).
        assert os.path.isdir(recent)
        assert removed == 1


def test_wipe_handles_no_temp_dir():
    from build import runtime_hook_meipass as rht
    # Junk path -- not a dir.
    assert rht._wipe_stale_meipass("/this/path/does/not/exist") == 0


def test_hook_noop_in_dev_mode():
    """Runtime hook main() harus no-op kalau sys.frozen=False
    (i.e., plain Python script — dev mode)."""
    from build import runtime_hook_meipass as rht

    saved_frozen = getattr(sys, "frozen", False)
    sys.frozen = False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "_MEI99999999")
            os.makedirs(sub)
            os.utime(sub, (time.time() - 600, time.time() - 600))
            # main() should not touch /dev/null/anything.
            rht.main()
            assert os.path.isdir(sub)  # untouched
    finally:
        sys.frozen = saved_frozen


def test_wipe_idempotent():
    """Calling twice is safe (no Exception, returns 0 on second call)."""
    from build import runtime_hook_meipass as rht

    with tempfile.TemporaryDirectory() as tmp:
        old = os.path.join(tmp, "_MEIidemp1")
        os.makedirs(old)
        os.utime(old, (time.time() - 60, time.time() - 60))

        saved = getattr(sys, "_MEIPASS", None)
        sys._MEIPASS = None
        try:
            first = rht._wipe_stale_meipass(tmp)
            second = rht._wipe_stale_meipass(tmp)
        finally:
            if saved is None:
                try:
                    del sys._MEIPASS
                except AttributeError:
                    pass
            else:
                sys._MEIPASS = saved

        assert first == 1
        assert second == 0  # nothing left to remove
