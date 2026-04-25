"""
Database models for biomarker results and annotations.

This module defines the SQLAlchemy models for storing biomarker discovery results,
statistical metrics, and clinical annotations.
"""

from datetime import datetime
from enum import Enum

import numpy as np
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
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class BiomarkerType(str, Enum):
    """Enumeration for biomarker types."""

    PROGNOSTIC = "prognostic"
    PREDICTIVE = "predictive"
    DIAGNOSTIC = "diagnostic"
    RESPONSE = "response"


class EvidenceLevel(str, Enum):
    """Enumeration for evidence levels."""

    LEVEL_1 = "level_1"  # FDA-approved
    LEVEL_2 = "level_2"  # Standard care
    LEVEL_3 = "level_3"  # Clinical evidence
    LEVEL_4 = "level_4"  # Biological evidence
    LEVEL_5 = "level_5"  # Preclinical evidence


class BiomarkerResult(Base):
    """Model for storing biomarker discovery results."""

    __tablename__ = "biomarker_results"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Gene information
    gene_symbol = Column(String(20), nullable=False)
    ensembl_id = Column(String(20))
    gene_name = Column(String(200))
    chromosome = Column(String(10))
    start_position = Column(Integer)
    end_position = Column(Integer)
    strand = Column(String(1))

    # Statistical results
    p_value = Column(Float)
    adjusted_p_value = Column(Float)
    log2_fold_change = Column(Float)
    effect_size = Column(Float)
    effect_size_type = Column(String(20))  # cohens_d, cliffs_delta, etc.

    # Machine learning results
    feature_importance = Column(Float)
    selection_frequency = Column(Float)  # Stability selection frequency
    model_performance = Column(JSON)  # AUC, accuracy, etc. per model

    # Biomarker classification
    biomarker_type = Column(String(20))
    evidence_level = Column(String(20))
    confidence_score = Column(Float)  # 0.0 to 1.0

    # Clinical relevance
    clinical_significance = Column(String(50))
    therapeutic_relevance = Column(Text)
    prognostic_value = Column(Text)

    # Validation information
    validation_status = Column(String(20))  # validated, candidate, rejected
    external_validation = Column(JSON)  # Results from external datasets
    literature_support = Column(JSON)  # PubMed references and evidence

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    analysis_run = relationship("AnalysisRun", back_populates="biomarker_results")
    annotations = relationship("BiomarkerAnnotation", back_populates="biomarker_result")
    pathway_enrichments = relationship(
        "PathwayEnrichment", back_populates="biomarker_result"
    )

    def __repr__(self):
        return f"<BiomarkerResult(gene='{self.gene_symbol}', p_value={self.p_value:.2e}, log2fc={self.log2_fold_change:.2f})>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "gene_symbol": self.gene_symbol,
            "ensembl_id": self.ensembl_id,
            "gene_name": self.gene_name,
            "chromosome": self.chromosome,
            "p_value": self.p_value,
            "adjusted_p_value": self.adjusted_p_value,
            "log2_fold_change": self.log2_fold_change,
            "effect_size": self.effect_size,
            "effect_size_type": self.effect_size_type,
            "feature_importance": self.feature_importance,
            "selection_frequency": self.selection_frequency,
            "model_performance": self.model_performance,
            "biomarker_type": self.biomarker_type,
            "evidence_level": self.evidence_level,
            "confidence_score": self.confidence_score,
            "clinical_significance": self.clinical_significance,
            "therapeutic_relevance": self.therapeutic_relevance,
            "prognostic_value": self.prognostic_value,
            "validation_status": self.validation_status,
            "external_validation": self.external_validation,
            "literature_support": self.literature_support,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_significant(self, threshold: float = 0.05) -> bool:
        """Check if biomarker is statistically significant."""
        return self.adjusted_p_value is not None and self.adjusted_p_value < threshold

    def get_rank_score(self) -> float:
        """Calculate composite ranking score."""
        if not self.p_value or not self.feature_importance:
            return 0.0

        # Combine statistical significance and ML importance
        significance_score = -np.log10(self.p_value) if self.p_value > 0 else 10
        importance_score = self.feature_importance or 0.0

        # Weighted combination (can be adjusted)
        return 0.6 * significance_score + 0.4 * importance_score


class BiomarkerAnnotation(Base):
    """Model for storing external database annotations for biomarkers."""

    __tablename__ = "biomarker_annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_result_id = Column(
        Integer, ForeignKey("biomarker_results.id"), nullable=False
    )

    # Annotation source
    database = Column(String(50), nullable=False)  # COSMIC, ClinVar, OncoKB, etc.
    annotation_type = Column(String(50))  # mutation, expression, pathway, etc.

    # Annotation data
    annotation_id = Column(String(100))  # External database ID
    annotation_value = Column(Text)  # The actual annotation
    confidence_score = Column(Float)  # Confidence in the annotation

    # Metadata
    source_url = Column(String(500))
    last_updated = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Additional context
    meta_data = Column(JSON)  # Additional annotation-specific data

    # Relationship
    biomarker_result = relationship("BiomarkerResult", back_populates="annotations")

    def __repr__(self):
        return f"<BiomarkerAnnotation(gene='{self.biomarker_result.gene_symbol}', database='{self.database}', type='{self.annotation_type}')>"


class PathwayEnrichment(Base):
    """Model for storing pathway enrichment results."""

    __tablename__ = "pathway_enrichments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_result_id = Column(
        Integer, ForeignKey("biomarker_results.id"), nullable=False
    )

    # Pathway information
    pathway_id = Column(String(50), nullable=False)  # KEGG, Reactome ID
    pathway_name = Column(String(200), nullable=False)
    pathway_database = Column(String(50))  # KEGG, Reactome, GO

    # Enrichment statistics
    enrichment_score = Column(Float)
    p_value = Column(Float)
    adjusted_p_value = Column(Float)
    odds_ratio = Column(Float)
    confidence_interval_lower = Column(Float)
    confidence_interval_upper = Column(Float)

    # Gene set information
    genes_in_pathway = Column(Integer)
    significant_genes = Column(Integer)
    gene_list = Column(JSON)  # List of genes in the pathway

    # Visualization data
    enrichment_plot_data = Column(JSON)  # Data for enrichment plots

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    biomarker_result = relationship(
        "BiomarkerResult", back_populates="pathway_enrichments"
    )

    def __repr__(self):
        return f"<PathwayEnrichment(pathway='{self.pathway_name}', enrichment_score={self.enrichment_score:.3f})>"


class SurvivalAnalysis(Base):
    """Model for storing survival analysis results."""

    __tablename__ = "survival_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_result_id = Column(
        Integer, ForeignKey("biomarker_results.id"), nullable=False
    )

    # Survival endpoint
    endpoint_type = Column(String(50))  # overall_survival, disease_free_survival, etc.

    # Cox regression results
    hazard_ratio = Column(Float)
    hazard_ratio_ci_lower = Column(Float)
    hazard_ratio_ci_upper = Column(Float)
    p_value = Column(Float)
    concordance_index = Column(Float)

    # Kaplan-Meier results
    median_survival_high = Column(Float)
    median_survival_low = Column(Float)
    logrank_p_value = Column(Float)

    # Risk stratification
    risk_groups = Column(JSON)  # High/low risk group assignments
    cutoff_value = Column(Float)  # Optimal cutoff for risk stratification

    # Visualization data
    survival_plot_data = Column(JSON)  # Data for survival curves

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    biomarker_result = relationship("BiomarkerResult")

    def __repr__(self):
        return f"<SurvivalAnalysis(gene='{self.biomarker_result.gene_symbol}', hr={self.hazard_ratio:.2f}, p={self.p_value:.2e})>"


class ModelResult(Base):
    """Model for storing machine learning model results."""

    __tablename__ = "model_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Model information
    model_type = Column(
        String(50), nullable=False
    )  # random_forest, logistic_regression, etc.
    model_name = Column(String(100))
    model_parameters = Column(JSON)  # Hyperparameters used

    # Performance metrics
    training_auc = Column(Float)
    validation_auc = Column(Float)
    test_auc = Column(Float)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)

    # Cross-validation results
    cv_scores = Column(JSON)  # Cross-validation scores
    cv_mean = Column(Float)
    cv_std = Column(Float)

    # Feature importance
    feature_importance = Column(JSON)  # Feature importance scores
    top_features = Column(JSON)  # List of top features

    # Model interpretation
    shap_values = Column(JSON)  # SHAP values for interpretability
    permutation_importance = Column(JSON)  # Permutation importance scores

    # Model file
    model_file_path = Column(String(500))  # Path to saved model
    model_size_mb = Column(Float)

    # Metadata
    training_time_seconds = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    analysis_run = relationship("AnalysisRun", back_populates="model_results")

    def __repr__(self):
        return f"<ModelResult(model='{self.model_type}', cv_auc={self.cv_mean:.3f}±{self.cv_std:.3f})>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "model_type": self.model_type,
            "model_name": self.model_name,
            "model_parameters": self.model_parameters,
            "training_auc": self.training_auc,
            "validation_auc": self.validation_auc,
            "test_auc": self.test_auc,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "cv_scores": self.cv_scores,
            "cv_mean": self.cv_mean,
            "cv_std": self.cv_std,
            "feature_importance": self.feature_importance,
            "top_features": self.top_features,
            "shap_values": self.shap_values,
            "permutation_importance": self.permutation_importance,
            "model_file_path": self.model_file_path,
            "model_size_mb": self.model_size_mb,
            "training_time_seconds": self.training_time_seconds,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LiteratureEvidence(Base):
    """Model for storing literature evidence for biomarkers."""

    __tablename__ = "literature_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    biomarker_result_id = Column(
        Integer, ForeignKey("biomarker_results.id"), nullable=False
    )

    # Publication information
    pubmed_id = Column(String(20))
    title = Column(Text)
    authors = Column(Text)
    journal = Column(String(200))
    publication_date = Column(DateTime(timezone=True))

    # Evidence details
    evidence_type = Column(String(50))  # experimental, clinical, review, etc.
    cancer_type = Column(String(100))
    sample_size = Column(Integer)
    evidence_strength = Column(String(20))  # strong, moderate, weak

    # Biomarker-specific findings
    finding_summary = Column(Text)
    statistical_significance = Column(Boolean)
    effect_direction = Column(String(20))  # up, down, mixed
    clinical_relevance = Column(Text)

    # Metadata
    relevance_score = Column(Float)  # 0.0 to 1.0
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    biomarker_result = relationship("BiomarkerResult")

    def __repr__(self):
        return f"<LiteratureEvidence(pmid='{self.pubmed_id}', title='{self.title[:50]}...')>"
