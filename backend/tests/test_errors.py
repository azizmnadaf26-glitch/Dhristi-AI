from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_has_request_id():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_unknown_route_uses_standard_error_shape():
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == response.headers["x-request-id"]