from app.config import settings


def test_oversized_body_is_rejected_before_authentication(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)  # limit becomes 2 MB
    response = client.post(
        "/api/cases",
        content=b"x" * (3 * 1024 * 1024),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 413  # not 401: no login was needed to be refused
    body = response.json()["error"]
    assert body["code"] == "file_too_large"
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


def test_normal_sized_request_still_reaches_authentication(client):
    response = client.post("/api/cases", content=b"small")
    assert response.status_code == 401