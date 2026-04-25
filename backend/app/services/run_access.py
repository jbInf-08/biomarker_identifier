"""
Ownership and tenant checks for analysis runs (API + services).
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.run_model import AnalysisRun
from app.models.user_model import User


def user_can_access_run(user: User, run: AnalysisRun) -> bool:
    """Admin may access any run; others must match user_id and tenant (when set)."""
    if getattr(user, "role", None) == "admin":
        return True
    if run.user_id and run.user_id != user.id:
        return False
    ut = getattr(user, "tenant_id", None)
    rt = getattr(run, "tenant_id", None)
    if ut and rt is not None and rt != ut:
        return False
    return True


def get_analysis_run_for_user(
    db: Session, run_id: str, user: User
) -> Optional[AnalysisRun]:
    """Return the run if it exists and ``user`` may access it; else None."""
    run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
    if not run or not user_can_access_run(user, run):
        return None
    return run


def filter_user_analysis_runs_query(db: Session, user: User):
    """
    Query for runs owned by ``user``, with optional tenant scope when ``user.tenant_id`` is set.
    """
    from sqlalchemy import or_

    q = db.query(AnalysisRun).filter(AnalysisRun.user_id == user.id)
    ut = getattr(user, "tenant_id", None)
    if ut:
        q = q.filter(
            or_(AnalysisRun.tenant_id == ut, AnalysisRun.tenant_id.is_(None))
        )
    return q
