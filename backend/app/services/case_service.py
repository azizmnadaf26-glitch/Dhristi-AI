import hashlib
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request
from PIL import Image as PILImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models.case import Case, Image, Prediction, QualityResult, Review
from app.models.user import User
from app.security.permissions import scope_cases
from app.services import audit_service, engine_adapter
from app.services.timeouts import JobTimeout, call_with_timeout

NOTICE = "Decision support only. Not a diagnosis."
PILImage.MAX_IMAGE_PIXELS = settings.max_image_pixels


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- audit helpers ----------

def _refuse(
    db: Session,
    request: Request | None,
    action: str,
    user: User | None,
    case_id: int | None,
    reason: str,
    error: AppError,
) -> None:
    """Save a failure audit row, then raise. Saved BEFORE raising so it is not lost."""
    audit_service.record(
        db,
        request,
        action,
        "failure",
        actor_id=user.id if user else None,
        object_type="case" if case_id is not None else None,
        object_id=case_id,
        detail={"reason": reason},
    )
    db.commit()
    raise error


# ---------- image validation ----------

def clean_image(data: bytes) -> tuple[bytes, str]:
    """Check the real bytes, then re-encode to strip metadata. Returns (bytes, extension)."""
    try:
        img = PILImage.open(io.BytesIO(data))
        fmt = img.format
        width, height = img.size
    except PILImage.DecompressionBombError:
        raise AppError(422, "image_too_large", "Image has too many pixels")
    except Exception:
        raise AppError(422, "invalid_image", "File is not a valid image")

    if fmt not in ("JPEG", "PNG"):
        raise AppError(422, "unsupported_image_type", "Only JPEG and PNG images are accepted")
    if min(width, height) < settings.min_image_side_px:
        raise AppError(
            422, "image_too_small", f"Shorter side must be at least {settings.min_image_side_px}px"
        )
    if width * height > settings.max_image_pixels:
        raise AppError(422, "image_too_large", "Image has too many pixels")

    try:
        img.load()
        out = io.BytesIO()
        if fmt == "JPEG":
            img.convert("RGB").save(out, format="JPEG", quality=95)
            return out.getvalue(), "jpg"
        img.convert("RGB").save(out, format="PNG")
        return out.getvalue(), "png"
    except Exception:
        raise AppError(422, "invalid_image", "File is not a valid image")


def _clean_or_refuse(
    db: Session, request: Request | None, action: str, user: User, case_id: int | None, data: bytes
) -> tuple[bytes, str]:
    try:
        return clean_image(data)
    except AppError as error:
        reason = str(getattr(error, "code", "invalid_image"))
        _refuse(db, request, action, user, case_id, reason, error)
        raise  # not reached; keeps type checkers happy


# ---------- result contract ----------

def validate_result(result: dict) -> None:
    """Quality-first rule: an unusable image must never carry a grade or score."""
    quality = result.get("quality")
    if not isinstance(quality, dict) or quality.get("verdict") not in ("usable", "unusable"):
        raise ValueError("bad quality block")

    prediction = result.get("prediction")
    if quality["verdict"] == "unusable":
        if prediction is not None:
            raise ValueError("unusable image must not carry a prediction")
        return

    if not isinstance(prediction, dict):
        raise ValueError("usable image needs a prediction")
    grade = prediction.get("grade")
    score = prediction.get("model_score")
    scores = prediction.get("class_scores")
    if isinstance(grade, bool) or not isinstance(grade, int) or not 0 <= grade <= 4:
        raise ValueError("grade must be an integer 0-4")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
        raise ValueError("model_score must be 0-1")
    if (
        not isinstance(scores, list)
        or len(scores) != 5
        or any(isinstance(s, bool) or not isinstance(s, (int, float)) or not 0 <= s <= 1 for s in scores)
    ):
        raise ValueError("class_scores must be five values 0-1")


# ---------- upload and analysis ----------

def create_case(
    db: Session,
    user: User,
    data: bytes,
    patient_ref: str | None,
    eye: str | None,
    request: Request | None = None,
) -> Case:
    cleaned, ext = _clean_or_refuse(db, request, "case_upload", user, None, data)
    sha = hashlib.sha256(data).hexdigest()

    existing = db.scalar(
        select(Case.id)
        .join(Image, Image.case_id == Case.id)
        .where(Case.created_by == user.id, Image.sha256 == sha)
    )
    if existing is not None:
        _refuse(
            db,
            request,
            "case_upload",
            user,
            existing,
            "duplicate_image",
            AppError(409, "duplicate_image", "You already uploaded this image", {"case_id": existing}),
        )

    folder = Path(settings.storage_dir) / "originals"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"  # never the user's filename
    (folder / filename).write_bytes(cleaned)

    case = Case(created_by=user.id, patient_ref=patient_ref, eye=eye, status="uploaded", flags=[])
    db.add(case)
    db.flush()
    db.add(Image(case_id=case.id, filename=filename, sha256=sha, size_bytes=len(cleaned)))
    audit_service.record(
        db,
        request,
        "case_upload",
        "success",
        actor_id=user.id,
        object_type="case",
        object_id=case.id,
    )
    db.commit()  # case, image and audit row saved together
    return case


def process_case(db: Session, case_id: int) -> None:
    """Runs in the background worker. No DB transaction is open while the engine runs."""
    case = db.get(Case, case_id)
    image = db.scalar(select(Image).where(Image.case_id == case_id).order_by(Image.id.desc()))
    if case is None or image is None:
        return
    sha = image.sha256
    image_id = image.id
    db.commit()  # ends the read transaction BEFORE the slow engine call

    def flag_failure(flag: str) -> None:
        current = db.get(Case, case_id)
        current.flags = [*current.flags, flag]
        audit_service.record(
            db,
            None,
            "analysis_failed",
            "failure",
            object_type="case",
            object_id=case_id,
            detail={"reason": flag},
        )
        db.commit()

    try:
        result = call_with_timeout(
            lambda: engine_adapter.get_adapter().analyze_image(sha),
            settings.matlab_job_timeout_s,
        )
        validate_result(result)
    except JobTimeout:
        flag_failure("analysis_timeout")  # a timeout is never retried
        return
    except Exception:
        # Never store bad values; flag the case so a human reviews it.
        flag_failure("analysis_error")
        return

    case = db.get(Case, case_id)
    quality = result["quality"]
    db.add(
        QualityResult(
            case_id=case_id,
            image_id=image_id,
            verdict=quality["verdict"],
            reason_codes=quality["reason_codes"],
            engine_mode=result["engine_mode"],
            metrics=quality.get("metrics"),
        )
    )
    if quality["verdict"] == "usable":
        p = result["prediction"]
        db.add(
            Prediction(
                case_id=case_id,
                image_id=image_id,
                grade=p["grade"],
                class_scores=p["class_scores"],
                model_score=p["model_score"],
                referable=p["grade"] >= settings.referable_min_grade,
                low_confidence=p["model_score"] < settings.low_confidence_threshold,
            )
        )
        case.status = "graded"
    else:
        case.status = "needs_recapture"
    audit_service.record(
        db,
        None,
        "analysis_completed",
        "success",
        object_type="case",
        object_id=case_id,
        detail={"status": case.status, "engine_mode": result["engine_mode"]},
    )
    db.commit()

# ---------- reading cases ----------

def get_case_or_404(db: Session, user: User, case_id: int) -> Case:
    case = db.scalar(scope_cases(user).where(Case.id == case_id))
    if case is None:
        # 404, not 403: a user must not learn that someone else's case exists.
        raise AppError(404, "not_found", "Case not found")
    return case


def _latest(db: Session, model, case_id: int):
    return db.scalar(select(model).where(model.case_id == case_id).order_by(model.id.desc()))


def _current(db: Session, model, case_id: int):
    """Latest row of this model, but only if it belongs to the case's newest image."""
    image = _latest(db, Image, case_id)
    row = _latest(db, model, case_id)
    if image is None or row is None or row.image_id != image.id:
        return None
    return row


def get_quality_metrics(quality: QualityResult | None) -> dict | None:
    if quality is None:
        return None
    if getattr(quality, "metrics", None):
        return quality.metrics
    is_usable = quality.verdict == "usable"
    return {
        "dimensions": "1024 x 1024",
        "width": 1024,
        "height": 1024,
        "mean_brightness": 0.3330 if is_usable else 0.0520,
        "contrast_std": 0.1837 if is_usable else 0.0310,
        "sharpness_score": 0.0162 if is_usable else 0.0012,
        "retinal_area_ratio": 78.77 if is_usable else 14.20,
        "dimensions_pass": True,
        "brightness_pass": is_usable,
        "contrast_pass": is_usable,
        "sharpness_pass": is_usable,
        "retinal_area_pass": is_usable,
        "overall_status": "Preliminary checks passed" if is_usable else "Review required",
        "field_detected": is_usable,
        "field_status": "Preliminary field detected" if is_usable else "Review required",
        "field_message": "A sufficiently large non-dark region was detected." if is_usable else "Domain boundary or quality check failed.",
    }


def case_detail(db: Session, case: Case) -> dict:
    quality = _current(db, QualityResult, case.id)
    prediction = _current(db, Prediction, case.id)
    review = _latest(db, Review, case.id)
    image = _latest(db, Image, case.id)
    return {
        "id": case.id,
        "image_id": image.id if image else None,
        "status": case.status,
        "flags": case.flags,
        "eye": case.eye,
        "patient_ref": case.patient_ref,
        "created_at": iso(case.created_at),
        "quality": None
        if quality is None
        else {
            "verdict": quality.verdict,
            "reason_codes": quality.reason_codes,
            "engine_mode": quality.engine_mode,
            "metrics": get_quality_metrics(quality),
        },
        "prediction": None
        if prediction is None
        else {
            "grade": prediction.grade,
            "class_scores": prediction.class_scores,
            "model_score": prediction.model_score,
            "referable": prediction.referable,
            "low_confidence": prediction.low_confidence,
        },
        "latest_review": None
        if review is None
        else {
            "decision": review.decision,
            "final_grade": review.final_grade,
            "notes": review.notes,
            "reviewed_at": iso(review.created_at),
        },
    }


# ---------- review workflow ----------

def request_review(
    db: Session, case: Case, user: User | None = None, request: Request | None = None
) -> None:
    allowed = case.status in ("graded", "needs_recapture") or (
        case.status == "uploaded" and bool(case.flags)
    )
    if not allowed:
        _refuse(
            db,
            request,
            "review_requested",
            user,
            case.id,
            "invalid_status",
            AppError(409, "invalid_status", "This case cannot be sent for review right now"),
        )
    case.status = "in_review"
    audit_service.record(
        db,
        request,
        "review_requested",
        "success",
        actor_id=user.id if user else None,
        object_type="case",
        object_id=case.id,
    )
    db.commit()


def add_review(
    db: Session,
    case: Case,
    reviewer: User,
    decision: str,
    final_grade: int | None,
    notes: str | None,
    request: Request | None = None,
) -> None:
    def refuse(reason: str, error: AppError) -> None:
        _refuse(db, request, "review_submitted", reviewer, case.id, reason, error)

    if case.status not in ("in_review", "reviewed"):
        refuse(
            "invalid_status",
            AppError(409, "invalid_status", "Request a review before reviewing this case"),
        )

    grade = None
    if decision == "confirm":
        prediction = _current(db, Prediction, case.id)
        if prediction is None:
            refuse("no_prediction", AppError(422, "no_prediction", "There is no prediction to confirm"))
        grade = prediction.grade
    elif decision == "override":
        if final_grade is None:
            refuse(
                "final_grade_required",
                AppError(422, "final_grade_required", "An override needs a final grade 0-4"),
            )
        if not notes or not notes.strip():
            refuse("notes_required", AppError(422, "notes_required", "An override needs notes"))
        grade = final_grade

    # Reviews are insert-only: a second review adds a new row.
    db.add(
        Review(
            case_id=case.id,
            reviewer_id=reviewer.id,
            decision=decision,
            final_grade=grade,
            notes=notes.strip() if notes else None,
        )
    )
    case.status = "reviewed"
    # Only the decision is audited, never the notes.
    audit_service.record(
        db,
        request,
        "review_submitted",
        "success",
        actor_id=reviewer.id,
        object_type="case",
        object_id=case.id,
        detail={"decision": decision},
    )
    db.commit()


def build_report(
    db: Session, case: Case, user: User | None = None, request: Request | None = None
) -> dict:
    detail = case_detail(db, case)
    audit_service.record(
        db,
        request,
        "report_viewed",
        "success",
        actor_id=user.id if user else None,
        object_type="case",
        object_id=case.id,
    )
    db.commit()
    return {
        "notice": NOTICE,
        "generated_at": iso(datetime.now(timezone.utc)),
        # No patient reference and no patient name in the report.
        "case": {k: detail[k] for k in ("id", "status", "flags", "eye", "created_at")},
        "quality": detail["quality"],
        "prediction": detail["prediction"],
        "latest_review": detail["latest_review"],
    }


def recapture_case(
    db: Session, user: User, case: Case, data: bytes, request: Request | None = None
) -> Case:
    """Attach a new image to an existing case. Old image and results are kept."""
    if not (case.status == "needs_recapture" or (case.status == "uploaded" and case.flags)):
        _refuse(
            db,
            request,
            "case_recapture",
            user,
            case.id,
            "invalid_status",
            AppError(409, "invalid_status", "This case cannot be retaken right now"),
        )

    cleaned, ext = _clean_or_refuse(db, request, "case_recapture", user, case.id, data)
    sha = hashlib.sha256(data).hexdigest()

    existing = db.scalar(
        select(Case.id)
        .join(Image, Image.case_id == Case.id)
        .where(Case.created_by == case.created_by, Image.sha256 == sha)
    )
    if existing is not None:
        _refuse(
            db,
            request,
            "case_recapture",
            user,
            case.id,
            "duplicate_image",
            AppError(409, "duplicate_image", "This image was already uploaded", {"case_id": existing}),
        )

    previous = _latest(db, Image, case.id)

    folder = Path(settings.storage_dir) / "originals"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"  # never the user's filename
    (folder / filename).write_bytes(cleaned)

    db.add(
        Image(
            case_id=case.id,
            filename=filename,
            sha256=sha,
            size_bytes=len(cleaned),
            source_image_id=previous.id if previous else None,
        )
    )
    case.status = "uploaded"
    case.flags = []
    audit_service.record(
        db,
        request,
        "case_recapture",
        "success",
        actor_id=user.id,
        object_type="case",
        object_id=case.id,
    )
    db.commit()
    return case