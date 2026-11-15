"""Imports evaluation results supplied by the model team. Never computes metrics."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation import Dataset, EvaluationRun, ModelVersion

SPLITS = {"train", "validation", "test"}
REQUIRED = ("model_version", "split", "run_at", "sample_count", "metrics")
ALLOWED = set(REQUIRED) | {"dataset", "is_demo"}


class ImportValidationError(ValueError):
    """The input file is not acceptable."""


def _parse_run_at(value) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ImportValidationError("run_at must be an ISO 8601 UTC string ending in Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise ImportValidationError("run_at is not a valid timestamp") from exc


def validate_payload(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ImportValidationError("Top level must be a JSON object")
    unknown = set(data) - ALLOWED
    if unknown:
        raise ImportValidationError(f"Unknown fields: {', '.join(sorted(unknown))}")
    missing = [f for f in REQUIRED if f not in data or data[f] is None]
    if missing:
        raise ImportValidationError(f"Missing fields: {', '.join(missing)}")
    mv = data["model_version"]
    if not isinstance(mv, dict) or not mv.get("kind") or not mv.get("version"):
        raise ImportValidationError("model_version needs kind and version")
    if data["split"] not in SPLITS:
        raise ImportValidationError("split must be train, validation or test")
    count = data["sample_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ImportValidationError("sample_count must be a whole number above 0")
    if not isinstance(data["metrics"], dict) or not data["metrics"]:
        raise ImportValidationError("metrics must be a non-empty object")
    ds = data.get("dataset")
    if ds is not None and (not isinstance(ds, dict) or not ds.get("name")):
        raise ImportValidationError("dataset needs a name")
    return {**data, "run_at": _parse_run_at(data["run_at"])}


def import_evaluation(db: Session, data: dict) -> str:
    """Returns 'imported' or 'skipped'. Commits itself."""
    clean = validate_payload(data)
    mv = db.scalar(
        select(ModelVersion).where(
            ModelVersion.kind == clean["model_version"]["kind"],
            ModelVersion.version == clean["model_version"]["version"],
        )
    )
    if mv is None:
        mv = ModelVersion(kind=clean["model_version"]["kind"], version=clean["model_version"]["version"])
        db.add(mv)
        db.flush()
    existing = db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.model_version_id == mv.id,
            EvaluationRun.split == clean["split"],
            EvaluationRun.run_at == clean["run_at"],
        )
    )
    if existing is not None:
        db.rollback()
        return "skipped"
    dataset_id = None
    if clean.get("dataset"):
        ds = db.scalar(select(Dataset).where(Dataset.name == clean["dataset"]["name"]))
        if ds is None:
            ds = Dataset(name=clean["dataset"]["name"])
            db.add(ds)
            db.flush()
        dataset_id = ds.id
    db.add(
        EvaluationRun(
            model_version_id=mv.id,
            dataset_id=dataset_id,
            split=clean["split"],
            run_at=clean["run_at"],
            sample_count=clean["sample_count"],
            metrics=clean["metrics"],
            is_demo=bool(clean.get("is_demo", True)),
        )
    )
    db.commit()
    return "imported"