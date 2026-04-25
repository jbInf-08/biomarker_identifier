"""
Admin-only endpoints (federated API keys, etc.).
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import create_service_api_key, get_current_user, log_audit, require_roles
from app.core.database import get_db
from app.middleware.rate_limit import limiter
from app.models.platform_models import ComplianceChecklistItem, ServiceApiKey
from app.models.user_model import User
from app.services.tenant_policy import apply_tenant_scope

router = APIRouter()

# Minimum length for waiver rationale when status is `waived` (audit evidence).
COMPLIANCE_WAIVER_NOTES_MIN_LEN = 20


def _validate_compliance_item_evidence(row: ComplianceChecklistItem) -> None:
    """Enforce evidence rules on the persisted row state before commit."""
    status = (row.status or "").strip()
    evidence = (row.evidence_link or "").strip()
    notes = (row.notes or "").strip()
    if status == "complete" and not evidence:
        raise HTTPException(
            status_code=400,
            detail="Status 'complete' requires a non-empty evidence_link (URL or ticket reference).",
        )
    if status == "waived" and len(notes) < COMPLIANCE_WAIVER_NOTES_MIN_LEN:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Status 'waived' requires notes of at least {COMPLIANCE_WAIVER_NOTES_MIN_LEN} "
                "characters documenting the waiver rationale and approver context."
            ),
        )


class FederatedApiKeyCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    scopes: Optional[List[str]] = Field(
        default=None,
        description="Optional scope strings, e.g. federated:write",
    )


class ComplianceItemCreateBody(BaseModel):
    framework: str = Field(..., pattern="^(irb|hipaa|gdpr)$")
    control_code: str = Field(..., min_length=1, max_length=80)
    title: str = Field(..., min_length=1, max_length=255)
    tenant_id: Optional[str] = None
    owner_user_id: Optional[str] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None


class ComplianceItemUpdateBody(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(open|in_progress|complete|waived)$")
    evidence_link: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[datetime] = None


@router.post("/federated-api-keys", response_model=Dict[str, Any])
async def create_federated_api_key(
    request: Request,
    body: FederatedApiKeyCreateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """
    Create a federated/automation API key. The **api_key** value is returned once only.
    """
    row, raw = create_service_api_key(db, name=body.name, scopes=body.scopes)
    log_audit(
        db,
        user_id=admin.id,
        action="admin_create_federated_api_key",
        resource=row.id,
        detail={"name": body.name},
        request=request,
    )
    return {
        "id": row.id,
        "name": row.name,
        "key_prefix": row.key_prefix,
        "scopes": row.scopes,
        "api_key": raw,
        "message": "Store this key securely; it cannot be retrieved again.",
    }


@router.get("/federated-api-keys", response_model=Dict[str, Any])
@limiter.limit("120/minute")
async def list_federated_api_keys(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """List keys (prefix only, never the secret)."""
    del request
    del admin
    rows = db.query(ServiceApiKey).order_by(ServiceApiKey.created_at.desc()).all()
    return {
        "keys": [
            {
                "id": r.id,
                "name": r.name,
                "key_prefix": r.key_prefix,
                "scopes": r.scopes,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            }
            for r in rows
        ]
    }


@router.delete("/federated-api-keys/{key_id}", response_model=Dict[str, Any])
@limiter.limit("30/minute")
async def revoke_federated_api_key(
    request: Request,
    key_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    row = db.query(ServiceApiKey).filter(ServiceApiKey.id == key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Key not found")
    row.is_active = False
    db.commit()
    log_audit(
        db,
        user_id=admin.id,
        action="admin_revoke_federated_api_key",
        resource=key_id,
        detail={},
        request=request,
    )
    return {"id": key_id, "status": "revoked"}


@router.post("/compliance/checklist-items", response_model=Dict[str, Any])
@limiter.limit("30/minute")
async def create_compliance_item(
    request: Request,
    body: ComplianceItemCreateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    owner_uid = None
    if body.owner_user_id:
        try:
            owner_uid = uuid.UUID(body.owner_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid owner_user_id")
    row = ComplianceChecklistItem(
        tenant_id=body.tenant_id,
        framework=body.framework.lower(),
        control_code=body.control_code.strip(),
        title=body.title.strip(),
        owner_user_id=owner_uid,
        due_date=body.due_date,
        notes=body.notes,
        status="open",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_audit(
        db,
        user_id=admin.id,
        action="admin_create_compliance_item",
        resource=row.id,
        detail={"framework": row.framework, "control_code": row.control_code},
        request=request,
    )
    return {"id": row.id, "status": row.status}


@router.get("/compliance/checklist-items", response_model=Dict[str, Any])
@limiter.limit("120/minute")
async def list_compliance_items(
    request: Request,
    framework: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    del request
    q = db.query(ComplianceChecklistItem).order_by(ComplianceChecklistItem.created_at.desc())
    q = apply_tenant_scope(q, ComplianceChecklistItem, user)
    if framework:
        q = q.filter(ComplianceChecklistItem.framework == framework.lower())
    rows = q.limit(300).all()
    return {
        "items": [
            {
                "id": r.id,
                "tenant_id": r.tenant_id,
                "framework": r.framework,
                "control_code": r.control_code,
                "title": r.title,
                "status": r.status,
                "evidence_link": r.evidence_link,
                "notes": r.notes,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "owner_user_id": str(r.owner_user_id) if r.owner_user_id else None,
            }
            for r in rows
        ]
    }


@router.patch("/compliance/checklist-items/{item_id}", response_model=Dict[str, Any])
@limiter.limit("60/minute")
async def update_compliance_item(
    request: Request,
    item_id: str,
    body: ComplianceItemUpdateBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(ComplianceChecklistItem).filter(ComplianceChecklistItem.id == item_id)
    q = apply_tenant_scope(q, ComplianceChecklistItem, user)
    row = q.first()
    if not row:
        raise HTTPException(status_code=404, detail="Compliance checklist item not found")
    if body.status is not None and getattr(user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update checklist status")
    if body.status is not None:
        row.status = body.status
    if body.evidence_link is not None:
        row.evidence_link = body.evidence_link
    if body.notes is not None:
        row.notes = body.notes
    if body.due_date is not None:
        row.due_date = body.due_date
    _validate_compliance_item_evidence(row)
    db.commit()
    log_audit(
        db,
        user_id=user.id,
        action="compliance_item_update",
        resource=row.id,
        detail={"status": row.status},
        request=request,
    )
    return {"id": row.id, "status": row.status}
