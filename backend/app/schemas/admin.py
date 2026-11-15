from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["operator", "clinician", "planner", "admin"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields -> 422

    email: str = Field(min_length=3, max_length=255, pattern=EMAIL_PATTERN)
    role: Role


class UpdateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role | None = None
    is_active: bool | None = None