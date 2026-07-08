"""AsynxDL — Test API Security.

Token auth sudah dihapus (localhost-only, tidak perlu auth).
Test yang tersisa: path traversal rejection.
"""
import os
import sys
import threading
import time
import urllib.request
import urllib.parse
import urllib.error

PROJECT_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir)
)
sys.path.insert(0, PROJECT_ROOT)

import pytest

TEST_PORT = 58297

def _start_backend_in_thread() -> threading.Thread:
    import uvicorn
    from backend.api.server import create_app
    config = uvicorn.Config(create_app(), host="127.0.0.1",
                            port=TEST_PORT, log_level="error", loop="asyncio")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{TEST_PORT}/status", timeout=0.5):
                return t
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("backend failed to start in test mode")

@pytest.fixture(scope="module")
def server_thread():
    t = _start_backend_in_thread()
    yield t

def _get(url: str) -> tuple:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def test_status_no_auth_required(server_thread):
    code, _ = _get(f"http://127.0.0.1:{TEST_PORT}/status")
    assert code == 200

def test_downloads_no_token_required(server_thread):
    """Token dihapus — GET /downloads harus 200 tanpa header auth."""
    code, _ = _get(f"http://127.0.0.1:{TEST_PORT}/downloads")
    assert code == 200

def test_settings_no_token_required(server_thread):
    """Token dihapus — GET /settings harus 200 tanpa header auth."""
    code, _ = _get(f"http://127.0.0.1:{TEST_PORT}/settings")
    assert code == 200

def test_path_traversal_rejected_by_model():
    """Pydantic AddDownloadRequest rejects ``..`` segments in save_path."""
    from backend.api.models import AddDownloadRequest
    with pytest.raises(Exception):
        AddDownloadRequest.model_validate({
            "url": "http://example.com/file",
            "save_path": "../../../etc/passwd",
        })

def test_auth_not_required(server_thread):
    """Token auth dihapus — endpoint tidak butuh auth sama sekali."""
    code, _ = _get(f"http://127.0.0.1:{TEST_PORT}/settings")
    assert code == 200
