"""Create legacy run telemetry tables via Alembic.

Revision ID: 20260420_0003
Revises: 20250417_0002
Create Date: 2026-04-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260420_0003"
down_revision: Union[str, None] = "20250417_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "run_logs"):
        op.create_table(
            "run_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("analysis_runs.id"), nullable=False),
            sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("level", sa.String(20), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("step", sa.String(100), nullable=True),
            sa.Column("meta_data", sa.JSON(), nullable=True),
        )

    if not _table_exists(bind, "run_metrics"):
        op.create_table(
            "run_metrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("analysis_runs.id"), nullable=False),
            sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("cpu_usage_percent", sa.Float(), nullable=True),
            sa.Column("memory_usage_mb", sa.Float(), nullable=True),
            sa.Column("disk_usage_mb", sa.Float(), nullable=True),
            sa.Column("network_io_mb", sa.Float(), nullable=True),
            sa.Column("step_name", sa.String(100), nullable=True),
            sa.Column("step_progress", sa.Float(), nullable=True),
            sa.Column("step_duration_seconds", sa.Float(), nullable=True),
            sa.Column("custom_metrics", sa.JSON(), nullable=True),
        )

    if not _table_exists(bind, "run_artifacts"):
        op.create_table(
            "run_artifacts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("analysis_runs.id"), nullable=False),
            sa.Column("artifact_type", sa.String(50), nullable=False),
            sa.Column("artifact_name", sa.String(200), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("file_size_mb", sa.Float(), nullable=True),
            sa.Column("mime_type", sa.String(100), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("meta_data", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("last_accessed", sa.DateTime(timezone=True), nullable=True),
        )

    if not _table_exists(bind, "run_configurations"):
        op.create_table(
            "run_configurations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("analysis_runs.id"), nullable=False),
            sa.Column("preprocessing_config", sa.JSON(), nullable=True),
            sa.Column("statistical_config", sa.JSON(), nullable=True),
            sa.Column("ml_config", sa.JSON(), nullable=True),
            sa.Column("validation_config", sa.JSON(), nullable=True),
            sa.Column("annotation_config", sa.JSON(), nullable=True),
            sa.Column("output_config", sa.JSON(), nullable=True),
            sa.Column("config_version", sa.String(20), nullable=True, server_default="1.0.0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    for name in ("run_configurations", "run_artifacts", "run_metrics", "run_logs"):
        if _table_exists(bind, name):
            op.drop_table(name)
