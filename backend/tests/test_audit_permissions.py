from sqlalchemy import select

from app.models.audit import AuditLog

PASSWORD = "Correct-Pass-123"


def auth_header(client, email):
    token = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def denied_rows(db):
    return db.scalars(
        select(AuditLog).where(AuditLog.action == "permission_denied")
    ).all()


def test_denied_request_is_audited(client, make_user, db_session):
    user = make_user(email="op@example.com", role="operator", must_change_password=False)
    headers = auth_header(client, "op@example.com")

    # /api/summary is for clinician, planner and admin only.
    response = client.get("/api/summary", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    rows = denied_rows(db_session)
    assert len(rows) == 1
    assert rows[0].outcome == "denied"
    assert rows[0].actor_id == user.id
    assert rows[0].detail == "role=operator"
    assert rows[0].request_id == response.headers["X-Request-ID"]


def test_allowed_request_is_not_audited_as_denied(client, make_user, db_session):
    make_user(email="doc@example.com", role="clinician", must_change_password=False)
    headers = auth_header(client, "doc@example.com")

    response = client.get("/api/summary", headers=headers)

    assert response.status_code == 200
    assert denied_rows(db_session) == []


def test_denial_row_has_no_secrets(client, make_user, db_session):
    make_user(email="op@example.com", role="operator", must_change_password=False)
    headers = auth_header(client, "op@example.com")
    token = headers["Authorization"].split(" ", 1)[1]

    client.get("/api/summary", headers=headers)

    row = denied_rows(db_session)[0]
    blob = " ".join(
        str(v)
        for v in (row.action, row.outcome, row.source, row.object_type, row.detail, row.request_id)
    )
    assert token not in blob
    assert "op@example.com" not in blob
    assert PASSWORD not in blob