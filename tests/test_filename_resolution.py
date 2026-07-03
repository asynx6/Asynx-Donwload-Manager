"""
Test v1.0.1: filename resolution.
URL dengan %20 / karakter encoded harus resolve ke nama file yang benar.
"""

from backend.core.file_validator import (
    resolve_filename,
    url_basename,
    sanitize_filename,
)


def test_url_basename_decodes_percent20():
    # URL seperti archive.org dengan spasi di name
    url = "https://archive.org/download/x/Grand%20Theft%20Auto%20-%20San%20Andreas%20PC.rar"
    assert url_basename(url) == "Grand Theft Auto - San Andreas PC.rar"


def test_url_basename_query_stripped():
    # Query string tidak boleh masuk ke nama file
    url = "https://example.com/path/movie.mp4?t=123&token=abc"
    assert url_basename(url) == "movie.mp4"


def test_url_basename_fragment_stripped():
    # Fragment # di akhir tidak boleh bocor.
    url = "https://example.com/file.zip?download=1#section"
    assert url_basename(url) == "file.zip"


def test_resolve_filename_user_priority():
    # Kalau supplied_filename valid, supplied_filename didahulukan.
    out = resolve_filename(
        user_input="my.zip",
        url_filename="other.zip",
        url="https://x/y.zip",
    )
    assert out == "my.zip"


def test_resolve_filename_fallback_to_url():
    out = resolve_filename(
        user_input="",
        url_filename="",
        url="https://archive.org/download/x/Photo%201.jpg",
    )
    assert out == "Photo 1.jpg"


def test_resolve_filename_sanitizes_traversal():
    out = resolve_filename(
        user_input="",
        url_filename="",
        url="https://x/..%2F..%2Fevil.exe",
    )
    # Pasti sanitized — tidak boleh ada path separator.
    assert "/" not in out
    assert "\\" not in out


def test_sanitize_filename_removes_unsafe():
    # Karakter Windows-forbidden: \ / : * ? " < > |
    out = sanitize_filename("file<>:\"|?*.zip")
    assert "<" not in out and ">" not in out
    assert ":" not in out and "?" not in out
    assert '"' not in out and "|" not in out
    assert "*" not in out


def test_resolve_filename_blank_inputs_falls_back():
    # user_input & url_filename kosong + URL tanpa nama → "unnamed_file"
    out = resolve_filename(user_input="", url_filename="", url="https://x/")
    # Bisa "unnamed_file" atau nama dari basename = "" → sanitized "unnamed_file".
    assert out == "unnamed_file"


def test_url_basename_handles_empty():
    assert url_basename("") == ""
    assert url_basename(None) == ""
