from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, func, select, true
from sqlalchemy.orm import Session

from app.models.case import Case, Prediction, Review
from app.services.case_service import iso

STATUSES = ("uploaded", "needs_recapture", "graded", "in_review", "reviewed")
DECISIONS = ("confirm", "override", "recapture", "refer")


def build_summary(db: Session, date_from: date | None, date_to: date | None) -> dict:
    """Aggregate counts only. No case IDs, no patient references."""
    conditions = []
    if date_from is not None:
        conditions.append(
            Case.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        conditions.append(
            Case.created_at
            < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )
    in_range = and_(true(), *conditions)
    case_ids = select(Case.id).where(in_range)

    total = db.scalar(select(func.count()).select_from(Case).where(in_range)) or 0

    by_status = dict.fromkeys(STATUSES, 0)
    for status, count in db.execute(
        select(Case.status, func.count()).where(in_range).group_by(Case.status)
    ):
        by_status[status] = count

    flagged = sum(1 for flags in db.scalars(select(Case.flags).where(in_range)) if flags)

    # Count each case's newest prediction and newest review only once.
    newest_prediction = (
        select(func.max(Prediction.id))
        .where(Prediction.case_id.in_(case_ids))
        .group_by(Prediction.case_id)
    )
    by_grade = {str(g): 0 for g in range(5)}
    referable = low_confidence = predictions_total = 0
    for grade, is_referable, is_low in db.execute(
        select(Prediction.grade, Prediction.referable, Prediction.low_confidence).where(
            Prediction.id.in_(newest_prediction)
        )
    ):
        by_grade[str(grade)] += 1
        predictions_total += 1
        referable += int(is_referable)
        low_confidence += int(is_low)

    newest_review = (
        select(func.max(Review.id))
        .where(Review.case_id.in_(case_ids))
        .group_by(Review.case_id)
    )
    decisions = dict.fromkeys(DECISIONS, 0)
    for (decision,) in db.execute(select(Review.decision).where(Review.id.in_(newest_review))):
        decisions[decision] += 1

    return {
        "range": {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        "generated_at": iso(datetime.now(timezone.utc)),
        "total_cases": total,
        "by_status": by_status,
        "flagged_cases": flagged,
        "predictions": {
            "total": predictions_total,
            "by_grade": by_grade,
            "referable": referable,
            "low_confidence": low_confidence,
        },
        "latest_review_decisions": decisions,
    }