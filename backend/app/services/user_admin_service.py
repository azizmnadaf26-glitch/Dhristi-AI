"""Admin user management. Every action is audited; secrets are never logged."""

import secrets

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models.user import User
from app.security.hashing import hash_password
from app.services import audit_service
from app.services.token_service import revoke_all_for_user


def new_temp_password() -> str:
    return secrets.token_urlsafe(12)  # 16 characters, above the 10 minimum


def _refuse(
    db: Session,
    request: Request | None,
    action: str,
    actor: User,
    target_id: int | None,
    reason: str,
    error: AppError,
) -> None:
    """Save a failure audit row, then raise. Saved BEFORE raising so it is not lost."""
    audit_service.record(
        db,
        request,
        action,
        "failure",
        actor_id=actor.id,
        object_type="user",
        object_id=target_id,
        detail={"reason": reason},
    )
    db.commit()
    raise error


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found", "User not found")
    return user


def create_user(
    db: Session, request: Request | None, actor: User, email: str, role: str
) -> tuple[User, str]:
    email = email.strip().lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        # The email itself is NOT written to the audit log.
        _refuse(
            db,
            request,
            "admin_user_create",
            actor,
            None,
            "email_exists",
            AppError(409, "email_exists", "A user with that email already exists"),
        )

    temp = new_temp_password()
    user = User(
        email=email,
        password_hash=hash_password(temp),
        role=role,
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    audit_service.record(
        db,
        request,
        "admin_user_create",
        "success",
        actor_id=actor.id,
        object_type="user",
        object_id=user.id,
        detail={"role": role},
    )
    db.commit()
    return user, temp


def update_user(
    db: Session,
    request: Request | None,
    actor: User,
    target: User,
    role: str | None,
    is_active: bool | None,
) -> User:
    if role is None and is_active is None:
        raise AppError(422, "validation_error", "Provide role and/or is_active")

    def refuse(reason: str, error: AppError) -> None:
        _refuse(db, request, "admin_user_update", actor, target.id, reason, error)

    new_role = role if role is not None else target.role
    new_active = is_active if is_active is not None else target.is_active

    if target.id == actor.id and new_active is False:
        refuse(
            "cannot_deactivate_self",
            AppError(409, "cannot_deactivate_self", "You cannot deactivate your own account"),
        )

    was_active_admin = target.role == "admin" and target.is_active
    stays_active_admin = new_role == "admin" and new_active
    if was_active_admin and not stays_active_admin:
        active_admins = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == "admin", User.is_active.is_(True))
        )
        if active_admins <= 1:
            refuse(
                "last_admin",
                AppError(
                    409,
                    "last_admin",
                    "The last active admin cannot be demoted or deactivated",
                ),
            )

    changed = []
    if new_role != target.role:
        changed.append("role")
    if new_active != target.is_active:
        changed.append("is_active")
    if not changed:
        return target  # nothing to do, nothing to audit

    revoke = "role" in changed or (target.is_active and not new_active)
    target.role = new_role
    target.is_active = new_active
    if revoke:
        revoke_all_for_user(db, target.id, commit=False)
    audit_service.record(
        db,
        request,
        "admin_user_update",
        "success",
        actor_id=actor.id,
        object_type="user",
        object_id=target.id,
        detail={"field": ",".join(changed)},
    )
    db.commit()  # change, revocation and audit row saved together
    return target


def reset_password(
    db: Session, request: Request | None, actor: User, target: User
) -> str:
    temp = new_temp_password()
    target.password_hash = hash_password(temp)
    target.must_change_password = True
    target.failed_login_count = 0
    target.locked_until = None
    revoke_all_for_user(db, target.id, commit=False)
    audit_service.record(
        db,
        request,
        "admin_password_reset",
        "success",
        actor_id=actor.id,
        object_type="user",
        object_id=target.id,
    )
    db.commit()
    return temp