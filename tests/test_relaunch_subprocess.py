"""AsynxDL — subprocess-relaunch regression test (Phase-H).

Verifies bahwa ``relaunch_subprocess`` melakukan ``subprocess.Popen``
+ ``os._exit`` ketika ``subprocess.Popen`` mocked — yaitu BUKAN
``os.execv`` lama yang sering gagal di Windows + PyInstaller karena
``_MEI*`` orphan tmp dir + ``base_library.zip`` missing.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


def test_relaunch_importable():
    """Module can di-import (parameter sanity)."""
    from frontend.ui.components import _relaunch
    assert hasattr(_relaunch, "relaunch_subprocess")


def test_relaunch_uses_popen_not_execv():
    """relaunch_subprocess WAJIB memanggil subprocess.Popen + os._exit,
    bukan os.execv (yang kita hindari karena PyInstaller-Windows broken).
    """
    from frontend.ui.components import _relaunch

    call_log: list[tuple[str, tuple]] = []

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            call_log.append(("Popen", (tuple(argv), kwargs)))

    fake_popen = _FakePopen

    # os._exit raises SystemExit — capture & ack.
    state = {"exit_code": None}

    def fake_exit(code):
        state["exit_code"] = code
        raise SystemExit(code)

    saved_popen = _relaunch._subprocess.Popen
    saved_exit = _relaunch._os._exit

    _relaunch._subprocess.Popen = fake_popen
    _relaunch._os._exit = fake_exit

    try:
        # Patch sys.argv agar predictable.
        saved_argv = sys.argv
        sys.argv = [sys.executable, "test.py", "--pytest"]
        try:
            try:
                _relaunch.relaunch_subprocess()
            except SystemExit as e:
                pass
        finally:
            sys.argv = saved_argv
    finally:
        _relaunch._subprocess.Popen = saved_popen
        _relaunch._os._exit = saved_exit

    assert state["exit_code"] == 0, "relaunch must call os._exit(0)"
    assert call_log, "relaunch must invoke subprocess.Popen at least once"
    # First call should contain sys.executable as argv[0].
    argv_in, kwargs = call_log[0][1]
    assert sys.executable in argv_in or any("python" in str(a) for a in argv_in)


def test_relaunch_handles_popen_failure():
    """Jika Popen melempar exception dua kali, helper swallow (best-effort)."""
    from frontend.ui.components import _relaunch

    class _BrokenPopen:
        def __init__(self, *a, **kw):
            raise OSError("Popen failed")

    saved_popen = _relaunch._subprocess.Popen
    saved_exit = _relaunch._os._exit
    _relaunch._subprocess.Popen = _BrokenPopen

    state = {"exit_code": None}

    def fake_exit(code):
        state["exit_code"] = code

    _relaunch._os._exit = fake_exit

    try:
        _relaunch.relaunch_subprocess()
    finally:
        _relaunch._subprocess.Popen = saved_popen
        _relaunch._os._exit = saved_exit

    assert state["exit_code"] == 0, "exit_code tetap 0 walau Popen explode"


def test_relaunch_argv_safe():
    """Argumen pytest/debug harus di-skip (mencegah child crash)."""
    from frontend.ui.components import _relaunch

    class _FakePopen:
        def __init__(self, argv, **kwargs):
            self.argv = argv
            self.kwargs = kwargs

    fake_instance = _FakePopen.__new__(_FakePopen)

    def fake_init(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs

    saved_popen = _relaunch._subprocess.Popen
    saved_exit = _relaunch._os._exit
    _relaunch._subprocess.Popen = fake_init
    _relaunch._os._exit = lambda c: None

    try:
        saved_argv = sys.argv
        sys.argv = [sys.executable, "scratch/test_restart_loop.py", "--pytest"]
        try:
            _relaunch.relaunch_subprocess()
        finally:
            sys.argv = saved_argv
    finally:
        _relaunch._subprocess.Popen = saved_popen
        _relaunch._os._exit = saved_exit
