import pytest
from fastapi.testclient import TestClient

from backend.api.server import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app, base_url="http://127.0.0.1:58296")


def test_status_without_auth(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_downloads_no_auth_required(client):
    """Token dihapus — GET /downloads harus 200 tanpa auth."""
    resp = client.get("/downloads")
    assert resp.status_code == 200


def test_downloads_accessible(client):
    resp = client.get("/downloads")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_settings_without_auth(client):
    resp = client.get("/settings")
    assert resp.status_code == 200


def test_invalid_url_rejected(client):
    resp = client.post(
        "/downloads/add",
        json={"url": "file:///etc/passwd", "filename": "x"},
    )
    assert resp.status_code == 422


def test_path_traversal_rejected(client):
    resp = client.post(
        "/downloads/add",
        json={"url": "http://127.0.0.1/file.bin", "filename": "../../x"},
    )
    assert resp.status_code == 422
