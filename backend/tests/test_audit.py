from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.services import audit_service


def fake_request(request_id="req123", host="127.0.0.1"):
    return SimpleNamespace(
        state=SimpleNamespace(request_id=request_id),
        client=SimpleNamespace(host=host),
    )


def test_record_saves_a_row(db_session):
    entry = audit_service.record(
        db_session,
        fake_request(),
        "case_upload",
        "success",
        object_type="case",
        object_id=7,
        detail={"status": "uploaded"},
    )
    row = db_session.scalars(select(AuditLog)).one()
    assert row.id == entry.id
    assert row.action == "case_upload"
    assert row.outcome == "success"
    assert row.object_type == "case"
    assert row.object_id == 7
    assert row.request_id == "req123"
    assert row.source == "127.0.0.1"
    assert row.detail == "status=uploaded"
    assert row.actor_id is None


def test_record_rejects_unknown_action(db_session):
    with pytest.raises(ValueError):
        audit_service.record(db_session, fake_request(), "made_up_action", "success")


def test_record_rejects_bad_outcome(db_session):
    with pytest.raises(ValueError):
        audit_service.record(db_session, fake_request(), "login", "maybe")


def test_record_rejects_unlisted_detail_key(db_session):
    with pytest.raises(ValueError):
        audit_service.record(
            db_session,
            fake_request(),
            "review_submitted",
            "success",
            detail={"notes": "some clinical text"},
        )
    assert db_session.scalars(select(AuditLog)).all() == []


def test_record_truncates_long_values(db_session):
    audit_service.record(
        db_session,
        fake_request(request_id="x" * 100),
        "analysis_failed",
        "failure",
        detail={"reason": "a" * 500},
    )
    row = db_session.scalars(select(AuditLog)).one()
    assert len(row.request_id) == 32
    assert row.detail == "reason=" + "a" * 40


def test_record_works_without_a_request(db_session):
    audit_service.record(db_session, None, "logout", "success")
    row = db_session.scalars(select(AuditLog)).one()
    assert row.source is None
    assert row.request_id is None