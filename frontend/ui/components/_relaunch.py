"""AsynxDL — Win32-friendly relaunch helper (Phase-H).

``os.execv`` di Windows + PyInstaller bundle terkenal broken —
keuntungan "replace process in-place" tidak mencapai real exec
karena Windows tidak punya syscall ``execve`` asli. ``python``
library cuma stub yang sebagian besar kasus gagal atau
menyebabkan ``_MEI*`` orphan yang mengacaukan bootloader extract
berikutnya (``FileNotFoundError: base_library.zip``).

Solusi: spawn process benar-benar BARU via ``subprocess.Popen``,
lalu terminate parent dengan ``os._exit(0)``. Bundle ```_MEI*`` orphans
akan di-wipe oleh runtime hook ```runtime_hook_meipass.py``` SEBELUM
new bootloader extract.

Modul ini dipisahkan supaya plugin / dialog apa pun yang butuh
restart (SettingsPanel, FirstRunWizard future, dll.) dapat
memanggil helper yang sama tanpa duplikasi logic.
"""
import os as _os
import subprocess as _subprocess
import sys as _sys
import time


def relaunch_subprocess(argv: list[str] | None = None) -> None:
    """Spawn ulang interpreter / bundle sebagai proses terpisah.

    Args:
        argv: command-line args (termasuk executable) untuk child.
              Jika ``None``, fallback ke ``[sys.executable] + sys.argv``.

    Notes:
        Setelah :func:`subprocess.Popen` sukses, parent proses
        di-terminate via :func:`os._exit(0)` — tidak raise, tidak
        graceful shutdown. AsynxDL restart = bootstrap fresh window.

        Uses ``creationflags`` di Windows:

        - ``DETACHED_PROCESS`` agar child punya console sendiri
        - ``CREATE_NEW_PROCESS_GROUP`` agar Ctrl-C tidak propagate
        """
    if argv is None:
        argv = [_sys.executable] + list(_sys.argv)
    elif not argv or not argv[0]:
        argv = [_sys.executable] + list(_sys.argv)
    argv = [str(x) for x in argv]

    # Strip dev-mode debugger args yang bisa bikin crash di child
    # (e.g. pytest, pytest-xdist).
    safe_argv = []
    skip_next = False
    for arg in argv:
        if skip_next:
            skip_next = False
            continue
        if arg.startswith(("-p", "--pytest", "--capture", "--tb")):
            if "=" not in arg:
                skip_next = True
            continue
        if arg.endswith(("pytest", "test_restart_loop.py")):
            continue
        safe_argv.append(arg)

    kwargs: dict = {"close_fds": True}
    env = _os.environ.copy()

    # PyInstaller frozen bundle: child must inherit TCL/TK library paths so
    # the Tkinter runtime hook can find _tcl_data/_tk_data inside _MEIPASS.
    # Do NOT pass PYINSTALLER_MEIPASS; the bootloader will set it fresh.
    if getattr(_sys, "frozen", False):
        meipass = getattr(_sys, "_MEIPASS", None)
        if meipass:
            env.setdefault("TCL_LIBRARY", _os.path.join(meipass, "tcl"))
            env.setdefault("TK_LIBRARY", _os.path.join(meipass, "tk"))
    kwargs["env"] = env

    if _os.name == "nt":
        flags = 0
        # DETACHED_PROCESS: child tidak share parent's console window.
        flags |= getattr(_subprocess, "DETACHED_PROCESS", 0x00000008)
        # CREATE_NEW_PROCESS_GROUP: kill-group tidak affect parent.
        flags |= getattr(_subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        kwargs["creationflags"] = flags

    # Beri waktu parent process mulai terminasi sebelum child jalan,
    # agar _MEI lama bisa dibersihkan dan tidak collision.
    if getattr(_sys, "frozen", False):
        try:
            time.sleep(0.15)
        except Exception:
            pass

    try:
        _subprocess.Popen(safe_argv, **kwargs)
    except Exception:
        # Last-resort: spawn tanpa flags.
        try:
            _subprocess.Popen([_sys.executable])
        except Exception:
            pass
    _os._exit(0)


__all__: list[str] = ["relaunch_subprocess"]
