from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import AppError
from app.models.user import User
from app.security.deps import require_roles
from app.security.permissions import ALL_ROLES, SUMMARY_ROLES
from app.services import summary_service
from app.services.case_service import NOTICE

router = APIRouter(prefix="/api", tags=["meta"])

# PROVISIONAL labels: replace with the exact labels from the backend specification.
GRADE_LABELS = {
    "0": "No apparent retinopathy",
    "1": "Mild",
    "2": "Moderate",
    "3": "Severe",
    "4": "Proliferative",
}


@router.get("/config")
def get_config(user: User = Depends(require_roles(*ALL_ROLES))):
    """Safe client settings only: never secrets or local file paths."""
    return {
        "app_name": "RetinaGuide XAI",
        "notice": NOTICE,
        "engine_mode": "demo_stub" if settings.matlab_fake else "live",
        "limits": {
            "max_upload_mb": settings.max_upload_mb,
            "allowed_image_types": ["image/jpeg", "image/png"],
            "min_image_side_px": settings.min_image_side_px,
            "max_image_pixels": settings.max_image_pixels,
            "page_size_default": 25,
            "page_size_max": 100,
        },
        "thresholds": {
            "low_confidence_threshold": settings.low_confidence_threshold,
            "referable_min_grade": settings.referable_min_grade,
        },
        "grade_labels": GRADE_LABELS,
    }


@router.get("/summary")
def get_summary(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    user: User = Depends(require_roles(*SUMMARY_ROLES)),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise AppError(422, "validation_error", "date_from must not be after date_to")
    return summary_service.build_summary(db, date_from, date_to)