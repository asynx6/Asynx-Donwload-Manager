"""
AsynxDL — Entry Point Aplikasi Lengkap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Menjalankan urutan startup:
    1. Load config
    2. Start FastAPI server di thread
    3. First-run wizard (jika diperlukan)
    4. Buka UI CustomTkinter
"""

import argparse
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.server import start_server_thread
from backend.system.config import is_first_run, load_config
from backend.system.crash_logger import install_crash_handler, redirect_streams_to_log, run_with_crash_logging
from backend.system.tray import TrayIcon
from frontend.ui.app import AsynxDLApp
from frontend.ui.windows.first_run_wizard import FirstRunWizard


def _wait_for_backend(timeout: int = 10) -> bool:
    import requests
    config = load_config()
    port = config.get("api_port", 58296)
    url = f"http://127.0.0.1:{port}/status"
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, timeout=1)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def main():
    parser = argparse.ArgumentParser(description="AsynxDL — Download Manager")
    parser.add_argument("--minimized", action="store_true", help="Start minimized to tray")
    parser.add_argument("--first-run", action="store_true", help="Force first-run wizard")
    args = parser.parse_args()

    config = load_config()
    port = config.get("api_port", 58296)

    # Start FastAPI server di thread daemon
    server_thread = start_server_thread(port=port)
    if not _wait_for_backend(timeout=10):
        print("[ERROR] Backend server tidak dapat di-start.")
        sys.exit(1)

    # Inisialisasi UI root
    app = AsynxDLApp(minimized=args.minimized)

    # Force window to be visible and on top briefly at startup
    if not args.minimized:
        app._root.attributes("-topmost", True)
        app.show_window()
        app._root.update_idletasks()
        app._root.after(500, lambda: app._root.attributes("-topmost", False))

    # First-run wizard
    if is_first_run() or args.first_run:
        def on_finish():
            app.show_window()
        wizard = FirstRunWizard(app._root, on_finish=on_finish)
        wizard.grab_set()
        app._root.wait_window(wizard)

    app.run()


if __name__ == "__main__":
    install_crash_handler()
    redirect_streams_to_log()
    run_with_crash_logging(main)
