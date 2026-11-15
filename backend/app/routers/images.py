from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import AppError
from app.models.case import Image
from app.models.user import User
from app.security.deps import require_roles
from app.security.permissions import CASE_ROLES
from app.services import case_service

router = APIRouter(prefix="/api/images", tags=["images"])

MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png"}


@router.get("/{image_id}/file")
def get_image_file(
    image_id: int,
    user: User = Depends(require_roles(*CASE_ROLES)),
    db: Session = Depends(get_db),
):
    image = db.get(Image, image_id)
    if image is None:
        raise AppError(404, "not_found", "Image not found")

    # Same rule as the case itself: a hidden case gives 404.
    case_service.get_case_or_404(db, user, image.case_id)

    base = (Path(settings.storage_dir) / "originals").resolve()
    path = (base / image.filename).resolve()
    if base not in path.parents or not path.is_file():
        # Outside the folder (path traversal) or missing: never reveal why.
        raise AppError(404, "not_found", "Image not found")

    return FileResponse(
        path,
        media_type=MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{image_id}/heatmap")
def get_image_heatmap(
    image_id: int,
    user: User = Depends(require_roles(*CASE_ROLES)),
    db: Session = Depends(get_db),
):
    image = db.get(Image, image_id)
    if image is None:
        raise AppError(404, "not_found", "Heatmap not found")

    # Access control: user must have permission to access the case
    case_service.get_case_or_404(db, user, image.case_id)

    base = (Path(settings.storage_dir) / "heatmaps").resolve()
    path = (base / f"{image_id}.png").resolve()
    if base not in path.parents or not path.is_file():
        raise AppError(404, "not_found", "Heatmap not found")

    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store"},
    )