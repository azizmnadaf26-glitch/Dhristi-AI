import io
import os

from PIL import Image as PILImage
from sqlalchemy import select

from app.models.audit import AuditLog

PASSWORD = "Correct-Pass-123"
EMAIL = "doc@example.com"


def png_bytes():
    img = PILImage.frombytes("RGB", (300, 300), os.urandom(300 * 300 * 3))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def setup_user(client, make_user):
    user = make_user(email=EMAIL, role="clinician", must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def upload(client, headers, data):
    return client.post(
        "/api/cases", headers=headers, files={"file": ("scan.png", data, "image/png")}
    )


def rows(db, action):
    return db.scalars(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)
    ).all()


def test_upload_and_analysis_are_audited(client, make_user, db_session):
    user, headers = setup_user(client, make_user)
    response = upload(client, headers, png_bytes())
    assert response.status_code == 202
    case_id = response.json()["id"]

    up = rows(db_session, "case_upload")
    assert len(up) == 1
    assert (up[0].outcome, up[0].actor_id, up[0].object_id) == ("success", user.id, case_id)
    done = rows(db_session, "analysis_completed")
    assert len(done) == 1 and done[0].object_id == case_id


def test_duplicate_upload_is_audited_as_failure(client, make_user, db_session):
    _, headers = setup_user(client, make_user)
    data = png_bytes()
    assert upload(client, headers, data).status_code == 202
    assert upload(client, headers, data).status_code == 409
    up = rows(db_session, "case_upload")
    assert [r.outcome for r in up] == ["success", "failure"]
    assert up[1].detail == "reason=duplicate_image"


def test_invalid_image_is_audited_as_failure(client, make_user, db_session):
    _, headers = setup_user(client, make_user)
    response = upload(client, headers, b"this is not an image")
    assert response.status_code == 422
    up = rows(db_session, "case_upload")
    assert len(up) == 1
    assert (up[0].outcome, up[0].detail) == ("failure", "reason=invalid_image")


def test_review_and_report_are_audited_without_notes(client, make_user, db_session):
    user, headers = setup_user(client, make_user)
    case_id = upload(client, headers, png_bytes()).json()["id"]

    assert client.post(f"/api/cases/{case_id}/request-review", headers=headers).status_code == 200
    review = client.post(
        f"/api/cases/{case_id}/review",
        headers=headers,
        json={"decision": "refer", "notes": "SECRET-NOTE-TEXT"},
    )
    assert review.status_code == 201
    assert client.get(f"/api/cases/{case_id}/report", headers=headers).status_code == 200

    assert rows(db_session, "review_requested")[0].outcome == "success"
    submitted = rows(db_session, "review_submitted")
    assert (submitted[0].outcome, submitted[0].detail) == ("success", "decision=refer")
    assert submitted[0].actor_id == user.id
    assert rows(db_session, "report_viewed")[0].object_id == case_id

    everything = db_session.scalars(select(AuditLog)).all()
    for r in everything:
        blob = " ".join(
            str(v) for v in (r.action, r.outcome, r.source, r.object_type, r.detail, r.request_id)
        )
        assert "SECRET-NOTE-TEXT" not in blob


def test_review_before_request_is_audited_as_failure(client, make_user, db_session):
    _, headers = setup_user(client, make_user)
    case_id = upload(client, headers, png_bytes()).json()["id"]
    response = client.post(
        f"/api/cases/{case_id}/review", headers=headers, json={"decision": "refer"}
    )
    assert response.status_code == 409
    sub = rows(db_session, "review_submitted")
    assert (sub[0].outcome, sub[0].detail) == ("failure", "reason=invalid_status")