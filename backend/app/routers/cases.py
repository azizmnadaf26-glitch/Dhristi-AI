from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, get_db
from app.errors import AppError
from app.models.case import Case
from app.models.user import User
from app.schemas.cases import ReviewRequest
from app.security.deps import require_roles
from app.security.permissions import CASE_ROLES, REVIEW_ROLES, scope_cases
from app.services import case_service, job_queue
from app.security.rate_limit import enforce_upload_limit

router = APIRouter(prefix="/api/cases", tags=["cases"])


def get_session_factory():
    return SessionLocal


def _run_job(case_id: int, session_factory) -> None:
    db = session_factory()
    try:
        case_service.process_case(db, case_id)
    finally:
        db.close()


@router.post("", status_code=202)
async def upload_case(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    patient_ref: str | None = Form(default=None, max_length=100),
    eye: str | None = Form(default=None),
    user: User = Depends(require_roles(*CASE_ROLES)),
    db: Session = Depends(get_db),
    session_factory=Depends(get_session_factory),
):
    enforce_upload_limit(user.id)
    job_queue.queue.check_capacity()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise AppError(413, "file_too_large", f"File is larger than {settings.max_upload_mb} MB")
    if eye not in (None, "left", "right"):
        raise AppError(422, "validation_error", "eye must be 'left' or 'right'")

    case = case_service.create_case(db, user, data, patient_ref, eye, request)
    job_queue.queue.submit_analysis(lambda cid=case.id: _run_job(cid, session_factory))
    return {"id": case.id, "status": case.status}


@router.get("")
def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status: str | None = Query(None),
    user: User = Depends(require_roles(*CASE_ROLES)),
    db: Session = Depends(get_db),
):
    base = scope_cases(user)
    if status:
        base = base.where(Case.status == status)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(Case.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": c.id,
                "status": c.status,
                "flags": c.flags,
                "eye": c.eye,
                "created_at": case_service.iso(c.created_at),
            }
            for c in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{case_id}")
def get_case(
    case_id: int,
    user: User = Depends(require_roles(*CASE_ROLES)),
    db: Session = Depends(get_db),
):
    case = case_service.get_case_or_404(db, user, case_id)
    return case_service.case_detail(db, case)


@router.post("/{case_id}/request-review")
def request_review(
    case_id: int,
    request: Request,
    user: User = Depends(require_roles(*CASE_ROLES)),
    db: Session = Depends(get_db),
):
    case = case_service.get_case_or_404(db, user, case_id)
    case_service.request_review(db, case, user, request)
    return case_service.case_detail(db, case)


@router.post("/{case_id}/review", status_code=201)
def review_case(
    case_id: int,
    body: ReviewRequest,
    request: Request,
    user: User = Depends(require_roles(*REVIEW_ROLES)),
    db: Session = Depends(get_db),
):
    case = case_service.get_case_or_404(db, user, case_id)
    case_service.add_review(
        db, case, user, body.decision, body.final_grade, body.notes, request
    )
    return case_service.case_detail(db, case)


@router.get("/{case_id}/report")
def case_report(
    case_id: int,
    request: Request,
    user: User = Depends(require_roles(*CASE_ROLES)),
    db: Session = Depends(get_db),
):
    case = case_service.get_case_or_404(db, user, case_id)
    return case_service.build_report(db, case, user, request)


@router.get("/{case_id}/report.pdf")
@router.get("/{case_id}/pdf")
def download_case_pdf(
    case_id: int,
    request: Request,
    user: User = Depends(require_roles(*CASE_ROLES)),
    db: Session = Depends(get_db),
):
    from app.services import pdf_report_service

    case = case_service.get_case_or_404(db, user, case_id)
    pdf_path = pdf_report_service.generate_pdf_for_case(db, case, user, request)
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"RetinaGuide_Report_Case_{case.id}.pdf",
        headers={
            "Content-Disposition": f'attachment; filename="RetinaGuide_Report_Case_{case.id}.pdf"',
            "Cache-Control": "private, no-cache",
        },
    )


@router.post("/{case_id}/recapture", status_code=202)
async def recapture(
    case_id: int,
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(*CASE_ROLES)),
    db: Session = Depends(get_db),
    session_factory=Depends(get_session_factory),
):
    enforce_upload_limit(user.id)
    job_queue.queue.check_capacity()
    case = case_service.get_case_or_404(db, user, case_id)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise AppError(413, "file_too_large", f"File is larger than {settings.max_upload_mb} MB")

    case_service.recapture_case(db, user, case, data, request)
    job_queue.queue.submit_analysis(lambda cid=case.id: _run_job(cid, session_factory))
    return {"id": case.id, "status": case.status}