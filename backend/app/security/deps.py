import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models.user import User
from app.security.tokens import decode_access_token
from app.security.rate_limit import enforce_user_limit
from app.services import audit_service

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Valid token + active user in the database. Used by /me, change-password, logout."""
    if credentials is None:
        raise AppError(401, "not_authenticated", "Authentication required")
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise AppError(401, "invalid_token", "Invalid or expired token")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, "invalid_token", "Invalid or expired token")

    enforce_user_limit(user.id)
    request.state.user_id = user.id
    return user


def get_active_user(user: User = Depends(get_current_user)) -> User:
    """Use this on every other route: blocks users who still must change their password."""
    if user.must_change_password:
        raise AppError(403, "password_change_required", "You must change your password first")
    return user


def require_roles(*allowed_roles: str):
    """Every protected route declares its roles with this."""

    def checker(
        request: Request,
        user: User = Depends(get_active_user),
        db: Session = Depends(get_db),
    ) -> User:
        if user.role not in allowed_roles:
            # Write the audit row BEFORE raising, otherwise it would be lost.
            audit_service.record(
                db,
                request,
                "permission_denied",
                "denied",
                actor_id=user.id,
                detail={"role": user.role},
            )
            db.commit()
            raise AppError(403, "forbidden", "You do not have permission for this action")
        return user

    return checker