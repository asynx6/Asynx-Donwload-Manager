import time

import pytest
from fastapi.testclient import TestClient

from backend.api.server import create_app
from backend.system.config import load_config


def wait_for_status(client: TestClient, task_id: str, timeout: int = 30):
    token = load_config()["api_secret_token"]
    start = time.time()
    while time.time() - start < timeout:
        resp = client.get(f"/downloads/{task_id}", headers={"X-AsynxDL-Token": token})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") in ("COMPLETED", "ERROR"):
                return data
        time.sleep(1)
    return None


def test_add_download_real_network(client):
    token = load_config()["api_secret_token"]
    resp = client.post(
        "/downloads/add",
        json={"url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf", "filename": "dummy.pdf"},
        headers={"X-AsynxDL-Token": token},
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
