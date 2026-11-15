from sqlalchemy import select

from app.models.audit import AuditLog
from app.services import audit_service

PASSWORD = "Correct-Pass-123"


def login_as(client, make_user, email, role):
    user = make_user(email=email, role=role, must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def add_rows(db, count, outcome="success", actor_id=None):
    for i in range(count):
        audit_service.record(
            db,
            None,
            "case_upload",
            outcome,
            actor_id=actor_id,
            object_type="case",
            object_id=i + 1,
        )
    db.commit()


def test_admin_lists_newest_first_with_safe_fields(client, make_user, db_session):
    _, headers = login_as(client, make_user, "admin@example.com", "admin")
    add_rows(db_session, 3)

    response = client.get("/api/admin/audit?action=case_upload", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    ids = [item["id"] for item in body["items"]]
    assert ids == sorted(ids, reverse=True)
    assert set(body["items"][0]) == {
        "id", "created_at", "actor_id", "action", "outcome",
        "source", "object_type", "object_id", "request_id", "detail",
    }
    assert body["items"][0]["created_at"].endswith("Z")


def test_pagination(client, make_user, db_session):
    _, headers = login_as(client, make_user, "admin@example.com", "admin")
    add_rows(db_session, 30)

    response = client.get(
        "/api/admin/audit?action=case_upload&page=2&page_size=10", headers=headers
    )

    body = response.json()
    assert len(body["items"]) == 10
    assert (body["total"], body["page"], body["page_size"]) == (30, 2, 10)


def test_filters_by_outcome_and_actor(client, make_user, db_session):
    admin, headers = login_as(client, make_user, "admin@example.com", "admin")
    add_rows(db_session, 2, outcome="success", actor_id=admin.id)
    add_rows(db_session, 1, outcome="failure")

    failed = client.get("/api/admin/audit?action=case_upload&outcome=failure", headers=headers)
    assert failed.json()["total"] == 1

    mine = client.get(
        f"/api/admin/audit?action=case_upload&actor_id={admin.id}", headers=headers
    )
    assert mine.json()["total"] == 2


def test_bad_filters_return_422(client, make_user):
    _, headers = login_as(client, make_user, "admin@example.com", "admin")
    assert client.get("/api/admin/audit?outcome=maybe", headers=headers).status_code == 422
    assert client.get("/api/admin/audit?page_size=101", headers=headers).status_code == 422


def test_non_admin_is_refused_and_denial_is_audited(client, make_user, db_session):
    user, headers = login_as(client, make_user, "doc@example.com", "clinician")

    response = client.get("/api/admin/audit", headers=headers)

    assert response.status_code == 403
    denied = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "permission_denied")
    ).all()
    assert len(denied) == 1
    assert denied[0].actor_id == user.id


def test_unauthenticated_is_refused(client):
    assert client.get("/api/admin/audit").status_code == 401