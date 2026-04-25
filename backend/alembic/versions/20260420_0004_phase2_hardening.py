"""Phase 2 hardening tables (spark jobs + compliance checklist).

Revision ID: 20260420_0004
Revises: 20260420_0003
Create Date: 2026-04-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260420_0004"
down_revision: Union[str, None] = "20260420_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "spark_jobs"):
        op.create_table(
            "spark_jobs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("app_path", sa.String(500), nullable=False),
            sa.Column("app_args", sa.JSON(), nullable=True),
            sa.Column("conf", sa.JSON(), nullable=True),
            sa.Column("retry_of_job_id", sa.String(36), nullable=True),
            sa.Column("pid", sa.Integer(), nullable=True),
            sa.Column("command", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
            sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
        )
        op.create_index("ix_spark_jobs_pid", "spark_jobs", ["pid"])
        op.create_index("ix_spark_jobs_retry_of_job_id", "spark_jobs", ["retry_of_job_id"])
        op.create_index("ix_spark_jobs_tenant_id", "spark_jobs", ["tenant_id"])
        op.create_index("ix_spark_jobs_user_id", "spark_jobs", ["user_id"])

    if not _table_exists(bind, "compliance_checklist_items"):
        op.create_table(
            "compliance_checklist_items",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("framework", sa.String(32), nullable=False),
            sa.Column("control_code", sa.String(80), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("evidence_link", sa.String(1024), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_compliance_checklist_items_framework",
            "compliance_checklist_items",
            ["framework"],
        )
        op.create_index(
            "ix_compliance_checklist_items_control_code",
            "compliance_checklist_items",
            ["control_code"],
        )
        op.create_index(
            "ix_compliance_checklist_items_tenant_id",
            "compliance_checklist_items",
            ["tenant_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "compliance_checklist_items"):
        op.drop_table("compliance_checklist_items")
    if _table_exists(bind, "spark_jobs"):
        op.drop_table("spark_jobs")
