"""
Database models for analysis runs and status tracking.

This module defines the SQLAlchemy models for tracking biomarker analysis runs,
their status, and associated metadata.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class RunStatus(str, Enum):
    """Enumeration for analysis run status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisType(str, Enum):
    """Enumeration for analysis types."""

    DIFFERENTIAL_EXPRESSION = "differential_expression"
    SURVIVAL_ANALYSIS = "survival_analysis"
    ML_PREDICTION = "ml_prediction"
    PATHWAY_ENRICHMENT = "pathway_enrichment"
    INTEGRATED_ANALYSIS = "integrated_analysis"


class AnalysisRun(Base):
    """Model for tracking biomarker analysis runs."""

    __tablename__ = "analysis_runs"

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Basic information
    project_name = Column(String(200), nullable=False)
    description = Column(Text)
    cancer_type = Column(String(50))
    investigator = Column(String(100))

    # Analysis configuration
    analysis_type = Column(String(50), nullable=False)
    configuration = Column(JSON)  # Analysis parameters and settings

    # Data information
    expression_file_path = Column(String(500))
    clinical_file_path = Column(String(500))
    mutation_file_path = Column(String(500))
    sample_count = Column(Integer)
    gene_count = Column(Integer)

    # Status tracking
    status = Column(String(20), default=RunStatus.PENDING.value)
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    current_step = Column(String(100))
    error_message = Column(Text)

    # Timing information
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    estimated_completion = Column(DateTime(timezone=True))

    # Results and outputs
    results_summary = Column(JSON)  # Summary statistics
    output_files = Column(JSON)  # Paths to generated files
    report_path = Column(String(500))

    # Performance metrics
    processing_time_seconds = Column(Float)
    memory_usage_mb = Column(Float)
    cpu_usage_percent = Column(Float)

    # User relationship (must match users.id type for PostgreSQL FK)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)

    # Relationships
    user = relationship("User", back_populates="analysis_runs")
    biomarker_results = relationship("BiomarkerResult", back_populates="analysis_run")
    model_results = relationship("ModelResult", back_populates="analysis_run")

    def __repr__(self):
        return f"<AnalysisRun(id='{self.id}', project='{self.project_name}', status='{self.status}')>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "description": self.description,
            "cancer_type": self.cancer_type,
            "investigator": self.investigator,
            "analysis_type": self.analysis_type,
            "configuration": self.configuration,
            "status": self.status,
            "progress": self.progress,
            "current_step": self.current_step,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "estimated_completion": self.estimated_completion.isoformat()
            if self.estimated_completion
            else None,
            "results_summary": self.results_summary,
            "output_files": self.output_files,
            "report_path": self.report_path,
            "processing_time_seconds": self.processing_time_seconds,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "sample_count": self.sample_count,
            "gene_count": self.gene_count,
            "tenant_id": self.tenant_id,
        }

    def update_status(
        self, status: RunStatus, current_step: str = None, progress: float = None
    ):
        """Update run status and progress."""
        self.status = status.value
        if current_step:
            self.current_step = current_step
        if progress is not None:
            self.progress = progress

        # Update timing information
        if status == RunStatus.RUNNING and not self.started_at:
            self.started_at = datetime.utcnow()
        elif status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]:
            self.completed_at = datetime.utcnow()
            if self.started_at:
                self.processing_time_seconds = (
                    self.completed_at - self.started_at
                ).total_seconds()

    def set_error(self, error_message: str):
        """Set error message and update status to failed."""
        self.error_message = error_message
        self.status = RunStatus.FAILED.value
        self.completed_at = datetime.utcnow()

    def is_completed(self) -> bool:
        """Check if analysis is completed."""
        return self.status == RunStatus.COMPLETED.value

    def is_failed(self) -> bool:
        """Check if analysis failed."""
        return self.status == RunStatus.FAILED.value

    def is_running(self) -> bool:
        """Check if analysis is running."""
        return self.status == RunStatus.RUNNING.value


class RunLog(Base):
    """Model for logging analysis run events."""

    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    level = Column(String(20))  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    step = Column(String(100))
    meta_data = Column(JSON)  # Additional context information

    # Relationship
    analysis_run = relationship("AnalysisRun")

    def __repr__(self):
        return f"<RunLog(run_id='{self.run_id}', level='{self.level}', message='{self.message[:50]}...')>"


class RunMetrics(Base):
    """Model for tracking detailed performance metrics during analysis."""

    __tablename__ = "run_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Performance metrics
    cpu_usage_percent = Column(Float)
    memory_usage_mb = Column(Float)
    disk_usage_mb = Column(Float)
    network_io_mb = Column(Float)

    # Analysis-specific metrics
    step_name = Column(String(100))
    step_progress = Column(Float)  # 0.0 to 1.0
    step_duration_seconds = Column(Float)

    # Custom metrics
    custom_metrics = Column(JSON)

    # Relationship
    analysis_run = relationship("AnalysisRun")

    def __repr__(self):
        return f"<RunMetrics(run_id='{self.run_id}', step='{self.step_name}', cpu='{self.cpu_usage_percent}%')>"


class RunArtifact(Base):
    """Model for tracking analysis artifacts and outputs."""

    __tablename__ = "run_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Artifact information
    artifact_type = Column(String(50), nullable=False)  # plot, table, model, report
    artifact_name = Column(String(200), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_mb = Column(Float)
    mime_type = Column(String(100))

    # Metadata
    description = Column(Text)
    tags = Column(JSON)  # List of tags for categorization
    meta_data = Column(JSON)  # Additional artifact-specific metadata

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed = Column(DateTime(timezone=True))

    # Relationship
    analysis_run = relationship("AnalysisRun")

    def __repr__(self):
        return f"<RunArtifact(run_id='{self.run_id}', type='{self.artifact_type}', name='{self.artifact_name}')>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "artifact_type": self.artifact_type,
            "artifact_name": self.artifact_name,
            "file_path": self.file_path,
            "file_size_mb": self.file_size_mb,
            "mime_type": self.mime_type,
            "description": self.description,
            "tags": self.tags,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_accessed": self.last_accessed.isoformat()
            if self.last_accessed
            else None,
        }


class RunConfiguration(Base):
    """Model for storing analysis configurations and parameters."""

    __tablename__ = "run_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Configuration sections
    preprocessing_config = Column(JSON)
    statistical_config = Column(JSON)
    ml_config = Column(JSON)
    validation_config = Column(JSON)
    annotation_config = Column(JSON)
    output_config = Column(JSON)

    # Version information
    config_version = Column(String(20), default="1.0.0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    analysis_run = relationship("AnalysisRun")

    def __repr__(self):
        return f"<RunConfiguration(run_id='{self.run_id}', version='{self.config_version}')>"

    def get_full_config(self) -> dict:
        """Get complete configuration as dictionary."""
        return {
            "preprocessing": self.preprocessing_config or {},
            "statistical": self.statistical_config or {},
            "machine_learning": self.ml_config or {},
            "validation": self.validation_config or {},
            "annotation": self.annotation_config or {},
            "output": self.output_config or {},
            "version": self.config_version,
        }
