from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

SIMULATION_LABEL = "Simulated estimate, not a measured result"


class CreateSimulationRequest(BaseModel):
    """PLACEHOLDER parameters until the backend specification defines the real ones."""

    model_config = ConfigDict(extra="forbid")  # unknown fields -> 422

    weekly_screenings: Annotated[StrictInt, Field(ge=1, le=10000)]
    devices: Annotated[StrictInt, Field(ge=1, le=50)]
    weeks: Annotated[StrictInt, Field(ge=1, le=52)]