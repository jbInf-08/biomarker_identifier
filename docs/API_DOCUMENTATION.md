# Cancer Biomarker Identifier - API Documentation

## Overview

The Cancer Biomarker Identifier API provides a comprehensive RESTful interface for identifying, analyzing, and validating cancer biomarkers using multi-omics data integration and machine learning approaches.

## Base URL

```
http://localhost:8000
```

The same route handlers are mounted at **unversioned** paths (`/api/...`), **`/api/v1/...`**, and **`/api/v2/...`** for core resources (biomarkers, analysis, data, clinical, auth, etc.). Prefer **`/api/v1/...`** for new integrations; see `backend/app/main.py` for the full list.

## Authentication

**Biomarker runs, data uploads, reports, and most user-specific operations require a valid JWT** (HTTP `Authorization: Bearer <token>`). Obtain a token by registering and logging in:

- `POST /api/v1/auth/register` (or `/api/auth/register`)
- `POST /api/v1/auth/login` (or `/api/auth/login`)

**Public / low-friction endpoints** include health and status (`GET /health`, `GET /api/status`, `GET /api/v1/system/health`, etc., depending on deployment). Use the interactive **Swagger UI** at `/docs` to see which operations require a bearer token.

## API Endpoints

### Core Endpoints

#### Liveness and readiness

- **`GET /health/live`** — liveness: process is up.
- **`GET /health/ready`**, **`GET /health`** — readiness: returns **503** if PostgreSQL (and Redis, when not in SQLite dev mode) is unhealthy. The JSON body includes per-component checks (see `backend/app/core/health.py`).

**Example (readiness success; shape varies with `HEALTH_CHECK_CELERY` and SQLite vs Postgres):**
```json
{
  "status": "healthy",
  "ready": true,
  "checks": {
    "database": {"ok": true},
    "redis": {"ok": true},
    "celery": {"ok": null, "skipped": true, "reason": "HEALTH_CHECK_CELERY=false"}
  },
  "timestamp": "2026-01-15T12:00:00+00:00"
}
```

#### API Status

**GET** `/api/status`

Short operational summary: API version, region (if `DEPLOYMENT_REGION` is set), and a map of useful path prefixes (biomarkers, federated capabilities, health URLs, etc.).

### Biomarker Pipeline Endpoints

#### Start Pipeline Run

**POST** `/api/biomarkers/run`

Start a new biomarker identification pipeline run.

**Request Body (multipart/form-data):**
- `expression_file` (file, required): Expression matrix file (TSV/CSV)
- `labels_file` (file, required): Sample labels file (TSV/CSV)
- `metadata_file` (file, optional): Metadata file (YAML/JSON)
- `run_name` (string, optional): Name for this run
- `normalization_method` (string, optional): Normalization method (default: "log2")
- `stats_methods` (string, optional): Statistical methods (default: "t_test")
- `selection_methods` (string, optional): ML selection methods (default: "logistic_regression")
- `n_features` (integer, optional): Number of features to select (default: 100)
- `stability_bootstraps` (integer, optional): Number of bootstrap iterations (default: 100)

**Response:**
```json
{
  "run_id": "biomarker_run_20240101_120000",
  "status": "started",
  "message": "Pipeline started successfully",
  "estimated_duration": "5-10 minutes"
}
```

#### Get Pipeline Runs

**GET** `/api/biomarkers/runs`

Get a list of all pipeline runs.

**Response:**
```json
[
  {
    "run_id": "biomarker_run_20240101_120000",
    "run_name": "BRCA Analysis",
    "status": "completed",
    "created_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:05:30Z"
  }
]
```

#### Get Run Status

**GET** `/api/biomarkers/runs/{run_id}/status`

Get the current status of a specific pipeline run.

**Response:**
```json
{
  "run_id": "biomarker_run_20240101_120000",
  "status": "running",
  "progress": 65,
  "current_step": "machine_learning_selection",
  "estimated_completion": "2024-01-01T12:08:00Z"
}
```

#### Get Run Results

**GET** `/api/biomarkers/runs/{run_id}/results`

Get complete results from a pipeline run.

**Response:**
```json
{
  "run_id": "biomarker_run_20240101_120000",
  "run_name": "BRCA Analysis",
  "status": "completed",
  "pipeline_steps": ["data_loading", "quality_control", "normalization", "statistical_analysis", "ml_selection"],
  "data_summary": {
    "n_genes": 20000,
    "n_samples": 100,
    "n_classes": 2
  },
  "biomarker_list": {
    "biomarkers": [
      {
        "gene": "TP53",
        "final_score": 0.95,
        "final_rank": 1,
        "statistical_evidence": {
          "t_test": true,
          "wilcoxon": true
        },
        "ml_evidence": {
          "consensus_score": 0.92,
          "selection_count": 4,
          "methods": ["logistic_regression", "random_forest", "svm", "xgboost"]
        }
      }
    ],
    "summary": {
      "total_biomarkers": 50,
      "statistically_significant": 45,
      "ml_selected": 48,
      "high_confidence": 30
    }
  },
  "statistical_analysis": {
    "method_results": {
      "t_test": {
        "significant_features": ["TP53", "BRCA1", "BRCA2"],
        "volcano_plot_data": "..."
      }
    }
  },
  "ml_selection": {
    "consensus_features": [
      {
        "feature": "TP53",
        "consensus_score": 0.92,
        "selection_count": 4,
        "methods": ["logistic_regression", "random_forest", "svm", "xgboost"]
      }
    ]
  }
}
```

#### Get Biomarkers

**GET** `/api/biomarkers/runs/{run_id}/biomarkers`

Get the ranked biomarker list from a completed run.

**Query Parameters:**
- `top_n` (integer, optional): Number of top biomarkers to return (default: 50)
- `min_score` (float, optional): Minimum final score threshold
- `statistically_significant` (boolean, optional): Filter for statistically significant only

**Response:**
```json
{
  "biomarkers": [
    {
      "gene": "TP53",
      "final_score": 0.95,
      "final_rank": 1,
      "statistical_evidence": {
        "t_test": true,
        "wilcoxon": true
      },
      "ml_evidence": {
        "consensus_score": 0.92,
        "selection_count": 4,
        "methods": ["logistic_regression", "random_forest", "svm", "xgboost"]
      }
    }
  ],
  "summary": {
    "total_biomarkers": 50,
    "statistically_significant": 45,
    "ml_selected": 48,
    "high_confidence": 30
  }
}
```

### Model Training and Evaluation

#### Train Model

**POST** `/api/biomarkers/runs/{run_id}/train-model`

Train and evaluate a machine learning model using selected features.

**Request Body:**
```json
{
  "model_type": "logistic_regression",
  "features": ["TP53", "BRCA1", "BRCA2"],
  "cv_folds": 5,
  "test_size": 0.3,
  "random_state": 42
}
```

**Response:**
```json
{
  "model_performance": {
    "accuracy": 0.85,
    "precision": 0.83,
    "recall": 0.87,
    "f1_score": 0.85,
    "roc_auc": 0.89,
    "pr_auc": 0.86
  },
  "cross_validation": {
    "accuracy": [0.82, 0.85, 0.88, 0.84, 0.86],
    "precision": [0.80, 0.83, 0.86, 0.82, 0.84],
    "recall": [0.85, 0.88, 0.91, 0.87, 0.89],
    "f1_score": [0.82, 0.85, 0.88, 0.84, 0.86]
  },
  "confusion_matrix": {
    "true_negatives": 15,
    "false_positives": 2,
    "false_negatives": 3,
    "true_positives": 20
  },
  "calibration": {
    "brier_score": 0.12,
    "reliability_curve": "..."
  }
}
```

### SHAP Analysis

#### Run SHAP Analysis

**POST** `/api/biomarkers/runs/{run_id}/shap-analysis`

Perform SHAP analysis for model explainability.

**Request Body:**
```json
{
  "model_type": "logistic_regression",
  "features": ["TP53", "BRCA1", "BRCA2"],
  "analysis_type": "both",
  "n_samples": 100
}
```

**Response:**
```json
{
  "global_analysis": {
    "feature_importance": {
      "TP53": 0.35,
      "BRCA1": 0.28,
      "BRCA2": 0.22
    },
    "summary_plot": "...",
    "bar_plot": "..."
  },
  "local_analysis": {
    "sample_contributions": {
      "SAMPLE_001": {
        "prediction": 0.85,
        "base_value": 0.5,
        "feature_contributions": {
          "TP53": 0.15,
          "BRCA1": 0.12,
          "BRCA2": 0.08
        }
      }
    },
    "waterfall_plots": "...",
    "dependence_plots": "..."
  }
}
```

### Pathway Analysis

#### Run Pathway Analysis

**POST** `/api/biomarkers/runs/{run_id}/pathway-analysis`

Perform pathway enrichment analysis on identified biomarkers.

**Request Body:**
```json
{
  "gene_list": ["TP53", "BRCA1", "BRCA2"],
  "analysis_type": "both",
  "gene_sets": ["KEGG", "REACTOME"],
  "min_size": 5,
  "max_size": 500
}
```

**Response:**
```json
{
  "gsea_results": {
    "KEGG": {
      "results": [
        {
          "pathway": "p53 signaling pathway",
          "nes": 2.15,
          "fdr": 0.001,
          "pvalue": 0.0005,
          "leading_edge": ["TP53", "CDKN1A"]
        }
      ],
      "status": "success"
    }
  },
  "ora_results": {
    "KEGG": {
      "results": [
        {
          "pathway": "p53 signaling pathway",
          "overlap": 3,
          "expected": 0.5,
          "pvalue": 0.001,
          "adj_pval": 0.005
        }
      ],
      "status": "success"
    }
  },
  "summary": {
    "n_genes": 3,
    "analysis_type": "both",
    "gsea_summary": {
      "significant_pathways": 5,
      "top_pathway": "p53 signaling pathway"
    },
    "ora_summary": {
      "significant_pathways": 3,
      "top_pathway": "p53 signaling pathway"
    }
  }
}
```

### Gene Annotation

#### Annotate Genes

**POST** `/api/biomarkers/runs/{run_id}/annotate`

Annotate genes with clinical and biological context.

**Request Body:**
```json
{
  "gene_list": ["TP53", "BRCA1", "BRCA2"],
  "databases": ["COSMIC", "ClinVar", "OncoKB"],
  "include_expression": true,
  "include_mutations": true
}
```

**Response:**
```json
{
  "annotations": {
    "TP53": {
      "basic_info": {
        "symbol": "TP53",
        "name": "tumor protein p53",
        "chromosome": "17p13.1",
        "description": "Tumor suppressor protein"
      },
      "cancer_info": {
        "COSMIC": {
          "mutation_frequency": 0.42,
          "cancer_types": ["breast", "lung", "colorectal"],
          "status": "success"
        },
        "OncoKB": {
          "oncogenicity": "Oncogene",
          "evidence_level": "1",
          "status": "success"
        }
      },
      "clinical_info": {
        "ClinVar": {
          "pathogenic_variants": 1250,
          "benign_variants": 450,
          "status": "success"
        }
      },
      "expression_info": {
        "tissue_expression": "ubiquitous",
        "cancer_expression": "overexpressed"
      },
      "mutation_info": {
        "hotspot_mutations": ["R175H", "R248W", "R273H"],
        "mutation_spectrum": "missense"
      }
    }
  },
  "summary": {
    "n_genes": 3,
    "databases_queried": ["COSMIC", "ClinVar", "OncoKB"],
    "cancer_genes": 3,
    "clinical_genes": 3
  }
}
```

### Report Generation

#### Generate Report

**POST** `/api/biomarkers/runs/{run_id}/report`

Generate a comprehensive report for a pipeline run.

**Request Body:**
```json
{
  "report_format": "html",
  "report_title": "BRCA Biomarker Analysis Report",
  "include_appendices": true,
  "include_methods": true,
  "include_figures": true
}
```

**Response:**
```json
{
  "report_path": "/reports/biomarker_run_20240101_120000_report.html",
  "report_url": "/api/reports/biomarker_run_20240101_120000_report.html",
  "report_size": "2.5MB",
  "generation_time": "15.3s"
}
```

#### Download Report

**GET** `/api/biomarkers/runs/{run_id}/download-report`

Download a generated report.

**Query Parameters:**
- `format` (string, optional): Report format (html/pdf, default: html)

**Response:** File download

### Data Validation

#### Validate Expression Data

**POST** `/api/data/validate-expression`

Validate expression data file format and content.

**Request Body (multipart/form-data):**
- `file` (file, required): Expression data file

**Response:**
```json
{
  "is_valid": true,
  "validation_errors": [],
  "data_summary": {
    "n_genes": 20000,
    "n_samples": 100,
    "missing_ratio": 0.05,
    "zero_ratio": 0.15
  },
  "recommendations": [
    "Consider log2 transformation for count data",
    "Check for batch effects"
  ]
}
```

#### Validate Labels

**POST** `/api/data/validate-labels`

Validate sample labels file.

**Request Body (multipart/form-data):**
- `file` (file, required): Labels file

**Response:**
```json
{
  "is_valid": true,
  "validation_errors": [],
  "label_summary": {
    "n_samples": 100,
    "n_classes": 2,
    "class_distribution": {
      "TUMOR": 50,
      "NORMAL": 50
    }
  }
}
```

#### Validate Data Compatibility

**POST** `/api/data/validate-compatibility`

Validate compatibility between expression and labels data.

**Request Body (multipart/form-data):**
- `expression_file` (file, required): Expression data file
- `labels_file` (file, required): Labels file

**Response:**
```json
{
  "is_compatible": true,
  "compatibility_issues": [],
  "sample_overlap": {
    "expression_samples": 100,
    "label_samples": 100,
    "common_samples": 100,
    "missing_samples": []
  }
}
```

### CGAS Integration

#### Get Mutation Information

**GET** `/api/cgas/mutations/{gene_symbol}`

Get mutation information for a gene from CGAS.

**Response:**
```json
{
  "gene_symbol": "TP53",
  "mutations": [
    {
      "mutation_id": "COSM12345",
      "chromosome": "17",
      "position": 7577120,
      "reference": "C",
      "alternate": "T",
      "consequence": "missense_variant",
      "cancer_types": ["breast", "lung"]
    }
  ],
  "summary": {
    "total_mutations": 1250,
    "cancer_types": ["breast", "lung", "colorectal"]
  }
}
```

#### Get Pathway Information

**GET** `/api/cgas/pathways/{gene_symbol}`

Get pathway information for a gene from CGAS.

**Response:**
```json
{
  "gene_symbol": "TP53",
  "pathways": [
    {
      "pathway_id": "KEGG:04115",
      "pathway_name": "p53 signaling pathway",
      "database": "KEGG",
      "role": "regulator"
    }
  ],
  "summary": {
    "total_pathways": 15,
    "databases": ["KEGG", "Reactome", "GO"]
  }
}
```

### Management Endpoints

#### Delete Run

**DELETE** `/api/biomarkers/runs/{run_id}`

Delete a pipeline run and all associated data.

**Response:**
```json
{
  "message": "Run deleted successfully",
  "deleted_files": [
    "pipeline_results.json",
    "biomarker_list.csv",
    "normalized_data.tsv"
  ]
}
```

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "error": "validation_error",
  "message": "Invalid input parameters",
  "details": {
    "field": "expression_file",
    "issue": "File format not supported"
  }
}
```

### 404 Not Found
```json
{
  "error": "not_found",
  "message": "Run not found",
  "run_id": "invalid_run_id"
}
```

### 422 Unprocessable Entity
```json
{
  "error": "validation_error",
  "message": "Data validation failed",
  "details": {
    "sample_overlap": "No common samples between expression and labels"
  }
}
```

### 500 Internal Server Error
```json
{
  "error": "internal_error",
  "message": "An unexpected error occurred",
  "request_id": "req_12345"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. Future versions will include rate limiting based on user authentication.

## File Formats

### Expression Data

Supported formats: TSV, CSV

**Required format:**
- Rows: Genes (Ensembl IDs or gene symbols)
- Columns: Samples (sample IDs as headers)
- Values: Expression values (counts, TPM, FPKM, etc.)

**Example:**
```tsv
Gene\tSAMPLE_001\tSAMPLE_002\tSAMPLE_003
TP53\t1250\t980\t1100
BRCA1\t850\t920\t780
BRCA2\t650\t720\t680
```

### Labels Data

Supported formats: TSV, CSV

**Required format:**
- `sample_id`: Sample identifier (must match expression data)
- `class_label`: Class label (e.g., TUMOR, NORMAL)
- Additional columns: Covariates (age, gender, stage, etc.)

**Example:**
```tsv
sample_id\tclass_label\tage\tgender
SAMPLE_001\tTUMOR\t45\tF
SAMPLE_002\tTUMOR\t52\tM
SAMPLE_003\tNORMAL\t48\tF
```

### Metadata

Supported formats: YAML, JSON

**Example:**
```yaml
project_name: "BRCA Biomarker Study"
investigator: "Dr. Jane Smith"
species: "Homo sapiens"
genome_build: "GRCh38"
normalization: "log2"
consent_note: "All samples collected with informed consent"
```

## Data Requirements

### Minimum Requirements
- **Expression data**: At least 100 genes and 10 samples
- **Labels**: Binary or multi-class labels
- **Sample overlap**: At least 80% sample overlap between expression and labels

### Recommended Requirements
- **Expression data**: 10,000+ genes, 50+ samples
- **Labels**: Balanced class distribution
- **Quality**: Low missing data (<10%), appropriate normalization

## Performance Considerations

### Processing Times
- **Small datasets** (<1,000 genes, <50 samples): 1-2 minutes
- **Medium datasets** (1,000-10,000 genes, 50-200 samples): 5-10 minutes
- **Large datasets** (>10,000 genes, >200 samples): 10-30 minutes

### Memory Usage
- **Small datasets**: <1GB RAM
- **Medium datasets**: 1-4GB RAM
- **Large datasets**: 4-8GB RAM

### File Size Limits
- **Expression files**: Up to 100MB
- **Label files**: Up to 10MB
- **Metadata files**: Up to 1MB

## Versioning

The HTTP API is exposed at **unversioned** paths (`/api/...`) and as **`/api/v1/...`** and **`/api/v2/...`** mirrors for the same route handlers. Prefer `/api/v1/...` for new clients. The application version string in OpenAPI and `/api/status` is **1.0.0** (see `backend/app/main.py`).

**Example:**
```
POST /api/v1/biomarkers/run
```

## Support

For API support and questions:
- **How to run**: [HOW_TO_RUN.md](../HOW_TO_RUN.md) and live `/docs` on your deployment
- **Issues**: [GitHub Issues](https://github.com/jbInf-08/biomarker_identifier/issues)
- **Maintainer contact**: as listed in the root [README.md](../README.md)

## Changelog

### Documentation refresh (2026-04)
- Aligned with JWT authentication, health endpoints (`/health`, `/health/ready`, `/health/live`), and current versioning layout.

### v1.0.0 (API surface)
- Core biomarker pipeline, statistics and ML, reporting, and versioned route mounts as implemented in the FastAPI app.
