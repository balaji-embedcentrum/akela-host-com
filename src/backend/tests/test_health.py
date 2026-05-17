"""Epic 0 AC: the app boots and /health returns 200 with zero external accounts."""

from fastapi.testclient import TestClient

from backend.main import create_app


def test_health_ok():
    with TestClient(create_app()) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]
