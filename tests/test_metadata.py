import os
import tempfile

import pytest

from backend.core.downloader import DownloadTask
from backend.core.metadata_manager import MetadataManager


def test_metadata_create_and_load():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = MetadataManager(queue_dir=tmp)
        meta = mgr.create(
            url="http://example.com/file.zip",
            filename="file.zip",
            save_path=os.path.join(tmp, "file.zip"),
            total_size=20 * 1024 * 1024,
            thread_count=4,
        )
        assert meta["id"]
        assert meta["status"] == "PENDING"
        loaded = mgr.load(meta["id"])
        assert loaded["filename"] == "file.zip"


def test_chunk_calculation():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = MetadataManager(queue_dir=tmp)
        meta = mgr.create(
            url="http://example.com/file.zip",
            filename="file.zip",
            save_path=os.path.join(tmp, "file.zip"),
            total_size=100,
            thread_count=4,
        )
        chunks = meta["chunks"]
        assert len(chunks) == 4
        assert chunks[0]["start"] == 0
        assert chunks[-1]["end"] == 99

