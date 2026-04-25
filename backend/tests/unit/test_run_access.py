import uuid

from app.models.run_model import AnalysisRun, RunStatus
from app.models.user_model import User
from app.services.run_access import get_analysis_run_for_user, user_can_access_run


def test_user_can_access_same_tenant(db_session):
    """SQLite test DB: create tenant, user, run with matching tenant."""
    from app.models.tenant_model import Tenant

    t = Tenant(id="t1", name="Org1")
    db_session.add(t)
    u = User(
        email="a@x.com",
        name="A",
        hashed_password="x",
        tenant_id="t1",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)

    run = AnalysisRun(
        id=str(uuid.uuid4()),
        project_name="p",
        analysis_type="biomarker_discovery",
        status=RunStatus.PENDING.value,
        user_id=u.id,
        tenant_id="t1",
    )
    db_session.add(run)
    db_session.commit()

    assert user_can_access_run(u, run)
    got = get_analysis_run_for_user(db_session, run.id, u)
    assert got is not None


def test_user_cannot_access_other_tenant(db_session):
    from app.models.tenant_model import Tenant

    db_session.add(Tenant(id="t1", name="A"))
    db_session.add(Tenant(id="t2", name="B"))
    u = User(
        email="u@x.com",
        name="U",
        hashed_password="x",
        tenant_id="t1",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)

    run = AnalysisRun(
        id=str(uuid.uuid4()),
        project_name="p",
        analysis_type="biomarker_discovery",
        status=RunStatus.PENDING.value,
        user_id=u.id,
        tenant_id="t2",
    )
    db_session.add(run)
    db_session.commit()

    assert not user_can_access_run(u, run)
    assert get_analysis_run_for_user(db_session, run.id, u) is None
