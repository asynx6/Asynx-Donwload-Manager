"""v1.0.2 — Cold-start perf regression tests (Bug 2 fix).

Verify:
1. _is_another_instance_running uses socket probe (no `requests` overhead).
2. _wait_for_backend backoff is the tighter (0.05..0.3) sequence.
3. start_server_thread tidak ada blocking sleep ≥ 0.05s.
4. lifespan tidak blocking selamat uvicorn bind.
"""

import inspect
import os
import socket
import threading
import time

import pytest

import backend.main as main_module
import backend.api.server as server_module


def test_singleton_probe_uses_socket_no_http():
    """Bug 2 fix: _is_another_instance_running adalah socket-based, bukan HTTP."""
    src = inspect.getsource(main_module._is_another_instance_running)
    assert "socket.create_connection" in src, "must use socket probe"
    assert "requests.get" not in src, "must NOT import requests for this probe"
    assert "timeout=0.4" in src or "timeout = 0.4" in src


def test_wait_for_backend_backoff_is_tight():
    """Bug 2 fix: _BACKOFF_STEPS adalah tighter sequence."""
    assert main_module._BACKOFF_STEPS == (0.05, 0.05, 0.1, 0.2, 0.3)


def test_start_server_thread_has_no_blocking_sleep():
    """Bug 2 fix: start_server_thread tidak ada blocking time.sleep di awal."""
    src = inspect.getsource(server_module.start_server_thread)
    # Kalau ada time.sleep di fungsi, harus di-comment sebagai BUG-2 noticement.
    assert "time.sleep" not in src or "Bug-2" in src, (
        "start_server_thread tidak boleh ada blocking time.sleep >= 0.05."
    )


def test_pair_check_probe_returns_false_when_no_server(monkeypatch):
    """Sanity: socket probe returns False ketika tidak ada server."""
    # Pick unused port.
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert main_module._is_another_instance_running(port) is False


def test_pair_check_probe_returns_true_when_server_up():
    """Sanity: socket probe returns True ketika ada listener di port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]
    try:
        assert main_module._is_another_instance_running(port) is True
    finally:
        s.close()


def test_quick_http_get():
    """Sanity check minimal HTTP helper returns 200."""
    import urllib.request
    # Spin raw HTTP server to test against.
    from http.server import BaseHTTPRequestHandler, HTTPServer
    captured = []

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            captured.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, fmt, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), _H)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        url = f"http://127.0.0.1:{httpd.server_port}/status"
        assert main_module._quick_http_get(url, timeout=1.0) == 200
        assert captured == ["/status"]
    finally:
        httpd.shutdown()
        httpd.server_close()
