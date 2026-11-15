from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.evaluation import Dataset, EvaluationRun, ModelVersion

RUN_AT = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def _version(db, kind="grading", version="v1", active=False):
    row = ModelVersion(kind=kind, version=version, is_active=active)
    db.add(row)
    db.flush()
    return row


def test_only_one_active_version_per_kind(db_session):
    _version(db_session, version="v1", active=True)
    with pytest.raises(IntegrityError):
        _version(db_session, version="v2", active=True)
    db_session.rollback()


def test_other_kind_and_inactive_rows_are_allowed(db_session):
    _version(db_session, kind="grading", version="v1", active=True)
    _version(db_session, kind="quality", version="v1", active=True)
    _version(db_session, kind="grading", version="v2", active=False)
    _version(db_session, kind="grading", version="v3", active=False)


def test_zero_sample_count_is_rejected(db_session):
    mv = _version(db_session)
    db_session.add(EvaluationRun(model_version_id=mv.id, split="test", run_at=RUN_AT, sample_count=0, metrics={}))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_invalid_split_is_rejected(db_session):
    mv = _version(db_session)
    db_session.add(EvaluationRun(model_version_id=mv.id, split="holdout", run_at=RUN_AT, sample_count=5, metrics={}))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_duplicate_run_is_rejected(db_session):
    mv = _version(db_session)
    for _ in range(2):
        db_session.add(EvaluationRun(model_version_id=mv.id, split="test", run_at=RUN_AT, sample_count=5, metrics={}))
        if _ == 0:
            db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_dataset_name_is_unique(db_session):
    db_session.add(Dataset(name="demo"))
    db_session.flush()
    db_session.add(Dataset(name="demo"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()