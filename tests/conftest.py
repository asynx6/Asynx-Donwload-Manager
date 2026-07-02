import http.server
import os
import threading

import pytest


class TestHTTPHandler(http.server.BaseHTTPRequestHandler):
    data = b"A" * (1024 * 1024)  # 1 MB

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.data)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        range_header = self.headers.get("Range")
        if range_header:
            try:
                start, end = range_header.replace("bytes=", "").split("-")
                start = int(start)
                end = int(end) if end else len(self.data) - 1
                chunk = self.data[start:end + 1]
                self.send_response(206)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(chunk)))
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.data)}")
                self.end_headers()
                self.wfile.write(chunk)
                return
            except Exception:
                pass
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.data)))
        self.end_headers()
        self.wfile.write(self.data)

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="session")
def local_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), TestHTTPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/file.bin"
    server.shutdown()
