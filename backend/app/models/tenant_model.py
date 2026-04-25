"""
Tenant model for multi-tenant foundation.

This is a minimal implementation to support the Week 5 multi-tenant
architecture description: it provides a tenant table and basic metadata
that can be referenced from user and data models.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String

from ..core.database import Base


class Tenant(Base):
    """Represents an organizational tenant."""

    __tablename__ = "tenants"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
