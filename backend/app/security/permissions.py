from sqlalchemy import select

from app.models.case import Case
from app.models.user import User

# All role rules live here, not scattered through the routes.
CASE_ROLES = ("operator", "clinician", "admin")
REVIEW_ROLES = ("clinician",)
ALL_ROLES = ("operator", "clinician", "planner", "admin")
SUMMARY_ROLES = ("clinician", "planner", "admin")
ADMIN_ROLES = ("admin",)
# PROVISIONAL: which roles may run simulations is still open question 5 for the team lead.
SIMULATION_RUN_ROLES = ("planner", "admin")
SIMULATION_READ_ROLES = ("clinician", "planner", "admin")

def scope_cases(user: User):
    """Only the cases this user may see. Operators see their own cases only."""
    stmt = select(Case)
    if user.role == "operator":
        stmt = stmt.where(Case.created_by == user.id)
    return stmt