"""
Tenant management service.

This is a lightweight `TenantManagementService` that supports basic CRUD
operations and lookup by ID. It is intended to satisfy the Week 5 multi-tenant
foundation description without tightly coupling business logic to any
particular auth implementation.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.tenant_model import Tenant


class TenantManagementService:
    """Service for managing tenants."""

    def __init__(self, db: Session):
        self.db = db

    def list_tenants(self) -> List[Tenant]:
        return self.db.query(Tenant).order_by(Tenant.created_at.desc()).all()

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def create_tenant(self, tenant_id: str, name: str) -> Tenant:
        tenant = Tenant(id=tenant_id, name=name, is_active=True)
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def update_tenant(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Tenant]:
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return None

        if name is not None:
            tenant.name = name
        if is_active is not None:
            tenant.is_active = is_active

        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def delete_tenant(self, tenant_id: str) -> bool:
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False

        self.db.delete(tenant)
        self.db.commit()
        return True
