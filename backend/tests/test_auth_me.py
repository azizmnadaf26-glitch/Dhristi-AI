from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

PASSWORD = "Correct-Pass-123"


def login(client, email="user@example.com", password=PASSWORD):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_me_requires_token(client):
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_returns_profile(client, make_user):
    make_user()
    token = login(client).json()["access_token"]
    response = client.get("/api/me", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "user@example.com"
    assert body["role"] == "clinician"
    assert "password_hash" not in body


def test_me_rejects_garbage_token(client):
    response = client.get("/api/me", headers=auth("not-a-real-token"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_me_rejects_expired_token(client, make_user):
    user = make_user()
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "iat": now - timedelta(minutes=30),
            "exp": now - timedelta(minutes=15),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    assert client.get("/api/me", headers=auth(expired)).status_code == 401


def test_deactivated_user_token_stops_working(client, make_user, db_session):
    user = make_user()
    token = login(client).json()["access_token"]
    assert client.get("/api/me", headers=auth(token)).status_code == 200

    user.is_active = False
    db_session.commit()
    assert client.get("/api/me", headers=auth(token)).status_code == 401


def test_change_password_success(client, make_user):
    make_user()
    token = login(client).json()["access_token"]
    response = client.post(
        "/api/auth/change-password",
        headers=auth(token),
        json={"current_password": PASSWORD, "new_password": "New-Password-456"},
    )
    assert response.status_code == 204

    assert login(client, password=PASSWORD).status_code == 401
    new_login = login(client, password="New-Password-456")
    assert new_login.status_code == 200
    assert new_login.json()["must_change_password"] is False


def test_change_password_wrong_current(client, make_user):
    make_user()
    token = login(client).json()["access_token"]
    response = client.post(
        "/api/auth/change-password",
        headers=auth(token),
        json={"current_password": "wrong-password", "new_password": "New-Password-456"},
    )
    assert response.status_code == 401


def test_change_password_too_short(client, make_user):
    make_user()
    token = login(client).json()["access_token"]
    response = client.post(
        "/api/auth/change-password",
        headers=auth(token),
        json={"current_password": PASSWORD, "new_password": "short"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "password_too_short"