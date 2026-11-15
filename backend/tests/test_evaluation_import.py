import pytest
from sqlalchemy import func, select

from app.models.evaluation import EvaluationRun
from app.services.evaluation_import import ImportValidationError, import_evaluation


def _payload(**over):
    base = {
        "model_version": {"kind": "grading", "version": "demo-v1"},
        "dataset": {"name": "demo-set"},
        "split": "test",
        "run_at": "2026-10-01T12:00:00Z",
        "sample_count": 40,
        "metrics": {"accuracy": 0.82},
    }
    base.update(over)
    return base


def _count(db):
    return db.scalar(select(func.count()).select_from(EvaluationRun))


def test_valid_import_is_stored(db_session):
    assert import_evaluation(db_session, _payload()) == "imported"
    assert _count(db_session) == 1


def test_second_import_is_skipped(db_session):
    import_evaluation(db_session, _payload())
    assert import_evaluation(db_session, _payload()) == "skipped"
    assert _count(db_session) == 1


@pytest.mark.parametrize("field", ["model_version", "split", "run_at", "sample_count", "metrics"])
def test_missing_field_is_rejected(db_session, field):
    data = _payload()
    del data[field]
    with pytest.raises(ImportValidationError):
        import_evaluation(db_session, data)


@pytest.mark.parametrize(
    "over",
    [
        {"sample_count": 0},
        {"sample_count": True},
        {"split": "holdout"},
        {"run_at": "2026-10-01 12:00:00"},
        {"metrics": {}},
        {"surprise": 1},
    ],
)
def test_bad_values_are_rejected(db_session, over):
    with pytest.raises(ImportValidationError):
        import_evaluation(db_session, _payload(**over))
    assert _count(db_session) == 0