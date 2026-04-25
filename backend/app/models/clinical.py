"""
Database models for clinical decision support
"""

from datetime import datetime

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
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class ClinicalGuideline(Base):
    """Clinical guideline model"""

    __tablename__ = "clinical_guidelines"

    id = Column(Integer, primary_key=True, index=True)
    guideline_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    organization = Column(String(200), nullable=False)
    version = Column(String(50), nullable=False)
    publication_date = Column(DateTime, nullable=False, index=True)
    last_updated = Column(DateTime, nullable=False, index=True)
    disease_focus = Column(String(200), nullable=False, index=True)
    biomarker_focus = Column(String(200), nullable=True, index=True)
    evidence_level = Column(String(10), nullable=False)  # A, B, C, D
    recommendation_strength = Column(
        String(20), nullable=False
    )  # strong, moderate, weak
    guideline_text = Column(Text, nullable=False)
    implementation_notes = Column(Text, nullable=True)
    references = Column(JSON, nullable=True)
    meta_data = Column(JSON, nullable=True)


class ClinicalEvidence(Base):
    """Clinical evidence model"""

    __tablename__ = "clinical_evidence"

    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(String(100), unique=True, nullable=False, index=True)
    biomarker = Column(String(100), nullable=False, index=True)
    disease = Column(String(100), nullable=False, index=True)
    evidence_level = Column(String(10), nullable=False, index=True)  # A, B, C, D
    clinical_significance = Column(
        String(20), nullable=False, index=True
    )  # high, moderate, low
    study_type = Column(
        String(50), nullable=False, index=True
    )  # RCT, cohort, case-control, meta-analysis
    study_title = Column(String(500), nullable=False)
    authors = Column(String(500), nullable=True)
    journal = Column(String(200), nullable=True)
    publication_year = Column(Integer, nullable=False, index=True)
    sample_size = Column(Integer, nullable=False)
    p_value = Column(Float, nullable=False)
    effect_size = Column(Float, nullable=False)
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    journal_impact_factor = Column(Float, nullable=True)
    citation_count = Column(Integer, default=0)
    doi = Column(String(200), nullable=True)
    pmid = Column(String(50), nullable=True)
    abstract = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)
    meta_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)


class ClinicalRecommendation(Base):
    """Clinical recommendation model"""

    __tablename__ = "clinical_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    recommendation_id = Column(String(100), unique=True, nullable=False, index=True)
    biomarker = Column(String(100), nullable=False, index=True)
    clinical_context = Column(String(200), nullable=False, index=True)
    recommendation_text = Column(Text, nullable=False)
    evidence_level = Column(String(10), nullable=False, index=True)
    recommendation_strength = Column(String(20), nullable=False, index=True)
    contraindications = Column(JSON, nullable=True)
    monitoring_requirements = Column(JSON, nullable=True)
    follow_up_period = Column(Integer, nullable=True)  # months
    cost_effectiveness = Column(String(50), nullable=True)
    implementation_notes = Column(Text, nullable=True)
    supporting_evidence = Column(JSON, nullable=True)  # List of evidence IDs
    guideline_references = Column(JSON, nullable=True)  # List of guideline IDs
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_active = Column(Boolean, default=True, index=True)


class ClinicalValidation(Base):
    """Clinical validation model"""

    __tablename__ = "clinical_validations"

    id = Column(Integer, primary_key=True, index=True)
    validation_id = Column(String(100), unique=True, nullable=False, index=True)
    biomarker = Column(String(100), nullable=False, index=True)
    clinical_decision = Column(Text, nullable=False)
    patient_context = Column(JSON, nullable=False)
    validation_score = Column(Float, nullable=False, index=True)
    guideline_compliance = Column(Boolean, nullable=False, index=True)
    evidence_support = Column(Boolean, nullable=False, index=True)
    guideline_validation = Column(JSON, nullable=True)
    evidence_validation = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    validated_by = Column(String(100), nullable=True, index=True)
    validated_at = Column(DateTime, default=datetime.utcnow, index=True)
    meta_data = Column(JSON, nullable=True)


class ClinicalOutcome(Base):
    """Clinical outcome model"""

    __tablename__ = "clinical_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    outcome_id = Column(String(100), unique=True, nullable=False, index=True)
    patient_id = Column(String(100), nullable=False, index=True)
    biomarker = Column(String(100), nullable=False, index=True)
    clinical_decision = Column(Text, nullable=False)
    outcome_type = Column(
        String(50), nullable=False, index=True
    )  # survival, response, progression
    outcome_value = Column(Float, nullable=False)
    outcome_unit = Column(String(50), nullable=True)
    follow_up_period = Column(Integer, nullable=True)  # months
    outcome_date = Column(DateTime, nullable=False, index=True)
    is_positive = Column(Boolean, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    meta_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ClinicalDecisionLog(Base):
    """Clinical decision log model"""

    __tablename__ = "clinical_decision_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    patient_id = Column(String(100), nullable=False, index=True)
    biomarker = Column(String(100), nullable=False, index=True)
    clinical_decision = Column(Text, nullable=False)
    decision_rationale = Column(Text, nullable=True)
    evidence_used = Column(JSON, nullable=True)
    guidelines_referenced = Column(JSON, nullable=True)
    validation_score = Column(Float, nullable=True)
    decision_timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    outcome_tracking = Column(Boolean, default=False)
    meta_data = Column(JSON, nullable=True)


class ClinicalQualityMetric(Base):
    """Clinical quality metric model"""

    __tablename__ = "clinical_quality_metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_id = Column(String(100), unique=True, nullable=False, index=True)
    metric_name = Column(String(200), nullable=False)
    metric_type = Column(
        String(50), nullable=False, index=True
    )  # compliance, outcome, process
    biomarker = Column(String(100), nullable=False, index=True)
    disease_context = Column(String(200), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(50), nullable=True)
    target_value = Column(Float, nullable=True)
    measurement_period = Column(
        String(50), nullable=False
    )  # daily, weekly, monthly, yearly
    measurement_date = Column(DateTime, nullable=False, index=True)
    data_source = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    meta_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ClinicalAuditTrail(Base):
    """Clinical audit trail model"""

    __tablename__ = "clinical_audit_trails"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    action = Column(
        String(100), nullable=False, index=True
    )  # create, update, delete, view
    resource_type = Column(
        String(50), nullable=False, index=True
    )  # guideline, evidence, recommendation
    resource_id = Column(String(100), nullable=False, index=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    change_reason = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    meta_data = Column(JSON, nullable=True)
