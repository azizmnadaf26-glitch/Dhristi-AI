from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.refresh_token import RefreshToken
from app.services.token_service import issue_refresh_token

PASSWORD = "Correct-Pass-123"


def login_as(client, make_user, email="admin@example.com", role="admin"):
    user = make_user(email=email, role=role, must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def tokens_of(db, user):
    return db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()


def test_create_user_and_login_with_temp_password(client, make_user):
    _, headers = login_as(client, make_user)
    response = client.post(
        "/api/admin/users",
        headers=headers,
        json={"email": "New.Person@Example.com", "role": "operator"},
    )
    assert response.status_code == 201
    body = response.json()
    temp = body["temp_password"]
    assert len(temp) >= 10
    assert body["user"]["email"] == "new.person@example.com"
    assert body["user"]["must_change_password"] is True
    assert "password_hash" not in body["user"]

    login = client.post(
        "/api/auth/login", json={"email": "new.person@example.com", "password": temp}
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True


def test_duplicate_email_is_refused(client, make_user):
    _, headers = login_as(client, make_user)
    make_user(email="taken@example.com", role="clinician")
    response = client.post(
        "/api/admin/users", headers=headers, json={"email": "taken@example.com", "role": "operator"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_exists"


def test_list_users_has_no_secrets(client, make_user):
    _, headers = login_as(client, make_user)
    make_user(email="other@example.com", role="planner")
    response = client.get("/api/admin/users", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert set(body["items"][0]) == {
        "id", "email", "role", "is_active", "must_change_password",
        "locked_until", "last_login_at", "created_at",
    }


def test_non_admin_cannot_manage_users(client, make_user):
    _, headers = login_as(client, make_user, "doc@example.com", "clinician")
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    assert client.post(
        "/api/admin/users", headers=headers, json={"email": "a@b.co", "role": "operator"}
    ).status_code == 403
    assert client.patch(
        "/api/admin/users/1", headers=headers, json={"role": "planner"}
    ).status_code == 403
    assert client.post("/api/admin/users/1/reset-password", headers=headers).status_code == 403


def test_unknown_fields_and_bad_values_are_422(client, make_user):
    _, headers = login_as(client, make_user)
    url = "/api/admin/users"
    assert client.post(
        url, headers=headers, json={"email": "a@b.co", "role": "operator", "password": "x"}
    ).status_code == 422
    assert client.post(
        url, headers=headers, json={"email": "a@b.co", "role": "superuser"}
    ).status_code == 422
    assert client.post(
        url, headers=headers, json={"email": "notanemail", "role": "operator"}
    ).status_code == 422
    assert client.patch(f"{url}/1", headers=headers, json={}).status_code == 422
    assert client.patch(
        f"{url}/1", headers=headers, json={"role": "admin", "extra": 1}
    ).status_code == 422


def test_role_change_revokes_refresh_tokens(client, make_user, db_session):
    _, headers = login_as(client, make_user)
    target = make_user(email="t@example.com", role="clinician", must_change_password=False)
    issue_refresh_token(db_session, target)
    assert all(t.revoked_at is None for t in tokens_of(db_session, target))

    response = client.patch(
        f"/api/admin/users/{target.id}", headers=headers, json={"role": "planner"}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "planner"
    tokens = tokens_of(db_session, target)
    assert tokens and all(t.revoked_at is not None for t in tokens)


def test_deactivation_takes_effect_immediately(client, make_user, db_session):
    _, headers = login_as(client, make_user)
    target = make_user(email="t@example.com", role="clinician", must_change_password=False)
    target_token = client.post(
        "/api/auth/login", json={"email": "t@example.com", "password": PASSWORD}
    ).json()["access_token"]
    target_headers = {"Authorization": f"Bearer {target_token}"}
    assert client.get("/api/me", headers=target_headers).status_code == 200

    response = client.patch(
        f"/api/admin/users/{target.id}", headers=headers, json={"is_active": False}
    )

    assert response.status_code == 200
    assert client.get("/api/me", headers=target_headers).status_code == 401
    assert all(t.revoked_at is not None for t in tokens_of(db_session, target))


def test_admin_cannot_deactivate_self(client, make_user):
    admin, headers = login_as(client, make_user)
    response = client.patch(
        f"/api/admin/users/{admin.id}", headers=headers, json={"is_active": False}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cannot_deactivate_self"


def test_cannot_demote_last_active_admin(client, make_user):
    admin, headers = login_as(client, make_user)
    make_user(email="inactive-admin@example.com", role="admin", is_active=False)

    blocked = client.patch(
        f"/api/admin/users/{admin.id}", headers=headers, json={"role": "clinician"}
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "last_admin"

    # With a second ACTIVE admin, demotion is allowed.
    make_user(email="second-admin@example.com", role="admin")
    allowed = client.patch(
        f"/api/admin/users/{admin.id}", headers=headers, json={"role": "clinician"}
    )
    assert allowed.status_code == 200
    assert allowed.json()["role"] == "clinician"


def test_reset_password(client, make_user, db_session):
    _, headers = login_as(client, make_user)
    target = make_user(
        email="t@example.com", role="clinician", must_change_password=False, failed_login_count=3
    )
    issue_refresh_token(db_session, target)

    response = client.post(f"/api/admin/users/{target.id}/reset-password", headers=headers)

    assert response.status_code == 200
    temp = response.json()["temp_password"]
    assert target.failed_login_count == 0
    assert target.must_change_password is True
    assert all(t.revoked_at is not None for t in tokens_of(db_session, target))

    old = client.post("/api/auth/login", json={"email": "t@example.com", "password": PASSWORD})
    assert old.status_code == 401
    new = client.post("/api/auth/login", json={"email": "t@example.com", "password": temp})
    assert new.status_code == 200
    assert new.json()["must_change_password"] is True


def test_admin_actions_are_audited_without_secrets(client, make_user, db_session):
    admin, headers = login_as(client, make_user)
    created = client.post(
        "/api/admin/users",
        headers=headers,
        json={"email": "secret.person@example.com", "role": "operator"},
    ).json()
    uid = created["user"]["id"]
    client.patch(f"/api/admin/users/{uid}", headers=headers, json={"role": "planner"})
    reset = client.post(f"/api/admin/users/{uid}/reset-password", headers=headers).json()

    wanted = ("admin_user_create", "admin_user_update", "admin_password_reset")
    rows = db_session.scalars(
        select(AuditLog).where(AuditLog.action.in_(wanted)).order_by(AuditLog.id)
    ).all()
    assert [r.action for r in rows] == list(wanted)
    assert all(r.outcome == "success" and r.actor_id == admin.id for r in rows)
    assert all(r.object_type == "user" and r.object_id == uid for r in rows)
    assert rows[0].detail == "role=operator"
    assert rows[1].detail == "field=role"
    for r in rows:
        blob = " ".join(
            str(v) for v in (r.action, r.source, r.object_type, r.detail, r.request_id)
        )
        assert "secret.person" not in blob
        assert created["temp_password"] not in blob
        assert reset["temp_password"] not in blob


def test_unknown_user_is_404(client, make_user):
    _, headers = login_as(client, make_user)
    assert client.patch(
        "/api/admin/users/9999", headers=headers, json={"role": "planner"}
    ).status_code == 404
    assert client.post("/api/admin/users/9999/reset-password", headers=headers).status_code == 404