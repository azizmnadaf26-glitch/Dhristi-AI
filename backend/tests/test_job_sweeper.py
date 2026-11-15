import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.models.audit import AuditLog
from app.models.case import Case, QualityResult
from app.services.job_sweeper import Sweeper, sweep_stuck_cases


def make_case(db, user, status="uploaded", flags=None, age_s=0):
    when = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    case = Case(
        created_by=user.id,
        status=status,
        flags=flags or [],
        created_at=when,
        updated_at=when,
    )
    db.add(case)
    db.commit()
    return case


def test_stale_unflagged_case_is_flagged_and_audited(db_session, make_user):
    user = make_user()
    case = make_case(db_session, user, age_s=2 * settings.matlab_job_timeout_s + 60)

    assert sweep_stuck_cases(db_session) == 1

    assert case.flags == ["analysis_timeout"]
    assert case.status == "uploaded"  # still routes to human review
    row = db_session.scalars(select(AuditLog).where(AuditLog.action == "analysis_failed")).one()
    assert (row.outcome, row.object_id, row.detail) == (
        "failure",
        case.id,
        "reason=analysis_timeout",
    )
    # The sweeper never re-runs a job: no result was created.
    assert db_session.scalars(select(QualityResult)).all() == []


def test_fresh_case_is_left_alone(db_session, make_user):
    case = make_case(db_session, make_user(), age_s=10)
    assert sweep_stuck_cases(db_session) == 0
    assert case.flags == []


def test_already_flagged_case_is_not_flagged_twice(db_session, make_user):
    case = make_case(db_session, make_user(), flags=["analysis_error"], age_s=100000)
    assert sweep_stuck_cases(db_session) == 0
    assert case.flags == ["analysis_error"]
    assert db_session.scalars(select(AuditLog)).all() == []


def test_other_statuses_are_left_alone(db_session, make_user):
    user = make_user()
    for status in ("graded", "needs_recapture", "in_review", "reviewed"):
        make_case(db_session, user, status=status, age_s=100000)
    assert sweep_stuck_cases(db_session) == 0


def test_sweeper_runs_repeatedly(monkeypatch):
    monkeypatch.setattr(settings, "sweep_interval_s", 0.05)
    calls = []
    sweeper = Sweeper(lambda: calls.append(1))
    sweeper.start()
    deadline = time.time() + 3
    while len(calls) < 3 and time.time() < deadline:
        time.sleep(0.02)
    sweeper.stop()
    assert len(calls) >= 3


def test_sweeper_survives_a_failing_pass(monkeypatch):
    monkeypatch.setattr(settings, "sweep_interval_s", 0.05)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database busy")

    sweeper = Sweeper(flaky)
    sweeper.start()
    deadline = time.time() + 3
    while len(calls) < 2 and time.time() < deadline:
        time.sleep(0.02)
    sweeper.stop()
    assert len(calls) >= 2