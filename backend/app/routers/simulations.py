from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models.simulation import SimulationRun
from app.models.user import User
from app.routers.cases import get_session_factory  # same function, so tests can override it
from app.routers.evaluation import _iso
from app.schemas.simulation import SIMULATION_LABEL, CreateSimulationRequest
from app.security.deps import require_roles
from app.security.permissions import SIMULATION_READ_ROLES, SIMULATION_RUN_ROLES
from app.services import job_queue, simulation_service

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


def _iso_or_none(value: datetime | None) -> str | None:
    return None if value is None else _iso(value)


def _out(run: SimulationRun) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "label": SIMULATION_LABEL,
        "params": run.params,
        "result": run.result,
        "engine_mode": run.engine_mode,
        "error_message": run.error_message,
        "created_at": _iso_or_none(run.created_at),
        "started_at": _iso_or_none(run.started_at),
        "finished_at": _iso_or_none(run.finished_at),
    }


def _run_job(run_id: int, session_factory) -> None:
    db = session_factory()
    try:
        simulation_service.run_simulation_job(db, run_id)
    finally:
        db.close()


@router.post("", status_code=202)
def start_simulation(
    body: CreateSimulationRequest,
    request: Request,
    user: User = Depends(require_roles(*SIMULATION_RUN_ROLES)),
    db: Session = Depends(get_db),
    session_factory=Depends(get_session_factory),
):
    run = simulation_service.start_simulation(db, request, user, body.model_dump())
    response = _out(run)  # built before the job can change the row
    run_id = run.id
    job_queue.queue.submit_simulation(lambda: _run_job(run_id, session_factory))
    return response


@router.get("")
def list_simulations(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_roles(*SIMULATION_READ_ROLES)),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(SimulationRun)) or 0
    rows = db.scalars(
        select(SimulationRun)
        .order_by(SimulationRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{simulation_id}")
def get_simulation(
    simulation_id: int,
    user: User = Depends(require_roles(*SIMULATION_READ_ROLES)),
    db: Session = Depends(get_db),
):
    run = db.get(SimulationRun, simulation_id)
    if run is None:
        raise AppError(404, "not_found", "Simulation not found")
    return _out(run)