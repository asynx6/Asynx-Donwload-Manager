import os
import tempfile
import pytest

from backend.core.file_validator import check_disk_space, sanitize_filename, resolve_duplicate_name


def test_sanitize_filename():
    assert sanitize_filename("file<name>.txt") == "file_name_.txt"
    assert sanitize_filename("   .hidden.  ") == "hidden"
    assert sanitize_filename("") == "unnamed_file"


def test_resolve_duplicate_name():
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, "a.txt"), "w").close()
        open(os.path.join(tmp, "a (1).txt"), "w").close()
        assert resolve_duplicate_name(tmp, "a.txt") == "a (2).txt"
        assert resolve_duplicate_name(tmp, "b.txt") == "b.txt"


def test_check_disk_space():
    with tempfile.TemporaryDirectory() as tmp:
        assert check_disk_space(os.path.join(tmp, "x.bin"), 1024) is True
        assert check_disk_space(os.path.join(tmp, "x.bin"), 1024 * 1024 * 1024 * 1024 * 100) is False
