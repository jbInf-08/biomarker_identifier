"""
Database models for storing omics data and clinical information.

This module defines the SQLAlchemy models for storing gene expression data,
clinical data, mutation data, and other omics data types.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class DataType(str, Enum):
    """Enumeration for data types."""

    EXPRESSION = "expression"
    CLINICAL = "clinical"
    MUTATION = "mutation"
    METHYLATION = "methylation"
    PROTEIN = "protein"
    METABOLITE = "metabolite"


class ExpressionData(Base):
    """Model for storing gene expression data."""

    __tablename__ = "expression_data"

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

    # Sample information
    sample_id = Column(String(50), nullable=False)
    patient_id = Column(String(50))

    # Expression values
    raw_expression = Column(Float)
    normalized_expression = Column(Float)
    log2_expression = Column(Float)
    tpm_expression = Column(Float)
    fpkm_expression = Column(Float)

    # Quality metrics
    quality_score = Column(Float)
    detection_p_value = Column(Float)
    is_expressed = Column(Boolean)

    # Metadata
    data_source = Column(String(100))  # RNA-seq, microarray, etc.
    platform = Column(String(100))  # Sequencing platform or array type
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    analysis_run = relationship("AnalysisRun")

    # Indexes for performance
    __table_args__ = (
        Index("idx_expression_gene_sample", "gene_symbol", "sample_id"),
        Index("idx_expression_run_gene", "run_id", "gene_symbol"),
        Index("idx_expression_run_sample", "run_id", "sample_id"),
    )

    def __repr__(self):
        return f"<ExpressionData(gene='{self.gene_symbol}', sample='{self.sample_id}', expression={self.normalized_expression:.2f})>"


class ClinicalData(Base):
    """Model for storing clinical and phenotypic data."""

    __tablename__ = "clinical_data"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Patient and sample information
    patient_id = Column(String(50), nullable=False)
    sample_id = Column(String(50), nullable=False)

    # Demographics
    age = Column(Integer)
    gender = Column(String(10))
    race = Column(String(50))
    ethnicity = Column(String(50))

    # Clinical information
    cancer_type = Column(String(100))
    cancer_subtype = Column(String(100))
    stage = Column(String(20))
    grade = Column(String(20))
    tumor_size = Column(Float)
    lymph_node_status = Column(String(20))
    metastasis_status = Column(String(20))

    # Treatment information
    treatment_type = Column(String(100))
    treatment_response = Column(String(50))
    treatment_duration = Column(Float)

    # Survival data
    survival_status = Column(Boolean)  # True = alive, False = dead
    survival_time_months = Column(Float)
    disease_free_survival_months = Column(Float)
    progression_free_survival_months = Column(Float)

    # Additional clinical variables
    bmi = Column(Float)
    smoking_status = Column(String(20))
    alcohol_consumption = Column(String(20))
    family_history = Column(Boolean)

    # Laboratory values
    lab_values = Column(JSON)  # Store additional lab values as JSON

    # Metadata
    data_source = Column(String(100))
    collection_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    analysis_run = relationship("AnalysisRun")

    # Indexes for performance
    __table_args__ = (
        Index("idx_clinical_patient_sample", "patient_id", "sample_id"),
        Index("idx_clinical_run_patient", "run_id", "patient_id"),
        Index("idx_clinical_survival", "survival_status", "survival_time_months"),
    )

    def __repr__(self):
        return f"<ClinicalData(patient='{self.patient_id}', sample='{self.sample_id}', cancer_type='{self.cancer_type}')>"


class MutationData(Base):
    """Model for storing somatic mutation data."""

    __tablename__ = "mutation_data"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Sample information
    sample_id = Column(String(50), nullable=False)
    patient_id = Column(String(50))

    # Gene information
    gene_symbol = Column(String(20), nullable=False)
    ensembl_id = Column(String(20))

    # Mutation details
    chromosome = Column(String(10))
    position = Column(Integer)
    reference_allele = Column(String(200))
    alternate_allele = Column(String(200))
    mutation_type = Column(String(50))  # SNV, INDEL, CNV, etc.
    variant_type = Column(String(50))  # missense, nonsense, frameshift, etc.

    # Protein change
    amino_acid_change = Column(String(200))
    protein_position = Column(Integer)

    # Frequency and coverage
    variant_allele_frequency = Column(Float)
    read_depth = Column(Integer)
    alternate_reads = Column(Integer)
    reference_reads = Column(Integer)

    # Clinical significance
    clinical_significance = Column(String(50))
    cosmic_id = Column(String(20))
    clinvar_id = Column(String(20))

    # Additional annotations
    annotations = Column(JSON)  # Additional mutation annotations

    # Metadata
    data_source = Column(String(100))  # WGS, WES, targeted sequencing
    sequencing_platform = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    analysis_run = relationship("AnalysisRun")

    # Indexes for performance
    __table_args__ = (
        Index("idx_mutation_gene_sample", "gene_symbol", "sample_id"),
        Index("idx_mutation_run_gene", "run_id", "gene_symbol"),
        Index("idx_mutation_position", "chromosome", "position"),
    )

    def __repr__(self):
        return f"<MutationData(gene='{self.gene_symbol}', mutation='{self.mutation_type}', sample='{self.sample_id}')>"


class MethylationData(Base):
    """Model for storing DNA methylation data."""

    __tablename__ = "methylation_data"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Sample information
    sample_id = Column(String(50), nullable=False)
    patient_id = Column(String(50))

    # Probe information
    probe_id = Column(String(50), nullable=False)
    gene_symbol = Column(String(20))
    ensembl_id = Column(String(20))

    # Genomic location
    chromosome = Column(String(10))
    position = Column(Integer)
    cpg_context = Column(String(20))  # CpG, CHG, CHH

    # Methylation values
    beta_value = Column(Float)  # 0-1 methylation level
    m_value = Column(Float)  # Logit transformation of beta
    detection_p_value = Column(Float)

    # Quality metrics
    bead_count = Column(Integer)
    quality_score = Column(Float)

    # Additional annotations
    annotations = Column(JSON)  # Additional methylation annotations

    # Metadata
    data_source = Column(String(100))  # 450K, EPIC, etc.
    platform = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    analysis_run = relationship("AnalysisRun")

    # Indexes for performance
    __table_args__ = (
        Index("idx_methylation_probe_sample", "probe_id", "sample_id"),
        Index("idx_methylation_run_gene", "run_id", "gene_symbol"),
        Index("idx_methylation_position", "chromosome", "position"),
    )

    def __repr__(self):
        return f"<MethylationData(probe='{self.probe_id}', gene='{self.gene_symbol}', beta={self.beta_value:.3f})>"


class ProteinData(Base):
    """Model for storing protein expression data."""

    __tablename__ = "protein_data"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Sample information
    sample_id = Column(String(50), nullable=False)
    patient_id = Column(String(50))

    # Protein information
    protein_symbol = Column(String(20), nullable=False)
    protein_name = Column(String(200))
    uniprot_id = Column(String(20))

    # Expression values
    raw_expression = Column(Float)
    normalized_expression = Column(Float)
    log2_expression = Column(Float)

    # Quality metrics
    quality_score = Column(Float)
    detection_p_value = Column(Float)
    is_detected = Column(Boolean)

    # Additional annotations
    annotations = Column(JSON)  # Additional protein annotations

    # Metadata
    data_source = Column(String(100))  # Mass spec, antibody-based, etc.
    platform = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    analysis_run = relationship("AnalysisRun")

    # Indexes for performance
    __table_args__ = (
        Index("idx_protein_symbol_sample", "protein_symbol", "sample_id"),
        Index("idx_protein_run_symbol", "run_id", "protein_symbol"),
    )

    def __repr__(self):
        return f"<ProteinData(protein='{self.protein_symbol}', sample='{self.sample_id}', expression={self.normalized_expression:.2f})>"


class DataQualityMetrics(Base):
    """Model for storing data quality metrics."""

    __tablename__ = "data_quality_metrics"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Sample information
    sample_id = Column(String(50), nullable=False)
    data_type = Column(String(20), nullable=False)  # expression, mutation, etc.

    # Quality metrics
    total_features = Column(Integer)
    detected_features = Column(Integer)
    detection_rate = Column(Float)
    mean_expression = Column(Float)
    median_expression = Column(Float)
    expression_variance = Column(Float)

    # Missing data
    missing_rate = Column(Float)
    missing_features = Column(Integer)

    # Outlier detection
    is_outlier = Column(Boolean)
    outlier_score = Column(Float)
    outlier_reason = Column(String(200))

    # Additional metrics
    quality_metrics = Column(JSON)  # Additional quality metrics

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    analysis_run = relationship("AnalysisRun")

    def __repr__(self):
        return f"<DataQualityMetrics(sample='{self.sample_id}', type='{self.data_type}', detection_rate={self.detection_rate:.2f})>"


class DataProcessingLog(Base):
    """Model for logging data processing steps."""

    __tablename__ = "data_processing_logs"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Processing information
    step_name = Column(String(100), nullable=False)
    step_order = Column(Integer)
    status = Column(String(20))  # started, completed, failed

    # Processing details
    input_file = Column(String(500))
    output_file = Column(String(500))
    processing_time_seconds = Column(Float)

    # Statistics
    input_records = Column(Integer)
    output_records = Column(Integer)
    filtered_records = Column(Integer)

    # Error information
    error_message = Column(Text)
    error_details = Column(JSON)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    analysis_run = relationship("AnalysisRun")

    def __repr__(self):
        return f"<DataProcessingLog(run_id='{self.run_id}', step='{self.step_name}', status='{self.status}')>"


class DataAnnotation(Base):
    """Model for storing data annotations and metadata."""

    __tablename__ = "data_annotations"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"), nullable=False)

    # Annotation information
    annotation_type = Column(String(50), nullable=False)  # gene_info, pathway, etc.
    entity_id = Column(String(50), nullable=False)  # gene symbol, pathway ID, etc.

    # Annotation data
    annotation_key = Column(String(100), nullable=False)
    annotation_value = Column(Text)
    annotation_source = Column(String(100))  # Database or source

    # Confidence and quality
    confidence_score = Column(Float)
    evidence_level = Column(String(20))

    # Additional context
    meta_data = Column(JSON)  # Additional annotation metadata

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True))

    # Relationships
    analysis_run = relationship("AnalysisRun")

    # Indexes for performance
    __table_args__ = (
        Index("idx_annotation_entity", "entity_id", "annotation_type"),
        Index("idx_annotation_run_type", "run_id", "annotation_type"),
    )

    def __repr__(self):
        return f"<DataAnnotation(entity='{self.entity_id}', type='{self.annotation_type}', key='{self.annotation_key}')>"
