"""
AsynxDL — Single-Instance Window Restore (Win32 inter-process)

Used by second-launch handler in backend/main.py: when user double-clicks
the app / shortcut while the first instance is alive (e.g. hidden in tray),
we use Win32 API to FindWindowW → ShowWindow(SW_RESTORE) → SetForegroundWindow
the existing window.

NOT a replacement for the port-probe single-instance check in main.py.
That probe decides "is anyone listening on 127.0.0.1:58296?". This module
is the operational handler: "an existing instance is running — please
restore its visible window so the new launch is a no-op rather than dead."

Also exposes a Mutex-based fast single-instance check that can be used
independently if a developer wants belt-and-suspenders defense before
the (slightly slower) port-probe.

Non-Windows platforms (Linux, macOS) degrade to no-op returns. AsynxDL is
a Windows-only desktop application per plan.md.
"""
from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# Win32 ctypes setup (only loaded on Windows)
# ---------------------------------------------------------------------------

_IS_WINDOWS: bool = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    # Type-correct arg/return signatures for the calls we make.
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int

    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int

    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.ShowWindow.restype = wintypes.BOOL

    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.SetForegroundWindow.restype = wintypes.BOOL

    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.IsIconic.restype = wintypes.BOOL

    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL

    _user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
    ]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    _EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _user32.EnumWindows.argtypes = [_EnumWindowsProc, wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL

    _kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.CreateMutexW.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.GetLastError.argtypes = []
    _kernel32.GetLastError.restype = wintypes.DWORD


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

_SW_RESTORE = 9      # SW_RESTORE — un-minimize + restore previous size/pos
_SW_SHOW = 5         # SW_SHOW — activate + show window

ERROR_ALREADY_EXISTS = 183

DEFAULT_WINDOW_TITLE = "AsynxDL"

DEFAULT_MUTEX_NAME = "Local\\AsynxDL_Singleton_Mutex"


# ---------------------------------------------------------------------------
# Module-level state for EnumWindows callback (Win32 requires a callable)
# ---------------------------------------------------------------------------

if _IS_WINDOWS:
    _found_hwnds: list[int] = []
else:
    _found_hwnds: list[int] = []  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_window_by_title(title_substr: str) -> int:
    """Find first top-level window whose title contains *title_substr* (case-insensitive).

    Returns the window handle (HWND as int) or 0 if no match found.
    """
    if not _IS_WINDOWS:
        return 0

    # Reset module-level accumulator.
    _found_hwnds.clear()
    needle = title_substr.casefold()

    def _enum_proc(hwnd: int, _lparam: int) -> bool:  # noqa: ANN001
        try:
            length = _user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True  # keep enumerating
            buf = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, buf, length + 1)
            if needle in buf.value.casefold():
                _found_hwnds.append(int(hwnd))
        except Exception:
            pass
        return True  # continue enumeration

    try:
        _user32.EnumWindows(_EnumWindowsProc(_enum_proc), 0)
    except Exception:
        return 0
    return _found_hwnds[0] if _found_hwnds else 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def signal_existing_window_to_show(title_substr: str = DEFAULT_WINDOW_TITLE) -> bool:
    """Bring an existing AsynxDL window to the foreground via Win32.

    Returns True if a matching window was found and restored+foregrounded;
    False on non-Windows or when no window matched the title.
    """
    if not _IS_WINDOWS:
        return False

    hwnd = _find_window_by_title(title_substr)
    if not hwnd:
        return False

    try:
        if _user32.IsIconic(hwnd):
            # Window is minimized → SW_RESTORE will un-minimize + restore size
            show_cmd = _SW_RESTORE
        else:
            # Already visible → SW_SHOW brings it to top in same state
            show_cmd = _SW_SHOW
        _user32.ShowWindow(hwnd, show_cmd)
    except Exception:
        pass
    try:
        _user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    return True


def acquire_mutex(name: str = DEFAULT_MUTEX_NAME) -> bool:
    """Attempt to acquire a named Win32 Mutex.

    Returns:
        True — caller acquired the mutex; this is the first instance.
        False — another instance already holds it; caller should bail.

    On non-Windows: returns True (assume ok, port-probe is the real check).
    """
    if not _IS_WINDOWS:
        return True

    try:
        handle = _kernel32.CreateMutexW(None, False, name)
    except Exception:
        return True  # be permissive on unexpected failure
    if not handle:
        return True
    last_error = _kernel32.GetLastError()
    if last_error == ERROR_ALREADY_EXISTS:
        try:
            _kernel32.CloseHandle(handle)
        except Exception:
            pass
        return False
    # On graceful process termination the mutex is auto-released by the
    # kernel; explicit CloseHandle is therefore optional.
    return True


def release_mutex(name: str = DEFAULT_MUTEX_NAME) -> None:
    """Release the named mutex (best-effort; safe to call multiple times).

    Provided for symmetry with acquire_mutex. Currently unused by main.py
    since the OS auto-releases the mutex on process exit, but exposed for
    explicit lifecycle control in the future.
    """
    if not _IS_WINDOWS:
        return
    # CreateMutex returns an existing handle if one was created in this process;
    # we have no global registry but the kernel tracks ownership per-process.
    # Closing it is harmless; absence of owning handle is silently ignored.
    try:
        h = _kernel32.CreateMutexW(None, False, name)
        if h:
            _kernel32.CloseHandle(h)
    except Exception:
        pass
