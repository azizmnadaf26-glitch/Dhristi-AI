"""Simulation lifecycle: queued -> running -> completed / failed.

The engine call runs with NO open database transaction. Engine error text is
never stored or audited (it could contain internal details).
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models.simulation import SimulationRun
from app.models.user import User
from app.schemas.simulation import SIMULATION_LABEL
from app.services import audit_service, engine_adapter
from app.services.timeouts import JobTimeout, call_with_timeout

ACTIVE_STATUSES = ("queued", "running")
MSG_TIMEOUT = "Simulation timed out"
MSG_ENGINE_ERROR = "Simulation failed in the engine."
MSG_BAD_RESULT = "Engine returned an unusable result."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_simulation(db: Session, request, user: User, params: dict) -> SimulationRun:
    busy = db.scalar(
        select(func.count())
        .select_from(SimulationRun)
        .where(SimulationRun.status.in_(ACTIVE_STATUSES))
    ) or 0
    if busy:
        raise AppError(
            409,
            "simulation_busy",
            "A simulation is already queued or running. Try again when it finishes.",
        )
    run = SimulationRun(created_by=user.id, status="queued", params=params)
    db.add(run)
    db.flush()
    audit_service.record(
        db, request, "simulation_started", "success",
        actor_id=user.id, object_type="simulation", object_id=run.id,
        detail={"role": user.role},
    )
    db.commit()
    return run


def _fail(db: Session, run: SimulationRun, message: str, reason: str) -> None:
    run.status = "failed"
    run.error_message = message
    run.result = None
    run.finished_at = _now()
    audit_service.record(
        db, None, "simulation_failed", "failure",
        actor_id=run.created_by, object_type="simulation", object_id=run.id,
        detail={"reason": reason},
    )
    db.commit()


def _check_result(result):
    """Return (engine_mode, outputs) or None when the engine result is unusable."""
    if not isinstance(result, dict):
        return None
    mode = result.get("engine_mode")
    outputs = result.get("outputs")
    if not isinstance(mode, str) or not mode or len(mode) > 20:
        return None
    if not isinstance(outputs, dict):
        return None
    return mode, outputs


def run_simulation_job(db: Session, run_id: int) -> None:
    run = db.get(SimulationRun, run_id)
    if run is None or run.status != "queued":
        return
    run.status = "running"
    run.started_at = _now()
    db.commit()  # ends the transaction BEFORE the engine is called

    params = dict(run.params)
    try:
        result = call_with_timeout(
            lambda: engine_adapter.get_adapter().run_simulation(params),
            settings.matlab_sim_timeout_s,
        )
    except JobTimeout:
        _fail(db, run, MSG_TIMEOUT, "timeout")
        return
    except Exception:
        _fail(db, run, MSG_ENGINE_ERROR, "engine_error")
        return

    checked = _check_result(result)
    if checked is None:
        _fail(db, run, MSG_BAD_RESULT, "bad_result")
        return
    mode, outputs = checked
    schema_version = result.get("schema_version")
    run.result = {
        "label": SIMULATION_LABEL,
        "schema_version": schema_version if isinstance(schema_version, str) else None,
        "outputs": outputs,
    }
    run.engine_mode = mode
    run.status = "completed"
    run.finished_at = _now()
    audit_service.record(
        db, None, "simulation_completed", "success",
        actor_id=run.created_by, object_type="simulation", object_id=run.id,
        detail={"engine_mode": mode},
    )
    db.commit()