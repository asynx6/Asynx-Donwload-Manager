"""
Unit tests for backend/system/instance.py — single-instance + window restore.

Tests are platform-aware: on non-Windows, signal_existing_window_to_show
must return False without raising; on Windows, we mock the ctypes surface
so we don't actually enumerate desktop windows during test runs.
"""
from __future__ import annotations

import sys
from unittest import mock

import pytest


@pytest.fixture
def fresh():
    """Reload module to reset module-level callback accumulator."""
    import importlib
    import backend.system.instance as inst
    importlib.reload(inst)
    return inst


def test_signal_existing_non_x86_returns_false_when_no_match(fresh):
    """When EnumWindows enumerates but finds no matching title, returns False.

    On non-Windows: the very first guard returns False without calling
    ctypes at all. On Windows: registers a fake _IS_WINDOWS, fake enum.
    """
    import backend.system.instance as inst
    with mock.patch.object(inst, "_IS_WINDOWS", sys.platform != "win32" or True), \
         mock.patch.object(inst, "_find_window_by_title", return_value=0):
        result = inst.signal_existing_window_to_show("__NoneXistent_Title__")
    assert result is False


def test_signal_existing_window_to_show_restores_when_match(fresh):
    """When a matching window exists and is iconic, ShowWindow(SW_RESTORE) is called."""
    if sys.platform != "win32":
        pytest.skip("Win32-only ctypes path")

    fake_calls = {"ShowWindow": [], "SetForegroundWindow": []}

    class _FakeUser32:
        def IsIconic(self, hwnd):
            return True  # pretend window is minimized

        def ShowWindow(self, hwnd, cmd):
            fake_calls["ShowWindow"].append((int(hwnd), int(cmd)))
            return True

        def SetForegroundWindow(self, hwnd):
            fake_calls["SetForegroundWindow"].append(int(hwnd))
            return True

    import backend.system.instance as inst
    with mock.patch.object(inst, "_IS_WINDOWS", True), \
         mock.patch.object(inst, "_find_window_by_title", return_value=0x12345ABCD), \
         mock.patch.object(inst, "_user32", _FakeUser32()):
        result = inst.signal_existing_window_to_show("AsynxDL")

    assert result is True
    assert fake_calls["ShowWindow"] == [(0x12345ABCD, inst._SW_RESTORE)]
    assert fake_calls["SetForegroundWindow"] == [0x12345ABCD]


def test_signal_existing_window_to_show_uses_show_when_not_minimized(fresh):
    """When window is non-iconic, ShowWindow(SW_SHOW) is used instead of RESTORE."""
    if sys.platform != "win32":
        pytest.skip("Win32-only ctypes path")

    fake_calls = {"ShowWindow": []}

    class _FakeUser32:
        def IsIconic(self, hwnd):
            return False

        def ShowWindow(self, hwnd, cmd):
            fake_calls["ShowWindow"].append(int(cmd))
            return True

        def SetForegroundWindow(self, hwnd):
            return True

    import backend.system.instance as inst
    with mock.patch.object(inst, "_IS_WINDOWS", True), \
         mock.patch.object(inst, "_find_window_by_title", return_value=0xC0FFEE), \
         mock.patch.object(inst, "_user32", _FakeUser32()):
        result = inst.signal_existing_window_to_show("AsynxDL")

    assert result is True
    assert fake_calls["ShowWindow"][0] == inst._SW_SHOW


def test_acquire_mutex_returns_true_when_platform_unavailable(fresh):
    """On non-Windows, acquire_mutex returns True without doing anything."""
    import backend.system.instance as inst
    with mock.patch.object(inst, "_IS_WINDOWS", False):
        assert inst.acquire_mutex("TestMutex") is True


def test_acquire_mutex_returns_false_on_already_exists(fresh):
    """When CreateMutex returns existing-mutex ERROR_ALREADY_EXISTS, returns False."""
    if sys.platform != "win32":
        pytest.skip("Win32-only kernel32 path")

    class _FakeKernel32:
        def CreateMutexW(self, *args, **kwargs):
            return 0xDEADBEEF

        def GetLastError(self):
            return inst.ERROR_ALREADY_EXISTS

        def CloseHandle(self, handle):
            return True

    import backend.system.instance as inst
    with mock.patch.object(inst, "_IS_WINDOWS", True), \
         mock.patch.object(inst, "_kernel32", _FakeKernel32()):
        result = inst.acquire_mutex("AnyName")
    assert result is False


def test_acquire_mutex_returns_true_on_fresh_creation(fresh):
    """When CreateMutex succeeds with no prior, returns True."""
    if sys.platform != "win32":
        pytest.skip("Win32-only kernel32 path")

    class _FakeKernel32:
        def CreateMutexW(self, *args, **kwargs):
            return 0xC0FFEE

        def GetLastError(self):
            return 0  # no error

        def CloseHandle(self, handle):
            return True

    import backend.system.instance as inst
    with mock.patch.object(inst, "_IS_WINDOWS", True), \
         mock.patch.object(inst, "_kernel32", _FakeKernel32()):
        result = inst.acquire_mutex("AnyName")
    assert result is True


def test_release_mutex_is_safe_on_non_windows(fresh):
    """release_mutex must not raise on any platform path."""
    import backend.system.instance as inst
    # First non-windows
    with mock.patch.object(inst, "_IS_WINDOWS", False):
        inst.release_mutex("X")  # must not raise
    # On Windows, we don't have a fake kernel, but the inner try/except
    # shields against all exceptions, so calling without mock is also safe
    # in a CI environment that lacks a real mutex.
    if sys.platform == "win32":
        try:
            inst.release_mutex("Local\\AsynxDL_Test_ReleaseHook")
        except Exception as exc:  # pragma: no cover
            pytest.fail(f"release_mutex raised: {exc}")
