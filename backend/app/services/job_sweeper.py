"""Stuck-job sweeper. Runs at startup and every SWEEP_INTERVAL_S seconds.

A stale 'uploaded' case with no flag gets 'analysis_timeout'.
A queued or running simulation that is stale (or left over from before a
restart) becomes 'failed' with the message 'Interrupted'.
Jobs are NEVER re-run automatically; a human decides what to do next.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models.case import Case
from app.models.simulation import SimulationRun
from app.services import audit_service

logger = logging.getLogger("app.sweeper")

MSG_INTERRUPTED = "Interrupted"


def _as_utc(value: datetime) -> datetime:
    # SQLite returns datetimes without a timezone; ours are always UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def sweep_stuck_cases(db: Session, now: datetime | None = None) -> int:
    """Flag stale unflagged uploaded cases. Returns how many were flagged."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=2 * settings.matlab_job_timeout_s)
    candidates = db.scalars(select(Case).where(Case.status == "uploaded")).all()
    flagged = 0
    for case in candidates:
        if case.flags:
            continue
        if _as_utc(case.updated_at) >= cutoff:
            continue
        case.flags = [*case.flags, "analysis_timeout"]
        audit_service.record(
            db,
            None,
            "analysis_failed",
            "failure",
            object_type="case",
            object_id=case.id,
            detail={"reason": "analysis_timeout"},
        )
        flagged += 1
    if flagged:
        db.commit()  # flags and audit rows saved together
    return flagged


def sweep_stuck_simulations(
    db: Session, now: datetime | None = None, at_startup: bool = False
) -> int:
    """Fail queued/running simulations that cannot still be alive.

    at_startup=True fails every queued/running run (the in-memory queue is
    empty after a restart). Otherwise only runs older than
    2 x matlab_sim_timeout_s are failed. Returns how many were failed.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=2 * settings.matlab_sim_timeout_s)
    candidates = db.scalars(
        select(SimulationRun).where(SimulationRun.status.in_(("queued", "running")))
    ).all()
    failed = 0
    for run in candidates:
        if not at_startup:
            reference = run.started_at or run.created_at
            if _as_utc(reference) >= cutoff:
                continue
        run.status = "failed"
        run.error_message = MSG_INTERRUPTED
        run.result = None
        run.finished_at = now
        audit_service.record(
            db,
            None,
            "simulation_failed",
            "failure",
            actor_id=run.created_by,
            object_type="simulation",
            object_id=run.id,
            detail={"reason": "interrupted"},
        )
        failed += 1
    if failed:
        db.commit()  # status and audit rows saved together
    return failed


def sweep_once_with_new_session(startup: bool = False) -> int:
    db = SessionLocal()
    try:
        cases = sweep_stuck_cases(db)
        simulations = sweep_stuck_simulations(db, at_startup=startup)
        return cases + simulations
    finally:
        db.close()


class Sweeper:
    def __init__(self, run_once, startup_run=None) -> None:
        self._run_once = run_once
        self._startup_run = startup_run  # used for the very first pass only
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="sweeper", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        first = True
        while not self._stop.is_set():  # first pass runs immediately = startup sweep
            run = self._startup_run if (first and self._startup_run) else self._run_once
            first = False
            try:
                run()
            except Exception:
                logger.exception("Sweep failed; will try again at the next interval")
            if self._stop.wait(settings.sweep_interval_s):
                break

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(5)


sweeper = Sweeper(
    sweep_once_with_new_session,
    startup_run=lambda: sweep_once_with_new_session(startup=True),
)