from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import AppError
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from app.security.deps import get_current_user
from app.security.rate_limit import login_rate_limit
from app.security.tokens import create_access_token
from app.services import audit_service
from app.services.auth_service import authenticate, change_password
from app.services.token_service import (
    audit_refresh_failure,
    issue_refresh_token,
    revoke_all_for_user,
    rotate_refresh_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
me_router = APIRouter(prefix="/api", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api/auth"  # the browser only sends it to the auth routes


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        max_age=settings.refresh_token_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=settings.access_token_minutes * 60,
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_rate_limit)])
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = authenticate(db, body.email, body.password, request)
    _set_refresh_cookie(response, issue_refresh_token(db, user))
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not refresh_token:
        audit_refresh_failure(db, request, None, "missing_token")
        raise AppError(401, "invalid_refresh_token", "Invalid or expired refresh token")
    user, new_raw = rotate_refresh_token(db, refresh_token, request)
    _set_refresh_cookie(response, new_raw)
    return _token_response(user)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    revoke_all_for_user(db, user.id, commit=False)
    audit_service.record(db, request, "logout", "success", actor_id=user.id)
    db.commit()  # revocation and audit row saved together
    response = Response(status_code=204)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    return response


@router.post("/change-password", status_code=204)
def change_password_route(
    body: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change_password(db, user, body.current_password, body.new_password, request)
    return Response(status_code=204)


@me_router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user