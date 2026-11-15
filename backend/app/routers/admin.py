from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.admin import CreateUserRequest, Role, UpdateUserRequest
from app.security.deps import require_roles
from app.security.permissions import ADMIN_ROLES
from app.services import user_admin_service
from app.services.case_service import iso

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "must_change_password": u.must_change_password,
        "locked_until": iso(u.locked_until),
        "last_login_at": iso(u.last_login_at),
        "created_at": iso(u.created_at),
    }


@router.get("/audit")
def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    action: str | None = Query(None, max_length=60),
    outcome: Literal["success", "denied", "failure"] | None = Query(None),
    actor_id: int | None = Query(None, ge=1),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """Audit rows, newest first. The table holds no secrets or notes by design."""
    base = select(AuditLog)
    if action:
        base = base.where(AuditLog.action == action)
    if outcome:
        base = base.where(AuditLog.outcome == outcome)
    if actor_id:
        base = base.where(AuditLog.actor_id == actor_id)

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "created_at": iso(r.created_at),
                "actor_id": r.actor_id,
                "action": r.action,
                "outcome": r.outcome,
                "source": r.source,
                "object_type": r.object_type,
                "object_id": r.object_id,
                "request_id": r.request_id,
                "detail": r.detail,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    role: Role | None = Query(None),
    is_active: bool | None = Query(None),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    base = select(User)
    if role:
        base = base.where(User.role == role)
    if is_active is not None:
        base = base.where(User.is_active.is_(is_active))
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [_user_dict(u) for u in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/users", status_code=201)
def create_user(
    body: CreateUserRequest,
    request: Request,
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """The temporary password is returned ONCE here and cannot be retrieved later."""
    new_user, temp = user_admin_service.create_user(db, request, user, body.email, body.role)
    return {"user": _user_dict(new_user), "temp_password": temp}


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    request: Request,
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    target = user_admin_service.get_user_or_404(db, user_id)
    updated = user_admin_service.update_user(
        db, request, user, target, body.role, body.is_active
    )
    return _user_dict(updated)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    request: Request,
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """New temporary password, shown once. The user must change it at next login."""
    target = user_admin_service.get_user_or_404(db, user_id)
    temp = user_admin_service.reset_password(db, request, user, target)
    return {"user": _user_dict(target), "temp_password": temp}