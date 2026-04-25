"""
Cross-cutting platform models: audit, API keys, interpretation snapshots.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class AuditLog(Base):
    """Structured audit trail for sensitive actions."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    resource = Column(String(120), nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ServiceApiKey(Base):
    """API keys for federated participants / automation (hashed secret)."""

    __tablename__ = "service_api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    key_prefix = Column(String(16), nullable=False, index=True)
    key_hash = Column(String(128), nullable=False)
    scopes = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)


class FederatedIdempotency(Base):
    """Maps client-supplied idempotency keys to federated round IDs."""

    __tablename__ = "federated_idempotency"

    key = Column(String(128), primary_key=True)
    round_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WebhookSubscription(Base):
    """Outbound webhook URLs for integrations (run events, etc.)."""

    __tablename__ = "webhook_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    secret = Column(String(255), nullable=True)
    events = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InterpretationSnapshot(Base):
    """Saved grounded LLM interpretations per run (versioned)."""

    __tablename__ = "interpretation_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    run_id = Column(String(36), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    notes = Column(Text, nullable=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class WebhookDeliveryLog(Base):
    """Outbound webhook attempt + idempotency (at-least-once with dedup key)."""

    __tablename__ = "webhook_delivery_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    webhook_id = Column(String(36), ForeignKey("webhook_subscriptions.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    event = Column(String(80), nullable=False, index=True)
    idempotency_key = Column(String(64), nullable=False, index=True)
    payload_hash = Column(String(64), nullable=False)
    http_status = Column(Integer, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # sent | failed | dead
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ResearchProject(Base):
    """Shared research workspace (tenant-scoped)."""

    __tablename__ = "research_projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ProjectMember(Base):
    """Membership + coarse role for collaborative research."""

    __tablename__ = "project_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("research_projects.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(32), default="viewer", nullable=False)  # viewer | editor | admin
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SparkJob(Base):
    """Submitted Spark jobs with lightweight lifecycle tracking."""

    __tablename__ = "spark_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)
    app_path = Column(String(500), nullable=False)
    app_args = Column(JSON, nullable=True)
    conf = Column(JSON, nullable=True)
    retry_of_job_id = Column(String(36), nullable=True, index=True)
    pid = Column(Integer, nullable=True, index=True)
    command = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="submitted")  # submitted | running | finished | failed | unknown
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_error = Column(Text, nullable=True)


class ComplianceChecklistItem(Base):
    """Auditable compliance checklist item (IRB/HIPAA/GDPR controls)."""

    __tablename__ = "compliance_checklist_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)
    framework = Column(String(32), nullable=False, index=True)  # irb | hipaa | gdpr
    control_code = Column(String(80), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="open")  # open | in_progress | complete | waived
    evidence_link = Column(String(1024), nullable=True)
    notes = Column(Text, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
