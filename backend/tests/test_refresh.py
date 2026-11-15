from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.errors import AppError
from app.models.refresh_token import RefreshToken
from app.services.token_service import (
    hash_token,
    issue_refresh_token,
    rotate_refresh_token,
)

GOOD = {"email": "user@example.com", "password": "Correct-Pass-123"}


def test_login_sets_httponly_strict_cookie(client, make_user):
    make_user()
    response = client.post("/api/auth/login", json=GOOD)
    cookie = response.headers["set-cookie"].lower()
    assert "refresh_token=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie


def test_refresh_rotates_cookie_and_returns_new_access_token(client, make_user):
    make_user()
    client.post("/api/auth/login", json=GOOD)
    old_cookie = client.cookies.get("refresh_token")
    assert old_cookie

    response = client.post("/api/auth/refresh")
    assert response.status_code == 200
    assert response.json()["access_token"]
    assert client.cookies.get("refresh_token") != old_cookie


def test_refresh_without_cookie_is_rejected(client):
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"


def test_logout_revokes_refresh_token(client, make_user):
    make_user()
    token = client.post("/api/auth/login", json=GOOD).json()["access_token"]
    response = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204
    assert client.post("/api/auth/refresh").status_code == 401


def test_only_the_hash_is_stored(db_session, make_user):
    user = make_user()
    raw = issue_refresh_token(db_session, user)
    row = db_session.scalar(select(RefreshToken))
    assert row.token_hash == hash_token(raw)
    assert raw not in row.token_hash


def test_reusing_an_old_token_revokes_everything(db_session, make_user):
    user = make_user()
    token1 = issue_refresh_token(db_session, user)
    _, token2 = rotate_refresh_token(db_session, token1)

    with pytest.raises(AppError):  # token1 was already used
        rotate_refresh_token(db_session, token1)
    with pytest.raises(AppError):  # token2 is revoked as a precaution
        rotate_refresh_token(db_session, token2)


def test_expired_refresh_token_is_rejected(db_session, make_user):
    user = make_user()
    raw = issue_refresh_token(db_session, user)
    row = db_session.scalar(select(RefreshToken))
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    with pytest.raises(AppError):
        rotate_refresh_token(db_session, raw)


def test_deactivated_user_cannot_refresh(db_session, make_user):
    user = make_user()
    raw = issue_refresh_token(db_session, user)
    user.is_active = False
    db_session.commit()
    with pytest.raises(AppError):
        rotate_refresh_token(db_session, raw)