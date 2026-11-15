import pytest
from sqlalchemy.exc import IntegrityError

from app.models.simulation import SimulationRun


def test_invalid_status_is_rejected(db_session, make_user):
    user = make_user()
    db_session.add(SimulationRun(created_by=user.id, status="paused", params={}))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_all_valid_statuses_are_accepted(db_session, make_user):
    user = make_user()
    for status in ("queued", "running", "completed", "failed"):
        db_session.add(SimulationRun(created_by=user.id, status=status, params={"a": 1}))
    db_session.flush()


def test_new_run_defaults_and_nulls(db_session, make_user):
    user = make_user()
    run = SimulationRun(created_by=user.id, params={"a": 1})
    db_session.add(run)
    db_session.commit()
    assert run.status == "queued"
    assert run.result is None
    assert run.error_message is None
    assert run.started_at is None
    assert run.finished_at is None
    assert run.created_at is not None