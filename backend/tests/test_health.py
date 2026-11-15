from fastapi.testclient import TestClient

from app.main import app


def test_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert body["engine_state"] in ("starting", "up", "down")