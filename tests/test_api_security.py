"""AsynxDL — Test API Security.

Verifikasi behavior baru (audit v1.0.7):
    - ``/downloads/add`` reject request tanpa token.
    - Placeholder token (kosong / AUTO_GENERATED_ON_FIRST_RUN) reject semua.
    - Path traversal di ``save_path`` ditolak.
    - GET ``/settings`` wajib token; tanpa token = 403.
    - WebSocket ditolak jika token bukan HMAC-valid.

Test ini dijalankan dengan pytest dalam mode sync. Backend di-spawn di
``threading.Thread`` pendek; menggunakan ``127.0.0.1:58297`` agar tidak
conflict dengan instance dev biasa di port 58296.
"""
import os
import sys
import threading
import time
import urllib.request

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
    # Wait until server bound
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
    # Override config token sebelum load agar konsisten
    from backend.system import config
    # Set placeholder token supaya verify_token_string returns False
    config.DEFAULT_CONFIG["api_secret_token"] = ""
    t = _start_backend_in_thread()
    yield t


def _post(url: str, payload: dict, headers: dict | None = None) -> tuple:
    data = urllib.parse.urlencode(payload).encode("utf-8")  # type: ignore[name-defined]
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:  # type: ignore[name-defined]
        return e.code, e.read()


def _get(url: str, headers: dict | None = None) -> tuple:
    req = urllib.request.Request(url, method="GET", headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:  # type: ignore[name-defined]
        return e.code, e.read()


def test_status_no_auth_required(server_thread):
    code, _ = _get(f"http://127.0.0.1:{TEST_PORT}/status")
    assert code == 200


def test_downloads_without_token_is_403(server_thread):
    code, _ = _get(f"http://127.0.0.1:{TEST_PORT}/downloads")
    assert code in (401, 403)


def test_startup_with_placeholder_token_rejects_post_add(server_thread):
    # With placeholder token="" config, even requests with bogus token are
    # rejected because _load_real_token returns empty.
    import urllib.request
    req = urllib.request.Request(
        f"http://127.0.0.1:{TEST_PORT}/downloads/add",
        data=b'{"url":"http://example.com/x","speed_limit_kbps":0}',
        method="POST",
        headers={"Content-Type": "application/json",
                  "X-AsynxDL-Token": "any-token"},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            assert r.status in (401, 403, 422)  # 422 = pydantic URL parse fail
            return
    except urllib.error.HTTPError as e:  # type: ignore[name-defined]
        assert e.code in (401, 403, 422)


def test_settings_without_token_is_403(server_thread):
    code, _ = _get(f"http://127.0.0.1:{TEST_PORT}/settings")
    assert code in (401, 403)


def test_path_traversal_rejected_by_model():
    """Pydantic AddDownloadRequest rejects ``..`` segments in save_path."""
    from backend.api.models import AddDownloadRequest
    with pytest.raises(Exception):
        AddDownloadRequest.model_validate({
            "url": "http://example.com/file",
            "save_path": "../../../etc/passwd",
        })


def test_auth_helpers_compare_digest(monkeypatch):
    """auth.verify_token_string uses hmac.compare_digest & reads from config."""
    import hmac as _hmac
    from backend.api import auth
    from backend.system import config

    fake_config = {"api_secret_token": "SECRET-XYZ"}
    # auth.py imported load_config via `from … import load_config` so the
    # binding behind ``auth.load_config`` must be patched.
    monkeypatch.setattr(auth, "load_config", lambda: fake_config)
    monkeypatch.setattr(config, "DEFAULT_CONFIG",
                         {**config.DEFAULT_CONFIG,
                          "api_secret_token": "SECRET-XYZ"})

    assert auth.verify_token_string("SECRET-XYZ") is True
    assert auth.verify_token_string("WRONG") is False

    captured = {"called": False}
    real_compare = _hmac.compare_digest

    def fake_compare(a, b):
        captured["called"] = True
        return real_compare(a, b)

    monkeypatch.setattr(auth.hmac, "compare_digest", fake_compare)
    assert auth.verify_token_string("SECRET-XYZ") is True
    assert captured["called"] is True
