"""
Tenant management API routes.

These routes provide a minimal CRUD surface that matches the Week 5
multi-tenant description (create, list, get, update, delete tenants).
Admin/authorization checks should be wired in via the existing auth layer.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.tenant_model import Tenant
from app.models.user_model import User
from app.services.tenant_service import TenantManagementService

router = APIRouter()


class TenantCreate(BaseModel):
    id: str
    name: str


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    is_active: bool


def get_tenant_service(db: Session = Depends(get_db)) -> TenantManagementService:
    return TenantManagementService(db=db)


@router.post("/", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    service: TenantManagementService = Depends(get_tenant_service),
    admin: User = Depends(require_roles("admin")),
):
    del admin
    if service.get_tenant(payload.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant with this ID already exists",
        )
    tenant = service.create_tenant(tenant_id=payload.id, name=payload.name)
    return tenant


@router.get("/", response_model=List[TenantRead])
def list_tenants(
    service: TenantManagementService = Depends(get_tenant_service),
    admin: User = Depends(require_roles("admin")),
):
    del admin
    return service.list_tenants()


@router.get("/{tenant_id}", response_model=TenantRead)
def get_tenant(
    tenant_id: str,
    service: TenantManagementService = Depends(get_tenant_service),
    admin: User = Depends(require_roles("admin")),
):
    del admin
    tenant = service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return tenant


@router.put("/{tenant_id}", response_model=TenantRead)
def update_tenant(
    tenant_id: str,
    payload: TenantUpdate,
    service: TenantManagementService = Depends(get_tenant_service),
    admin: User = Depends(require_roles("admin")),
):
    del admin
    tenant = service.update_tenant(
        tenant_id=tenant_id,
        name=payload.name,
        is_active=payload.is_active,
    )
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return tenant


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: str,
    service: TenantManagementService = Depends(get_tenant_service),
    admin: User = Depends(require_roles("admin")),
):
    del admin
    ok = service.delete_tenant(tenant_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return None
