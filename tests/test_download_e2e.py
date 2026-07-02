import os
import tempfile
import time

import pytest

from backend.core.downloader import DownloadTask


def test_download_local_file(local_server):
    with tempfile.TemporaryDirectory() as tmp:
        task = DownloadTask(
            url=local_server,
            save_path=tmp,
            filename="local.bin",
            max_threads=4,
            speed_limit_kbps=0,
        )
        # Jalankan start di thread agar tidak block test
        import threading
        t = threading.Thread(target=task.start, daemon=True)
        t.start()
        timeout = 60
        start = time.time()
        while task.status not in ("COMPLETED", "ERROR") and time.time() - start < timeout:
            time.sleep(0.5)
        assert task.status == "COMPLETED", f"Download failed: {task.status}"
        final_path = os.path.join(tmp, "local.bin")
        assert os.path.exists(final_path)
        assert os.path.getsize(final_path) == 1024 * 1024
