from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings, validate_settings
from app.models.user import User
from app.security.tokens import create_access_token

PASSWORD = "Correct-Pass-123"
VALID_SIM = {"weekly_screenings": 200, "devices": 2, "weeks": 12}
TEST_ONLY_SECRET = "x" * 40  # a throwaway value, not a real secret


def login_as(client, make_user, email, role):
    user = make_user(email=email, role=role, must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def forge(claims, secret=None, algorithm="HS256"):
    secret = settings.jwt_secret if secret is None else secret
    return jwt.encode(claims, secret, algorithm=algorithm)


def good_claims(sub="1", role="planner", minutes=15):
    now = datetime.now(timezone.utc)
    return {"sub": sub, "role": role, "iat": now, "exp": now + timedelta(minutes=minutes)}


# ---------- access token attacks ----------

def test_no_token_returns_401_not_authenticated(client):
    r = client.get("/api/simulations")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"


def test_garbage_token_returns_401(client):
    r = client.get("/api/simulations", headers=bearer("not-a-real-token"))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_wrong_signature_returns_401(client, make_user):
    user, _ = login_as(client, make_user, "p@example.com", "planner")
    token = forge(good_claims(sub=str(user.id)), secret=TEST_ONLY_SECRET)
    r = client.get("/api/simulations", headers=bearer(token))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_expired_token_returns_401(client, make_user):
    user, _ = login_as(client, make_user, "p@example.com", "planner")
    token = forge(good_claims(sub=str(user.id), minutes=-1))
    r = client.get("/api/simulations", headers=bearer(token))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_alg_none_token_returns_401(client, make_user):
    user, _ = login_as(client, make_user, "p@example.com", "planner")
    token = jwt.encode(good_claims(sub=str(user.id)), None, algorithm="none")
    r = client.get("/api/simulations", headers=bearer(token))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_token_with_non_numeric_subject_returns_401(client):
    token = forge(good_claims(sub="abc"))
    r = client.get("/api/simulations", headers=bearer(token))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_token_without_subject_returns_401(client):
    claims = good_claims()
    del claims["sub"]
    r = client.get("/api/simulations", headers=bearer(forge(claims)))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_token_for_unknown_user_returns_401(client):
    token = forge(good_claims(sub="99999"))
    r = client.get("/api/simulations", headers=bearer(token))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_role_claim_in_token_is_ignored(client, make_user):
    # A clinician holding a validly signed token that CLAIMS to be admin.
    user, _ = login_as(client, make_user, "c@example.com", "clinician")
    token = create_access_token(user.id, "admin")
    r = client.post("/api/simulations", json=VALID_SIM, headers=bearer(token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


# ---------- user state ----------

def test_deactivated_user_token_stops_working(client, make_user, db_session):
    user, headers = login_as(client, make_user, "p@example.com", "planner")
    assert client.get("/api/simulations", headers=headers).status_code == 200
    row = db_session.get(User, user.id)
    row.is_active = False
    db_session.commit()
    r = client.get("/api/simulations", headers=headers)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_must_change_password_user_is_blocked(client, make_user):
    make_user(email="n@example.com", role="planner")  # must_change_password defaults to True
    token = client.post(
        "/api/auth/login", json={"email": "n@example.com", "password": PASSWORD}
    ).json()["access_token"]
    r = client.get("/api/simulations", headers=bearer(token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "password_change_required"


# ---------- refresh cookie attacks ----------

def test_garbage_refresh_cookie_is_rejected(client):
    client.cookies.set("refresh_token", "garbage-value")
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401


def test_old_refresh_cookie_cannot_be_reused(client, make_user):
    make_user(email="u@example.com", role="clinician", must_change_password=False)
    client.post("/api/auth/login", json={"email": "u@example.com", "password": PASSWORD})
    old_cookie = client.cookies.get("refresh_token")
    assert old_cookie
    assert client.post("/api/auth/refresh").status_code == 200  # rotates the cookie
    client.cookies.clear()
    client.cookies.set("refresh_token", old_cookie)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401


# ---------- unsafe settings are refused at startup ----------

def test_short_jwt_secret_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "too-short")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_settings()


def test_wildcard_cors_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", TEST_ONLY_SECRET)
    monkeypatch.setattr(settings, "cors_allowed_origins", ["*"])
    with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS"):
        validate_settings()


def test_out_of_range_referable_grade_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", TEST_ONLY_SECRET)
    monkeypatch.setattr(settings, "referable_min_grade", 9)
    with pytest.raises(RuntimeError, match="REFERABLE_MIN_GRADE"):
        validate_settings()


def test_production_with_fake_engine_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", TEST_ONLY_SECRET)
    monkeypatch.setattr(settings, "matlab_fake", True)
    with pytest.raises(RuntimeError, match="Unsafe production config"):
        validate_settings()


def test_production_with_insecure_cookie_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", TEST_ONLY_SECRET)
    monkeypatch.setattr(settings, "matlab_fake", False)
    monkeypatch.setattr(settings, "cookie_secure", False)
    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        validate_settings()


def test_safe_development_settings_are_accepted(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", TEST_ONLY_SECRET)
    monkeypatch.setattr(settings, "referable_min_grade", 2)
    monkeypatch.setattr(settings, "cors_allowed_origins", ["http://localhost:5173"])
    assert validate_settings() is None