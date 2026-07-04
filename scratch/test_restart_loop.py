"""AsynxDL — Restart loop stress tester (v1.1.0).

Menjalankan ``python backend/main.py --minimized`` lalu tunggu backend
``/status`` ready, shutdown, lalu ulangi 3x. Setiap iterasi tervalidasi
bahwa ``asyncio.windows_events``-style import chain (yang tergantung
``_overlapped.pyd``) tidak menggagalkan boot berikutnya.

Hasil dari script ini dipakai sebagai regresi deterministik untuk
Bug #1 — *ModuleNotFoundError: No module named '_overlapped'*.

Usage::

    python scratch/test_restart_loop.py
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\asynx\Downloads\AsynxDL").resolve()


def _send_simple_http(host: str, port: int, timeout: float = 0.5) -> int:
    import urllib.request
    req = urllib.request.Request(f"http://{host}:{port}/status", method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def _wait_status(port: int, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                if _send_simple_http("127.0.0.1", port) == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.15)
    return False


def _wait_port_free(port: int, timeout: float = 6.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                time.sleep(0.15)
        except Exception:
            return True
        time.sleep(0.15)
    return False


def main() -> int:
    """Loop 3x: spawn backend, verify /status, terminate; collect errors."""
    python = sys.executable
    backend_main = PROJECT_ROOT / "backend" / "main.py"
    if not backend_main.exists():
        print(f"[FAIL] backend/main.py not found at {backend_main}")
        return 2
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.setdefault("PYTHONPATH", str(PROJECT_ROOT))

    iterations = 3
    port = 58296
    errors: list[str] = []
    min_booted_ms: float = 9999.0
    for it in range(1, iterations + 1):
        proc = subprocess.Popen(
            [python, str(backend_main), "--minimized"],
            cwd=str(PROJECT_ROOT), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        t0 = time.monotonic()
        ready = _wait_status(port, timeout=10.0)
        dt_ms = (time.monotonic() - t0) * 1000.0
        if ready:
            min_booted_ms = min(min_booted_ms, dt_ms)
        # Capture early stderr (ModuleNotFoundError etc)
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        rc = proc.returncode
        if rc not in (0, 15) or "_overlapped" in (stderr or ""):
            errors.append(f"iter {it}: rc={rc} stderr_tail={stderr[-400:] if stderr else ''}")
        if not ready:
            errors.append(f"iter {it}: /status non-200 within timeout (boot_ms={dt_ms:.0f})")
        # Tunggu port released
        _wait_port_free(port, timeout=8.0)

    if errors:
        print("FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PASS — {iterations}x restart loop OK. fastest boot: {min_booted_ms:.0f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
