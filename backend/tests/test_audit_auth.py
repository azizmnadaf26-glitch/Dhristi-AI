from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.errors import AppError
from app.models.audit import AuditLog
from app.models.refresh_token import RefreshToken
from app.services.token_service import issue_refresh_token, rotate_refresh_token

GOOD = {"email": "user@example.com", "password": "Correct-Pass-123"}
BAD = {"email": "user@example.com", "password": "wrong-password"}


def fake_request():
    return SimpleNamespace(
        state=SimpleNamespace(request_id="req123"),
        client=SimpleNamespace(host="127.0.0.1"),
    )


def audit_rows(db):
    return db.scalars(select(AuditLog).order_by(AuditLog.id)).all()


def login_token(client):
    return client.post("/api/auth/login", json=GOOD).json()["access_token"]


def test_login_success_is_audited(client, make_user, db_session):
    user = make_user()
    assert client.post("/api/auth/login", json=GOOD).status_code == 200
    row = audit_rows(db_session)[0]
    assert (row.action, row.outcome, row.actor_id) == ("login", "success", user.id)
    assert row.request_id


def test_failed_logins_are_audited_without_the_typed_email(client, make_user, db_session):
    user = make_user()
    client.post("/api/auth/login", json=BAD)
    client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"}
    )
    rows = audit_rows(db_session)
    assert [r.outcome for r in rows] == ["failure", "failure"]
    assert rows[0].detail == "reason=bad_password"
    assert rows[0].actor_id == user.id
    assert rows[1].detail == "reason=unknown_account"
    assert rows[1].actor_id is None
    for r in rows:
        blob = " ".join(
            str(v)
            for v in (r.action, r.outcome, r.source, r.object_type, r.object_id, r.request_id, r.detail)
        )
        assert "nobody" not in blob
        assert "example.com" not in blob
        assert "wrong-password" not in blob


def test_locked_login_is_audited_as_denied(client, make_user, db_session):
    make_user()
    for _ in range(5):
        client.post("/api/auth/login", json=BAD)
    assert client.post("/api/auth/login", json=GOOD).status_code == 423
    last = audit_rows(db_session)[-1]
    assert (last.action, last.outcome, last.detail) == (
        "login",
        "denied",
        "reason=account_locked",
    )


def test_refresh_success_is_audited(make_user, db_session):
    user = make_user()
    raw = issue_refresh_token(db_session, user)
    rotate_refresh_token(db_session, raw, fake_request())
    row = audit_rows(db_session)[-1]
    assert (row.action, row.outcome, row.actor_id) == ("token_refresh", "success", user.id)


def test_unknown_refresh_token_is_audited_without_the_token(make_user, db_session):
    with pytest.raises(AppError):
        rotate_refresh_token(db_session, "not-a-real-token", fake_request())
    row = audit_rows(db_session)[-1]
    assert (row.action, row.outcome, row.actor_id) == ("token_refresh", "failure", None)
    assert row.detail == "reason=unknown_token"
    assert "not-a-real-token" not in str(row.detail)


def test_reused_refresh_token_is_audited_and_revokes_everything(make_user, db_session):
    user = make_user()
    old_raw = issue_refresh_token(db_session, user)
    rotate_refresh_token(db_session, old_raw, fake_request())  # old_raw is now used
    with pytest.raises(AppError):
        rotate_refresh_token(db_session, old_raw, fake_request())
    row = audit_rows(db_session)[-1]
    assert row.detail == "reason=token_reuse"
    assert row.actor_id == user.id
    tokens = db_session.scalars(select(RefreshToken)).all()
    assert tokens and all(t.revoked_at is not None for t in tokens)


def test_refresh_without_cookie_is_audited(client, db_session):
    response = client.post("/api/auth/refresh")
    assert response.status_code == 401
    row = audit_rows(db_session)[-1]
    assert (row.action, row.outcome, row.detail) == (
        "token_refresh",
        "failure",
        "reason=missing_token",
    )


def test_logout_is_audited_and_revokes_tokens(client, make_user, db_session):
    user = make_user()
    token = login_token(client)
    response = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204
    row = audit_rows(db_session)[-1]
    assert (row.action, row.outcome, row.actor_id) == ("logout", "success", user.id)
    tokens = db_session.scalars(select(RefreshToken)).all()
    assert tokens and all(t.revoked_at is not None for t in tokens)


def test_password_change_is_audited(client, make_user, db_session):
    user = make_user()
    headers = {"Authorization": f"Bearer {login_token(client)}"}
    wrong = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "not-my-password", "new_password": "A-Brand-New-Pass-1"},
    )
    assert wrong.status_code == 401
    ok = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": GOOD["password"], "new_password": "A-Brand-New-Pass-1"},
    )
    assert ok.status_code == 204
    rows = [r for r in audit_rows(db_session) if r.action == "password_change"]
    assert [(r.outcome, r.detail) for r in rows] == [
        ("failure", "reason=wrong_current"),
        ("success", None),
    ]
    assert all(r.actor_id == user.id for r in rows)
    assert "A-Brand-New-Pass-1" not in " ".join(str(r.detail) for r in rows)