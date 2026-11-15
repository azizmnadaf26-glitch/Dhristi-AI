from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models.user import User
from app.security.hashing import hash_password, verify_password
from app.services import audit_service

# Used when the email doesn't exist, so the work done (and time taken)
# is similar to a real login attempt.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _as_utc(value: datetime | None) -> datetime | None:
    # SQLite returns datetimes without a timezone; ours are always UTC.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _invalid_credentials() -> AppError:
    return AppError(401, "invalid_credentials", "Invalid email or password")


def authenticate(
    db: Session, email: str, password: str, request: Request | None = None
) -> User:
    now = datetime.now(timezone.utc)
    user = db.scalar(select(User).where(User.email == email.strip().lower()))

    if user is None:
        verify_password(password, _DUMMY_HASH)
        # The typed email is NOT stored.
        audit_service.record(
            db, request, "login", "failure", detail={"reason": "unknown_account"}
        )
        db.commit()
        raise _invalid_credentials()

    locked_until = _as_utc(user.locked_until)
    if locked_until is not None and locked_until > now:
        audit_service.record(
            db,
            request,
            "login",
            "denied",
            actor_id=user.id,
            detail={"reason": "account_locked"},
        )
        db.commit()
        raise AppError(423, "account_locked", "Account is temporarily locked. Try again later.")

    password_ok = verify_password(password, user.password_hash)
    if not password_ok or not user.is_active:
        user.failed_login_count += 1
        if user.failed_login_count >= settings.max_failed_logins:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
        audit_service.record(
            db,
            request,
            "login",
            "failure",
            actor_id=user.id,
            detail={"reason": "bad_password" if not password_ok else "inactive_account"},
        )
        db.commit()
        raise _invalid_credentials()

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    audit_service.record(db, request, "login", "success", actor_id=user.id)
    db.commit()
    return user


def _password_change_failed(
    db: Session, request: Request | None, user: User, reason: str
) -> None:
    audit_service.record(
        db,
        request,
        "password_change",
        "failure",
        actor_id=user.id,
        detail={"reason": reason},
    )
    db.commit()


def change_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
    request: Request | None = None,
) -> None:
    if not verify_password(current_password, user.password_hash):
        _password_change_failed(db, request, user, "wrong_current")
        raise AppError(401, "invalid_credentials", "Current password is incorrect")
    if len(new_password) < settings.password_min_length:
        _password_change_failed(db, request, user, "too_short")
        raise AppError(
            422,
            "password_too_short",
            f"New password must be at least {settings.password_min_length} characters",
        )
    if new_password == current_password:
        _password_change_failed(db, request, user, "unchanged")
        raise AppError(422, "password_unchanged", "New password must be different")

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    audit_service.record(db, request, "password_change", "success", actor_id=user.id)
    db.commit()