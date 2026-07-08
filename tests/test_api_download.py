import time

import pytest
from fastapi.testclient import TestClient

from backend.api.server import create_app
from backend.api.state import manager


def wait_for_status(client: TestClient, task_id: str, timeout: int = 30):
    start = time.time()
    while time.time() - start < timeout:
        resp = client.get(f"/downloads/{task_id}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") in ("COMPLETED", "ERROR"):
                return data
        time.sleep(1)
    return None


def test_add_download_real_network(client):
    resp = client.post(
        "/downloads/add",
        json={"url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf", "filename": "dummy.pdf"},
    )
    assert resp.status_code == 200
    data = resp.json()
    task_id = data.get("id")
    assert task_id
    final = wait_for_status(client, task_id, timeout=30)
    assert final, "Download tidak selesai dalam batas waktu"
    assert final["status"] == "COMPLETED", f"Download gagal: {final}"


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_add_same_url_after_error(client):
    """User bisa re-add URL yang sama setelah task sebelumnya ERROR/COMPLETED.

    Verifikasi: duplicate check di start_new cleanup task ERROR/CANCELLED
    supaya user bisa retry download tanpa restart app.
    """
    test_url = f"http://127.0.0.1:1/test_retry_{int(time.time())}.bin"

    # Simulate: tambah task, lalu paksa status ke ERROR
    result = manager.start_new(url=test_url)
    assert "id" in result, f"start_new failed: {result}"
    task_id1 = result["id"]

    # Force task ke ERROR (simulasi download gagal)
    with manager._lock:
        task = manager._active.get(task_id1)
        assert task is not None
        task._status = "ERROR"

    # Re-add URL yang sama — harusnya tidak 409
    resp2 = client.post(
        "/downloads/add",
        json={"url": test_url},
    )
    assert resp2.status_code == 200, f"Expected 200, got {resp2.status_code}: {resp2.text}"
    task_id2 = resp2.json()["id"]
    assert task_id2 != task_id1, "Should create new task, not reuse old one"
