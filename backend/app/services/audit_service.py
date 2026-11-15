"""Append-only audit trail.

record() adds a row to the session and flushes it, but does NOT commit.
The caller commits, so the audit row and the action it describes are saved together.

Never put passwords, tokens, typed emails, notes text, patient references
or request bodies in an audit row. Only whitelisted detail keys are accepted.
"""

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog

OUTCOMES = ("success", "denied", "failure")

ACTIONS = frozenset(
    {
        # authentication
        "login",
        "token_refresh",
        "logout",
        "password_change",
        "permission_denied",
        # cases and analysis
        "case_upload",
        "case_recapture",
        "review_requested",
        "review_submitted",
        "report_viewed",
        "analysis_completed",
        "analysis_failed",
        # admin, evaluation, simulation (used in later steps)
        "admin_user_create",
        "admin_user_update",
        "admin_password_reset",
        "model_version_changed",
        "evaluation_imported",
        "simulation_started",
        "simulation_completed",
        "simulation_failed",
    }
)

ALLOWED_DETAIL_KEYS = frozenset(
    {"decision", "reason", "role", "status", "flag", "engine_mode", "field", "count"}
)

MAX_VALUE_LEN = 40
MAX_DETAIL_LEN = 200
MAX_REQUEST_ID_LEN = 32
MAX_SOURCE_LEN = 64


def _clean_detail(detail: dict | None) -> str | None:
    if not detail:
        return None
    unknown = set(detail) - ALLOWED_DETAIL_KEYS
    if unknown:
        raise ValueError(f"Audit detail key not allowed: {sorted(unknown)}")
    parts = [f"{key}={str(detail[key])[:MAX_VALUE_LEN]}" for key in sorted(detail)]
    return "; ".join(parts)[:MAX_DETAIL_LEN]


def record(
    db: Session,
    request: Request | None,
    action: str,
    outcome: str,
    *,
    actor_id: int | None = None,
    object_type: str | None = None,
    object_id: int | None = None,
    detail: dict | None = None,
    request_id: str | None = None,
) -> AuditLog:
    """Add one audit row to the session (flush, no commit)."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown audit action: {action}")
    if outcome not in OUTCOMES:
        raise ValueError(f"Unknown audit outcome: {outcome}")

    source = None
    if request is not None:
        client = getattr(request, "client", None)
        if client is not None and client.host:
            source = client.host[:MAX_SOURCE_LEN]
        if request_id is None:
            request_id = getattr(request.state, "request_id", None)

    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        outcome=outcome,
        source=source,
        object_type=object_type,
        object_id=object_id,
        request_id=request_id[:MAX_REQUEST_ID_LEN] if request_id else None,
        detail=_clean_detail(detail),
    )
    db.add(entry)
    db.flush()
    return entry