import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import audit_service


def _as_utc(value: datetime) -> datetime:
    # SQLite returns datetimes without a timezone; ours are always UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _invalid() -> AppError:
    return AppError(401, "invalid_refresh_token", "Invalid or expired refresh token")


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _add_token_row(db: Session, user_id: int, now: datetime) -> str:
    """Create a random token, store only its hash, and return the raw token."""
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(raw),
            expires_at=now + timedelta(hours=settings.refresh_token_hours),
        )
    )
    return raw


def issue_refresh_token(db: Session, user: User) -> str:
    raw = _add_token_row(db, user.id, datetime.now(timezone.utc))
    db.commit()
    return raw


def revoke_all_for_user(db: Session, user_id: int, *, commit: bool = True) -> None:
    """Revoke every live refresh token of a user.

    Pass commit=False when the caller wants to save an audit row in the same transaction.
    """
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ).all()
    for row in rows:
        row.revoked_at = now
    if commit:
        db.commit()


def audit_refresh_failure(
    db: Session,
    request: Request | None,
    user_id: int | None,
    reason: str,
    *,
    revoke_all: bool = False,
) -> None:
    """Write the audit row (and any revocation) in ONE commit, before the caller raises."""
    if revoke_all and user_id is not None:
        revoke_all_for_user(db, user_id, commit=False)
    audit_service.record(
        db,
        request,
        "token_refresh",
        "failure",
        actor_id=user_id,
        detail={"reason": reason},
    )
    db.commit()


def rotate_refresh_token(
    db: Session, raw: str, request: Request | None = None
) -> tuple[User, str]:
    """Swap a valid refresh token for a new one. The old one stops working."""
    now = datetime.now(timezone.utc)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))

    if row is None:
        audit_refresh_failure(db, request, None, "unknown_token")
        raise _invalid()

    if row.revoked_at is not None:
        # An already-used token came back: it may have been stolen.
        audit_refresh_failure(db, request, row.user_id, "token_reuse", revoke_all=True)
        raise _invalid()

    if _as_utc(row.expires_at) <= now:
        audit_refresh_failure(db, request, row.user_id, "expired")
        raise _invalid()

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        audit_refresh_failure(
            db, request, row.user_id, "inactive_account", revoke_all=True
        )
        raise _invalid()

    row.revoked_at = now
    new_raw = _add_token_row(db, user.id, now)
    audit_service.record(db, request, "token_refresh", "success", actor_id=user.id)
    db.commit()  # old token revoked, new one saved and audit row written together
    return user, new_raw