import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.models.audit import AuditLog
from app.models.simulation import SimulationRun
from app.services.job_sweeper import Sweeper, sweep_stuck_simulations

PASSWORD = "Correct-Pass-123"
VALID = {"weekly_screenings": 200, "devices": 2, "weeks": 12}


def login_as(client, make_user, email, role):
    user = make_user(email=email, role=role, must_change_password=False)
    token = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def make_run(db, user, status="running", age_s=0):
    created = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    run = SimulationRun(
        created_by=user.id,
        status=status,
        params=VALID,
        created_at=created,
        started_at=created if status == "running" else None,
    )
    db.add(run)
    db.commit()
    return run


def stale_age():
    return 2 * settings.matlab_sim_timeout_s + 60


def test_stale_running_run_is_failed_and_audited(db_session, make_user):
    user = make_user(email="p@example.com", role="planner", must_change_password=False)
    run = make_run(db_session, user, "running", age_s=stale_age())
    assert sweep_stuck_simulations(db_session) == 1
    db_session.refresh(run)
    assert run.status == "failed"
    assert run.error_message == "Interrupted"
    assert run.result is None
    assert run.finished_at is not None
    rows = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "simulation_failed")
    ).all()
    assert len(rows) == 1
    assert rows[0].outcome == "failure"
    assert rows[0].object_type == "simulation"
    assert "interrupted" in rows[0].detail


def test_stale_queued_run_is_failed(db_session, make_user):
    user = make_user(email="p@example.com", role="planner", must_change_password=False)
    run = make_run(db_session, user, "queued", age_s=stale_age())
    assert sweep_stuck_simulations(db_session) == 1
    db_session.refresh(run)
    assert run.status == "failed"
    assert run.error_message == "Interrupted"


def test_fresh_run_is_left_alone_by_the_periodic_pass(db_session, make_user):
    user = make_user(email="p@example.com", role="planner", must_change_password=False)
    queued = make_run(db_session, user, "queued", age_s=0)
    running = make_run(db_session, user, "running", age_s=0)
    assert sweep_stuck_simulations(db_session) == 0
    db_session.refresh(queued)
    db_session.refresh(running)
    assert queued.status == "queued"
    assert running.status == "running"


def test_startup_pass_fails_even_fresh_runs(db_session, make_user):
    user = make_user(email="p@example.com", role="planner", must_change_password=False)
    queued = make_run(db_session, user, "queued", age_s=0)
    running = make_run(db_session, user, "running", age_s=0)
    assert sweep_stuck_simulations(db_session, at_startup=True) == 2
    db_session.refresh(queued)
    db_session.refresh(running)
    assert queued.status == "failed"
    assert running.status == "failed"
    assert queued.error_message == "Interrupted"
    assert running.error_message == "Interrupted"


def test_finished_runs_are_never_touched(db_session, make_user):
    user = make_user(email="p@example.com", role="planner", must_change_password=False)
    done = make_run(db_session, user, "completed", age_s=stale_age())
    bad = make_run(db_session, user, "failed", age_s=stale_age())
    bad.error_message = "Simulation timed out"
    db_session.commit()
    assert sweep_stuck_simulations(db_session, at_startup=True) == 0
    db_session.refresh(done)
    db_session.refresh(bad)
    assert done.status == "completed"
    assert bad.status == "failed"
    assert bad.error_message == "Simulation timed out"


def test_sweeper_uses_startup_run_for_the_first_pass_only(monkeypatch):
    monkeypatch.setattr(settings, "sweep_interval_s", 0.01)
    calls = []
    sweeper = Sweeper(
        lambda: calls.append("regular"),
        startup_run=lambda: calls.append("startup"),
    )
    sweeper.start()
    deadline = time.time() + 3
    while len(calls) < 3 and time.time() < deadline:
        time.sleep(0.01)
    sweeper.stop()
    assert calls[0] == "startup"
    assert "regular" in calls[1:]
    assert "startup" not in calls[1:]


def test_sweep_unblocks_new_simulations(client, make_user, db_session):
    planner, headers = login_as(client, make_user, "p@example.com", "planner")
    make_run(db_session, planner, "running", age_s=0)
    blocked = client.post("/api/simulations", json=VALID, headers=headers)
    assert blocked.status_code == 409
    assert sweep_stuck_simulations(db_session, at_startup=True) == 1
    allowed = client.post("/api/simulations", json=VALID, headers=headers)
    assert allowed.status_code == 202