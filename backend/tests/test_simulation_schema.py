import pytest
from pydantic import ValidationError

from app.schemas.simulation import SIMULATION_LABEL, CreateSimulationRequest

GOOD = {"weekly_screenings": 200, "devices": 2, "weeks": 12}


def test_valid_request_is_accepted():
    assert CreateSimulationRequest(**GOOD).model_dump() == GOOD


@pytest.mark.parametrize("field", list(GOOD))
def test_missing_field_is_rejected(field):
    data = {k: v for k, v in GOOD.items() if k != field}
    with pytest.raises(ValidationError):
        CreateSimulationRequest(**data)


@pytest.mark.parametrize(
    "over",
    [
        {"weekly_screenings": 0},
        {"weekly_screenings": 10001},
        {"devices": 0},
        {"weeks": 53},
        {"weeks": True},
        {"devices": "5"},
        {"weeks": 2.5},
    ],
)
def test_bad_values_are_rejected(over):
    with pytest.raises(ValidationError):
        CreateSimulationRequest(**{**GOOD, **over})


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        CreateSimulationRequest(**GOOD, surprise=1)


def test_label_text_is_exact():
    assert SIMULATION_LABEL == "Simulated estimate, not a measured result"