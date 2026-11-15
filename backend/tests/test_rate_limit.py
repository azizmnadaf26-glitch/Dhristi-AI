from app.config import settings


def test_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_login_per_min", 3)
    body = {"email": "nobody@example.com", "password": "whatever-123"}

    for _ in range(3):
        assert client.post("/api/auth/login", json=body).status_code == 401

    response = client.post("/api/auth/login", json=body)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert int(response.headers["retry-after"]) >= 1
    assert "x-request-id" in response.headers


def test_logged_in_routes_are_rate_limited(client, make_user, monkeypatch):
    make_user(must_change_password=False)
    login = client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "Correct-Pass-123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    monkeypatch.setattr(settings, "rate_limit_default_per_min", 3)
    codes = [client.get("/api/me", headers=headers).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]