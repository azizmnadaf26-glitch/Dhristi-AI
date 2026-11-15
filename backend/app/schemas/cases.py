from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["confirm", "override", "recapture", "refer"]
    final_grade: int | None = Field(default=None, ge=0, le=4)
    notes: str | None = Field(default=None, max_length=2000)