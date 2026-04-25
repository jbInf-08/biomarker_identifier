"""
Configuration settings for the Cancer Biomarker Identifier application.

This module handles all configuration settings including database connections,
API keys, file paths, and application behavior parameters.
"""

import json
import os
from typing import List, Optional, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path

DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",  # e.g. BIOMARKER_DISABLE_RATE_LIMIT read directly by middleware
    )

    # Application settings
    APP_NAME: str = "Cancer Biomarker Identifier"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API settings
    API_V1_STR: str = "/api/v1"
    BASE_URL: str = "http://localhost:8000"
    # Union[str, List[str]] so .env comma-separated values are not JSON-decoded before validators run
    ALLOWED_ORIGINS: Union[str, List[str]] = ["http://localhost:3000", "http://localhost:8000"]

    # Database settings
    DATABASE_URL: str = "sqlite:///./biomarker_app.db"
    # SQLAlchemy pool (PostgreSQL only; tune to workers × pool_size < max_connections)
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "biomarker_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"

    # Redis settings (for Celery)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Root data directory (uploads, pipeline outputs)
    DATA_DIR: str = "data"

    # File storage settings
    UPLOAD_DIR: str = "data/raw"
    PROCESSED_DIR: str = "data/processed"
    REPORTS_DIR: str = "app/reports"
    EXPORT_DIR: str = "data/exports"
    VISUALIZATION_DIR: str = "data/visualizations"
    MODELS_DIR: str = "app/models"
    STATIC_DIR: str = "app/static"
    TEMP_DIR: str = "data/temp"

    # External API settings
    COSMIC_API_KEY: Optional[str] = None
    ONCOKB_API_KEY: Optional[str] = None
    PUBMED_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    HUGGINGFACE_HUB_TOKEN: Optional[str] = None

    # Analysis settings
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    MAX_SAMPLES: int = 1000
    MAX_GENES: int = 50000
    DEFAULT_RANDOM_SEED: int = 42

    # Machine learning settings
    CV_FOLDS: int = 5
    # API: optional PyTorch / GCN paths (disable on slim deploy images)
    ML_ENABLE_FOCAL_LOSS: bool = True
    ML_ENABLE_SHALLOW_GCN: bool = True
    STABILITY_BOOTSTRAPS: int = 100
    PERMUTATION_TESTS: int = 100
    FEATURE_SELECTION_THRESHOLD: float = 0.6

    # Preprocessing settings
    MIN_VARIANCE_GENES: int = 10000
    MIN_EXPRESSION_THRESHOLD: float = 1.0
    MAX_MISSING_RATE: float = 0.1
    BATCH_CORRECTION_METHOD: str = "combat"  # or "limma" or None

    # Statistical testing settings
    FDR_METHOD: str = "benjamini_hochberg"  # or "bonferroni"
    EFFECT_SIZE_METRIC: str = "cohens_d"  # or "cliffs_delta"

    # Security settings
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/biomarker_app.log"
    # Emit JSON to stdout in production (Docker / log aggregation)
    LOG_JSON: bool = False

    # Readiness: include Celery worker inspect (optional; adds latency)
    HEALTH_CHECK_CELERY: bool = False

    # Deployment / Docker (renamed from ENVIRONMENT, etc. to avoid env conflicts)
    BIOMARKER_ENV: Optional[str] = None
    BIOMARKER_PROMETHEUS_ENABLED: Optional[bool] = None
    BIOMARKER_GRAFANA_ENABLED: Optional[bool] = None
    BIOMARKER_DOCKER_USERNAME: Optional[str] = None

    # Deployment / region (optional; surfaced in health for multi-region ops)
    DEPLOYMENT_REGION: Optional[str] = None

    # Multi-tenant: when True, users with tenant_id must send matching X-Tenant-ID
    MULTI_TENANT_ENFORCE: bool = False

    # Federated / external clients
    FEDERATED_REQUIRE_API_KEY: bool = False
    # Bonawitz-style zero-sum masked tensors (``meta_data.use_bonawitz_mask``) after Fernet
    FEDERATED_BONAWITZ_MASK_AGGREGATION_ENABLED: bool = False
    FEDERATED_CRYPTO_SECURE_AGGREGATION_ENABLED: bool = False
    # Default FedProx proximal term μ (local objective on **clients**; see FederatedConfig)
    FEDERATED_FEDPROX_MU: float = 0.01

    # Raw count DE via R (rpy2 + DESeq2/edgeR); see app/analysis/raw_counts_deseq2.py
    ANALYSIS_ENABLE_RAW_COUNTS_DESEQ2: bool = False

    # Planned: full graph neural feature-learning stage (beyond shallow GCN)
    ML_ENABLE_DEEP_GNN_STAGE: bool = False

    # PubMed E-utilities (optional grounding)
    ENABLE_PUBMED_GROUNDING: bool = False
    NCBI_EMAIL: Optional[str] = None
    NCBI_TOOL: str = "biomarker_identifier"
    NCBI_API_KEY: Optional[str] = None

    # HTTP rate limiting (slowapi)
    RATE_LIMIT_ENABLED: bool = True

    # Production config validation (fail fast when BIOMARKER_ENV=production)
    STRICT_CONFIG_CHECK: bool = False

    # CGAS Integration settings
    CGAS_BASE_URL: str = "http://localhost:5000"
    CGAS_MUTATION_API: str = "/api/mutations"
    CGAS_PATHWAY_API: str = "/api/pathways"
    # When True, /api/cgas/* proxies to ``CGAS_BASE_URL`` (real CGAS or compatible service).
    CGAS_FORWARD_ENABLED: bool = False

    # Spark submit integration (optional; production ETL/large matrix jobs)
    SPARK_SUBMIT_BIN: str = "spark-submit"
    SPARK_MASTER_URL: str = "spark://spark-master:7077"
    SPARK_DEPLOY_MODE: str = "client"  # client | cluster
    SPARK_ENABLED: bool = False

    # Email (optional; export sharing uses these when configured)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@localhost"

    # Report settings
    REPORT_TEMPLATE_DIR: str = "app/reports/templates"
    REPORT_OUTPUT_FORMATS: List[str] = ["html", "pdf"]

    @field_validator("ALLOWED_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Normalize CORS origins from comma-separated string, JSON array, or list."""
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        s = (v or "").strip()
        if not s:
            return ["http://localhost:3000", "http://localhost:8000"]
        if s.startswith("["):
            parsed = json.loads(s)
            if not isinstance(parsed, list):
                raise ValueError("ALLOWED_ORIGINS JSON must be a list")
            return [str(x).strip() for x in parsed if str(x).strip()]
        return [i.strip() for i in s.split(",") if i.strip()]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str]) -> str:
        """Assemble database URL from components."""
        if isinstance(v, str) and v.strip():
            return v
        # Return default when not set or empty
        return "sqlite:///./biomarker_app.db"

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str]) -> str:
        """Assemble Redis URL from components."""
        if isinstance(v, str) and v.strip():
            return v
        return "redis://localhost:6379/0"

    @model_validator(mode="after")
    def validate_production_cors(self) -> "Settings":
        if (self.BIOMARKER_ENV or "").lower() == "production":
            origins = self.ALLOWED_ORIGINS or []
            if any(str(o).strip() == "*" for o in origins):
                raise ValueError(
                    "ALLOWED_ORIGINS must not contain '*' when BIOMARKER_ENV=production "
                    "(browsers reject credentials with wildcard CORS)."
                )
        return self


# Create settings instance
settings = Settings()

# Validate SECRET_KEY in production (skip during testing)
_is_testing = "pytest" in os.environ.get("_", "") or "PYTEST_CURRENT_TEST" in os.environ
if not _is_testing and not settings.DEBUG and settings.SECRET_KEY == DEFAULT_SECRET_KEY:
    raise ValueError(
        "SECRET_KEY must be set to a secure value in production. "
        "Set the SECRET_KEY environment variable."
    )


# Create necessary directories
def create_directories():
    """Create necessary directories for the application."""
    directories = [
        settings.UPLOAD_DIR,
        settings.PROCESSED_DIR,
        settings.REPORTS_DIR,
        settings.EXPORT_DIR,
        settings.VISUALIZATION_DIR,
        settings.MODELS_DIR,
        settings.STATIC_DIR,
        "logs",
        "data/external_sources",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


# Default analysis configuration
DEFAULT_ANALYSIS_CONFIG = {
    "preprocessing": {
        "min_variance_genes": settings.MIN_VARIANCE_GENES,
        "min_expression_threshold": settings.MIN_EXPRESSION_THRESHOLD,
        "max_missing_rate": settings.MAX_MISSING_RATE,
        "log_transform": True,
        "batch_correction": settings.BATCH_CORRECTION_METHOD,
    },
    "statistical_testing": {
        "test_method": "welch_t",  # or "mannwhitney", "anova"
        "fdr_method": settings.FDR_METHOD,
        "effect_size_metric": settings.EFFECT_SIZE_METRIC,
        "multiple_testing_correction": True,
    },
    "machine_learning": {
        "models": ["logistic_l1", "random_forest", "xgboost"],
        "cv_folds": settings.CV_FOLDS,
        "feature_selection": {
            "method": "rfe",  # or "lasso", "mutual_info"
            "n_features": [50, 100, 200],
            "stability_threshold": settings.FEATURE_SELECTION_THRESHOLD,
        },
        "hyperparameter_tuning": {
            "method": "grid_search",  # or "random_search", "bayesian"
            "cv_folds": 3,
        },
    },
    "validation": {
        "cross_validation": {
            "outer_folds": settings.CV_FOLDS,
            "inner_folds": 3,
            "stratified": True,
            "random_state": settings.DEFAULT_RANDOM_SEED,
        },
        "stability_selection": {
            "n_bootstraps": settings.STABILITY_BOOTSTRAPS,
            "selection_threshold": settings.FEATURE_SELECTION_THRESHOLD,
        },
        "permutation_testing": {
            "n_permutations": settings.PERMUTATION_TESTS,
            "random_state": settings.DEFAULT_RANDOM_SEED,
        },
    },
    "annotation": {
        "pathway_databases": ["KEGG", "REACTOME"],
        "clinical_databases": ["COSMIC", "CLINVAR", "ONCOKB"],
        "gsea_analysis": True,
        "literature_search": True,
    },
    # Reserved flags for roadmap items (see docs/PRODUCT_ROADMAP.md)
    "optional_pipeline_stages": {
        "deep_gnn_feature_learning": False,
        "raw_counts_deseq2_edgeR": False,
    },
    "output": {
        "export_csv": True,
        "export_json": True,
        "generate_html_report": True,
        "generate_pdf_report": True,
        "include_visualizations": True,
    },
}

# Model-specific configurations
MODEL_CONFIGS = {
    "logistic_l1": {
        "regularization": [0.01, 0.1, 1.0, 10.0],
        "class_weight": "balanced",
        "max_iter": 1000,
        "solver": "liblinear",
    },
    "linear_svm_rfe": {
        "n_features": [50, 100, 200],
        "class_weight": "balanced",
        "kernel": "linear",
    },
    "random_forest": {
        "n_estimators": 500,
        "max_features": "sqrt",
        "class_weight": "balanced",
        "random_state": settings.DEFAULT_RANDOM_SEED,
    },
    "xgboost": {
        "learning_rate": 0.1,
        "max_depth": 4,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": settings.DEFAULT_RANDOM_SEED,
    },
    "lightgbm": {
        "learning_rate": 0.1,
        "max_depth": 4,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": settings.DEFAULT_RANDOM_SEED,
    },
}

# Pathway database configurations
PATHWAY_DATABASES = {
    "KEGG": {
        "base_url": "https://rest.kegg.org",
        "species": "hsa",  # human
        "enrichment_method": "hypergeometric",
    },
    "REACTOME": {
        "base_url": "https://reactome.org/ContentService",
        "enrichment_method": "hypergeometric",
    },
    "GO": {
        "base_url": "http://geneontology.org",
        "enrichment_method": "hypergeometric",
    },
}

# Clinical database configurations
CLINICAL_DATABASES = {
    "COSMIC": {
        "base_url": "https://cancer.sanger.ac.uk/cosmic",
        "api_key_required": True,
        "rate_limit": 100,  # requests per hour
    },
    "CLINVAR": {
        "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        "api_key_required": False,
        "rate_limit": 3,  # requests per second
    },
    "ONCOKB": {
        "base_url": "https://www.oncokb.org/api/v1",
        "api_key_required": True,
        "rate_limit": 1000,  # requests per day
    },
}

# File format configurations
SUPPORTED_FORMATS = {
    "expression_data": [".csv", ".tsv", ".txt", ".xlsx"],
    "clinical_data": [".csv", ".tsv", ".txt", ".xlsx"],
    "mutation_data": [".maf", ".vcf", ".csv", ".tsv"],
    "methylation_data": [".csv", ".tsv", ".txt"],
    "protein_data": [".csv", ".tsv", ".txt"],
}

# Quality control thresholds
QC_THRESHOLDS = {
    "min_library_size": 1000000,  # minimum reads per sample
    "max_missing_genes": 0.5,  # maximum fraction of missing genes per sample
    "min_gene_expression": 1.0,  # minimum expression value
    "max_zero_fraction": 0.8,  # maximum fraction of zero values per gene
    "min_sample_correlation": 0.3,  # minimum correlation between technical replicates
    "max_pca_outlier_distance": 3.0,  # maximum Mahalanobis distance for PCA outliers
}

# Initialize directories on import
create_directories()
