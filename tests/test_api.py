import pytest
from fastapi.testclient import TestClient

from backend.api.server import create_app
from backend.system.config import load_config


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app, base_url="http://127.0.0.1:58296")


def test_status_without_auth(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_downloads_requires_auth(client):
    resp = client.get("/downloads")
    assert resp.status_code == 403


def test_downloads_with_auth(client):
    token = load_config()["api_secret_token"]
    resp = client.get("/downloads", headers={"X-AsynxDL-Token": token})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_settings_with_auth(client):
    token = load_config()["api_secret_token"]
    resp = client.get("/settings", headers={"X-AsynxDL-Token": token})
    assert resp.status_code == 200


def test_invalid_url_rejected(client):
    token = load_config()["api_secret_token"]
    resp = client.post(
        "/downloads/add",
        json={"url": "file:///etc/passwd", "filename": "x"},
        headers={"X-AsynxDL-Token": token},
    )
    assert resp.status_code == 422


def test_path_traversal_rejected(client):
    token = load_config()["api_secret_token"]
    resp = client.post(
        "/downloads/add",
        json={"url": "http://127.0.0.1/file.bin", "filename": "../../x"},
        headers={"X-AsynxDL-Token": token},
    )
    assert resp.status_code == 422
