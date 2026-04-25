"""
Collaborative research: shared projects (tenant-scoped) and membership.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.middleware.rate_limit import limiter
from app.models.platform_models import ProjectMember, ResearchProject
from app.models.user_model import User
from app.services.tenant_policy import effective_tenant_filter, is_platform_admin

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectRead(BaseModel):
    id: str
    tenant_id: Optional[str]
    name: str
    description: Optional[str]
    owner_user_id: str
    role: str  # caller's role: owner | member role

    model_config = ConfigDict(from_attributes=True)


def _projects_visible_to_user(db: Session, user: User):
    tid = effective_tenant_filter(user)
    member_subq = (
        db.query(ProjectMember.project_id)
        .filter(ProjectMember.user_id == user.id)
        .subquery()
    )
    q = db.query(ResearchProject).filter(
        or_(
            ResearchProject.owner_user_id == user.id,
            ResearchProject.id.in_(member_subq),
        )
    )
    if tid and not is_platform_admin(user):
        q = q.filter(
            or_(ResearchProject.tenant_id == tid, ResearchProject.tenant_id.is_(None))
        )
    return q.order_by(ResearchProject.created_at.desc())


@router.get("/projects", response_model=List[ProjectRead])
@limiter.limit("60/minute")
async def list_projects(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    del request
    out: List[ProjectRead] = []
    for p in _projects_visible_to_user(db, user).all():
        role = "owner"
        if p.owner_user_id != user.id:
            m = (
                db.query(ProjectMember)
                .filter(
                    ProjectMember.project_id == p.id,
                    ProjectMember.user_id == user.id,
                )
                .first()
            )
            role = m.role if m else "viewer"
        out.append(
            ProjectRead(
                id=p.id,
                tenant_id=p.tenant_id,
                name=p.name,
                description=p.description,
                owner_user_id=str(p.owner_user_id),
                role=role,
            )
        )
    return out


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_project(
    request: Request,
    body: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    del request
    tid = effective_tenant_filter(user)
    row = ResearchProject(
        tenant_id=tid,
        name=body.name.strip()[:255],
        description=body.description,
        owner_user_id=user.id,
    )
    db.add(row)
    db.flush()
    db.add(
        ProjectMember(
            project_id=row.id,
            user_id=user.id,
            role="admin",
        )
    )
    db.commit()
    db.refresh(row)
    return ProjectRead(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        description=row.description,
        owner_user_id=str(row.owner_user_id),
        role="owner",
    )


class MemberAdd(BaseModel):
    user_id: str
    role: str = "viewer"


@router.post("/projects/{project_id}/members", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def add_member(
    request: Request,
    project_id: str,
    body: MemberAdd,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Invite-style membership (by user UUID); production would use email invites."""
    del request
    role = body.role
    if role not in ("viewer", "editor", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")
    proj = db.query(ResearchProject).filter(ResearchProject.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if proj.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only project owner can add members")
    from uuid import UUID as PyUUID

    try:
        uid = PyUUID(body.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")
    existing = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == uid,
        )
        .first()
    )
    if existing:
        existing.role = role
    else:
        db.add(
            ProjectMember(project_id=project_id, user_id=uid, role=role)
        )
    db.commit()
    return None
