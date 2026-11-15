from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import AppError
from app.models.evaluation import EvaluationRun, ModelVersion
from app.models.user import User
from app.security.deps import require_roles
from app.security.permissions import ADMIN_ROLES, SUMMARY_ROLES

router = APIRouter(prefix="/api", tags=["evaluation"])

SPLITS = ("train", "validation", "test")
DEMO_LABEL = "Demo data supplied by the model team. Not a measured clinical result."


def _iso(value: datetime) -> str:
    """UTC, ISO 8601 with Z. SQLite hands back naive datetimes, which are UTC here."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_out(run: EvaluationRun, mv: ModelVersion) -> dict:
    return {
        "id": run.id,
        "model_version": {"id": mv.id, "kind": mv.kind, "version": mv.version},
        "split": run.split,
        "run_at": _iso(run.run_at),
        "sample_count": run.sample_count,
        "metrics": run.metrics,  # stored as supplied; the backend never computes metrics
        "is_demo": run.is_demo,
    }


@router.get("/evaluation/latest")
def evaluation_latest(
    user: User = Depends(require_roles(*SUMMARY_ROLES)),
    db: Session = Depends(get_db),
):
    items = []
    for split in SPLITS:
        row = db.execute(
            select(EvaluationRun, ModelVersion)
            .join(ModelVersion, ModelVersion.id == EvaluationRun.model_version_id)
            .where(EvaluationRun.split == split)
            .order_by(EvaluationRun.run_at.desc(), EvaluationRun.id.desc())
            .limit(1)
        ).first()
        if row is not None:
            items.append(_run_out(*row))
    return {
        "label": DEMO_LABEL,
        "targets": settings.evaluation_targets,  # shown as settings, never stored as pass/fail
        "items": items,
    }


@router.get("/evaluation/runs")
def evaluation_runs(
    split: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_roles(*SUMMARY_ROLES)),
    db: Session = Depends(get_db),
):
    if split is not None and split not in SPLITS:
        raise AppError(422, "validation_error", "split must be train, validation or test")
    base = select(EvaluationRun, ModelVersion).join(
        ModelVersion, ModelVersion.id == EvaluationRun.model_version_id
    )
    count = select(func.count()).select_from(EvaluationRun)
    if split is not None:
        base = base.where(EvaluationRun.split == split)
        count = count.where(EvaluationRun.split == split)
    total = db.scalar(count) or 0
    rows = db.execute(
        base.order_by(EvaluationRun.run_at.desc(), EvaluationRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_run_out(run, mv) for run, mv in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/admin/models")
def admin_models(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(ModelVersion)) or 0
    rows = db.scalars(
        select(ModelVersion)
        .order_by(ModelVersion.kind, ModelVersion.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": m.id,
                "kind": m.kind,
                "version": m.version,
                "is_active": m.is_active,
                "notes": m.notes,
                "created_at": _iso(m.created_at),
            }
            for m in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }