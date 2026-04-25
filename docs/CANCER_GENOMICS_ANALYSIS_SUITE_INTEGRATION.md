# Cancer Genomics Analysis Suite - Complete Integration Deep Dive

## Executive Summary

The **Cancer Genomics Analysis Suite** is not a separate standalone system, but rather the comprehensive collection of genomics analysis capabilities that are **fully integrated** throughout the Cancer Biomarker Identifier platform. This document provides a complete technical deep dive into how all genomics analysis components are connected, orchestrated, and integrated.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Pipeline Integration](#core-pipeline-integration)
3. [Component-Level Integration](#component-level-integration)
4. [Data Flow Architecture](#data-flow-architecture)
5. [API Integration Layer](#api-integration-layer)
6. [Real-Time Communication](#real-time-communication)
7. [Database Integration](#database-integration)
8. [Configuration Management](#configuration-management)
9. [Error Handling & Recovery](#error-handling--recovery)
10. [Performance Optimization](#performance-optimization)

---

## 1. Architecture Overview

### 1.1 System Architecture

The Cancer Genomics Analysis Suite is architected as a **modular, pipeline-based system** where each analysis component is a specialized module that integrates seamlessly into the main biomarker discovery pipeline.

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Interface Layer                         │
│  (React Frontend - Upload, Configure, Monitor, Visualize)      │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────────┐
│                    API Gateway Layer                            │
│  (FastAPI REST Endpoints + WebSocket Routes)                   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────────┐
│              Background Task Orchestration                       │
│  (Celery Task Queue - Async Processing)                        │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────────┐
│              MAIN GENOMICS ANALYSIS PIPELINE                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  BiomarkerPipeline (Orchestrator)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                        │                                         │
│  ┌─────────────────────┼─────────────────────┐                 │
│  │                     │                     │                 │
│  ▼                     ▼                     ▼                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Data Loading │  │ Quality      │  │ Normalization│          │
│  │ & Validation │  │ Control      │  │ & Batch      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                 │                     │               │
│         └─────────────────┴─────────────────────┘               │
│                        │                                         │
│         ┌──────────────┴──────────────┐                          │
│         │                            │                          │
│         ▼                            ▼                          │
│  ┌──────────────┐            ┌──────────────┐                  │
│  │ Statistical │            │ Machine      │                  │
│  │ Analysis     │            │ Learning     │                  │
│  │ Pipeline     │            │ Pipeline     │                  │
│  └──────────────┘            └──────────────┘                  │
│         │                            │                          │
│         └──────────────┬─────────────┘                          │
│                        │                                         │
│                        ▼                                         │
│              ┌──────────────────┐                                 │
│              │ Biomarker List  │                                 │
│              │ Generation       │                                 │
│              └──────────────────┘                                 │
│                        │                                         │
│         ┌──────────────┼──────────────┐                          │
│         │              │              │                          │
│         ▼              ▼              ▼                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ Clinical     │ │ Pathway      │ │ Report      │             │
│  │ Annotation   │ │ Analysis     │ │ Generation  │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                        │
┌───────────────────────┴─────────────────────────────────────────┐
│                    Data Persistence Layer                        │
│  (PostgreSQL - Results, Redis - Cache, File System - Artifacts)│
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Integration Principles

1. **Unified Configuration**: All components share a single configuration system
2. **Consistent Data Format**: Standardized pandas DataFrames flow between components
3. **Modular Design**: Each component is independently testable and replaceable
4. **Progress Tracking**: Real-time progress updates via WebSocket
5. **Error Resilience**: Comprehensive error handling at each integration point
6. **Result Aggregation**: Multiple analysis results combined into unified outputs

---

## 2. Core Pipeline Integration

### 2.1 BiomarkerPipeline - The Central Orchestrator

**Location**: `backend/app/pipelines/biomarker_pipeline.py`

The `BiomarkerPipeline` class is the **central orchestrator** that coordinates all genomics analysis components. It initializes and manages the lifecycle of each component.

#### Initialization

```python
class BiomarkerPipeline:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.pipeline_results = {}
        self.run_id = None
        
        # Initialize ALL genomics analysis components
        self.data_io = DataIO(config)              # Data loading
        self.qc = QualityControl(config)           # Quality control
        self.normalizer = Normalization(config)    # Normalization
        self.stats_pipeline = StatisticalPipeline(config)  # Statistical analysis
        self.ml_pipeline = MLSelectionPipeline(config)     # ML analysis
```

#### Pipeline Execution Flow

The pipeline executes in **9 sequential steps**, with each step tightly integrated:

```python
def run_pipeline(self, expression_file, labels_file, metadata_file=None, ...):
    # Step 1: Data Loading and Validation
    data_results = self.data_io.load_data(...)
    expression_data = data_results["expression_data"]
    labels = data_results["labels"]
    
    # Step 2: Quality Control
    qc_results = self.qc.perform_qc_analysis(expression_data, labels, ...)
    
    # Step 3: Data Filtering
    filtered_data, filtering_summary = self.qc.filter_data(...)
    
    # Step 4: Normalization
    norm_results = self.normalizer.normalize_data(...)
    normalized_data = norm_results["final_data"]
    
    # Step 5: Statistical Analysis (GENOMICS ANALYSIS SUITE)
    stats_results = self.stats_pipeline.run_statistical_analysis(
        normalized_data, labels, ...
    )
    
    # Step 6: Machine Learning Feature Selection (GENOMICS ANALYSIS SUITE)
    ml_results = self.ml_pipeline.run_ml_selection(
        normalized_data, labels, ...
    )
    
    # Step 7: Generate Final Biomarker List (COMBINES STATS + ML)
    biomarker_list = self._generate_biomarker_list(stats_results, ml_results, ...)
    
    # Step 8: Generate Summary
    pipeline_summary = self._generate_pipeline_summary(results)
    
    # Step 9: Save Results
    self._save_pipeline_results(results, run_output_dir)
```

### 2.2 Data Flow Between Components

Each component receives data in a **standardized format** and produces results that feed into the next component:

```
Raw Files (CSV/TSV)
    ↓
[DataIO] → pandas.DataFrame (genes × samples)
    ↓
[QualityControl] → Filtered DataFrame
    ↓
[Normalization] → Normalized DataFrame
    ↓
    ├─→ [StatisticalPipeline] → Statistical Results Dict
    └─→ [MLSelectionPipeline] → ML Results Dict
    ↓
[BiomarkerPipeline._generate_biomarker_list()] → Combined Biomarker List
    ↓
[Clinical Annotation] → Enriched Biomarker List
    ↓
[Pathway Analysis] → Pathway Enrichment Results
    ↓
[Report Generation] → Final Reports (HTML/PDF)
```

---

## 3. Component-Level Integration

### 3.1 Statistical Analysis Pipeline Integration

**Location**: `backend/app/pipelines/stats.py`

The Statistical Pipeline is a **wrapper** around the core statistical analysis module that provides:

#### Integration Points

1. **Input**: Normalized expression data (pandas.DataFrame) + labels (pandas.Series)
2. **Processing**: Multiple statistical methods (t-test, Wilcoxon, ANOVA, etc.)
3. **Output**: Standardized results dictionary

```python
class StatisticalPipeline:
    def __init__(self, config):
        self.stats_analyzer = StatisticalAnalysis(config)  # Core module
    
    def run_statistical_analysis(self, expression_data, labels, ...):
        # Automatically selects appropriate methods based on data
        if len(labels.unique()) == 2:
            analysis_methods = ["t_test", "wilcoxon"]
        elif len(labels.unique()) > 2:
            analysis_methods = ["anova", "kruskal"]
        
        # Run each method
        for method in analysis_methods:
            method_result = self.stats_analyzer.differential_expression_analysis(
                expression_data, labels, method, ...
            )
            results["method_results"][method] = method_result
        
        # Generate visualizations
        volcano_data = self.stats_analyzer.volcano_plot_data(...)
        
        # Rank features
        ranking_results = self.stats_analyzer.rank_features(...)
        
        return results  # Standardized format
```

#### Integration with Main Pipeline

The statistical results are **directly consumed** by the biomarker list generation:

```python
# In BiomarkerPipeline._generate_biomarker_list()
significant_features = {}
for method, method_result in stats_results.get("method_results", {}).items():
    if "significant_features_adjusted" in method_result:
        significant = method_result["significant_features_adjusted"]
        significant_features[method] = significant
```

### 3.2 Machine Learning Pipeline Integration

**Location**: `backend/app/pipelines/ml_select.py`

The ML Pipeline integrates **multiple feature selection methods** and combines them into consensus features.

#### Integration Architecture

```python
class MLSelectionPipeline:
    def __init__(self, config):
        self.feature_selector = FeatureSelection(config)  # Core module
    
    def run_ml_selection(self, expression_data, labels, ...):
        # Step 1: Filter methods (variance, F-test, mutual info)
        filter_results = self.feature_selector.filter_methods(...)
        
        # Step 2: Wrapper methods (RFE, sequential selection)
        wrapper_results = self.feature_selector.wrapper_methods(...)
        
        # Step 3: Embedded methods (LASSO, Random Forest, SVM)
        embedded_results = self.feature_selector.embedded_methods(...)
        
        # Step 4: Stability selection
        stability_results = self.feature_selector.stability_selection(...)
        
        # Step 5: Ensemble selection (combines all methods)
        ensemble_results = self.feature_selector.ensemble_selection(...)
        
        # Step 6: Generate consensus features
        consensus_features = self._generate_consensus_features(results)
        
        # Step 7: Evaluate selected features
        evaluation_results = self._evaluate_selected_features(...)
        
        return results
```

#### Consensus Feature Generation

The ML pipeline generates **consensus features** by combining results from multiple methods:

```python
def _generate_consensus_features(self, results):
    # Collect features from all methods
    all_selected_features = {}
    for category, category_results in results["method_results"].items():
        for method, method_result in category_results.items():
            all_selected_features[f"{category}_{method}"] = method_result["selected_features"]
    
    # Calculate feature frequency across methods
    feature_counts = {}
    for method_features in all_selected_features.values():
        for feature in method_features:
            feature_counts[feature] = feature_counts.get(feature, 0) + 1
    
    # Calculate consensus score (frequency / total methods)
    n_methods = len(all_selected_features)
    consensus_features = []
    for feature, count in feature_counts.items():
        consensus_score = count / n_methods
        if consensus_score >= 0.5:  # At least 50% agreement
            consensus_features.append({
                "feature": feature,
                "consensus_score": consensus_score,
                "selection_count": count,
                "methods": [...]
            })
    
    return {"consensus_features": consensus_features, ...}
```

### 3.3 Biomarker List Generation - The Integration Point

**Location**: `backend/app/pipelines/biomarker_pipeline.py` (lines 200-294)

This is where **statistical and ML results are combined**:

```python
def _generate_biomarker_list(self, stats_results, ml_results, **kwargs):
    # Get significant features from statistical analysis
    significant_features = {}
    for method, method_result in stats_results.get("method_results", {}).items():
        if "significant_features_adjusted" in method_result:
            significant_features[method] = method_result["significant_features_adjusted"]
    
    # Get consensus features from ML selection
    consensus_features = ml_results.get("consensus_features", {}).get("consensus_features", [])
    
    # Combine all features
    all_features = set()
    for features in significant_features.values():
        all_features.update(features)
    for feature_info in consensus_features:
        all_features.add(feature_info["feature"])
    
    # Create biomarker entries with BOTH statistical and ML evidence
    biomarkers = []
    for feature in all_features:
        biomarker_entry = {
            "gene": feature,
            "statistical_evidence": {},  # Which stat methods found it
            "ml_evidence": {},           # ML consensus score
            "consensus_score": 0.0,
            "final_rank": 0
        }
        
        # Add statistical evidence
        for method, features in significant_features.items():
            biomarker_entry["statistical_evidence"][method] = feature in features
        
        # Add ML evidence
        for feature_info in consensus_features:
            if feature_info["feature"] == feature:
                biomarker_entry["ml_evidence"] = {
                    "consensus_score": feature_info["consensus_score"],
                    "selection_count": feature_info["selection_count"],
                    "methods": feature_info["methods"]
                }
                biomarker_entry["consensus_score"] = feature_info["consensus_score"]
        
        biomarkers.append(biomarker_entry)
    
    # Calculate final ranking score (WEIGHTED COMBINATION)
    for biomarker in biomarkers:
        stat_score = sum(biomarker["statistical_evidence"].values()) / len(...)
        ml_score = biomarker["consensus_score"]
        
        # Weighted combination: 60% statistical, 40% ML
        final_score = 0.6 * stat_score + 0.4 * ml_score
        biomarker["final_score"] = final_score
    
    # Sort by final score
    biomarkers.sort(key=lambda x: x["final_score"], reverse=True)
    
    return {"biomarkers": biomarkers, "summary": {...}}
```

### 3.4 Clinical Annotation Integration

**Location**: `backend/app/pipelines/annotate.py`

Clinical annotation enriches biomarkers with database information:

```python
class GeneAnnotation:
    def annotate_genes(self, gene_list, databases=None, ...):
        if databases is None:
            databases = ["COSMIC", "ClinVar", "OncoKB"]
        
        for gene in gene_list:
            # Query each database
            cancer_info = self._get_cancer_info(gene, databases)
            clinical_info = self._get_clinical_info(gene, databases)
            mutation_info = self._get_mutation_info(gene, databases)
            
            # Combine into annotation
            gene_annotation = {
                "gene": gene,
                "cancer_info": cancer_info,      # COSMIC, OncoKB
                "clinical_info": clinical_info,   # ClinVar, OncoKB
                "mutation_info": mutation_info   # COSMIC mutations
            }
        
        return results
```

#### Database Integration Points

- **COSMIC**: Cancer gene census, mutation frequencies
- **ClinVar**: Clinical significance of variants
- **OncoKB**: Therapeutic actionability, evidence levels

### 3.5 Pathway Analysis Integration

**Location**: `backend/app/pipelines/pathways.py`

Pathway analysis integrates with GSEA and ORA:

```python
class PathwayAnalysis:
    def run_pathway_analysis(self, gene_list, expression_data=None, labels=None, ...):
        # GSEA (requires expression data)
        if analysis_type in ["gsea", "both"] and expression_data is not None:
            gsea_results = self._run_gsea(expression_data, labels, gene_sets, ...)
        
        # ORA (gene list only)
        if analysis_type in ["ora", "both"]:
            ora_results = self._run_ora(gene_list, gene_sets, ...)
        
        return {
            "gsea_results": gsea_results,
            "ora_results": ora_results,
            "summary": self._generate_pathway_summary(results)
        }
```

#### Integration with gseapy Library

The pathway analysis uses the `gseapy` library for actual GSEA/ORA computation:

```python
def _run_gsea(self, expression_data, labels, gene_sets, ...):
    import gseapy as gp
    
    # Calculate differential expression for GSEA
    de_results = self._calculate_differential_expression(expression_data, labels)
    
    # Run GSEA for each gene set
    for gene_set in gene_sets:
        gsea_result = gp.gsea(
            data=de_results,
            gene_sets=self._map_gene_set_name(gene_set),
            cls=labels,
            ...
        )
```

---

## 4. Data Flow Architecture

### 4.1 Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ USER UPLOAD                                                    │
│ - Expression file (CSV/TSV)                                    │
│ - Labels file (CSV/TSV)                                        │
│ - Metadata file (optional)                                     │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: DATA LOADING (DataIO)                                  │
│ - File validation                                               │
│ - Format conversion                                             │
│ - Data type checking                                            │
│ Output: expression_data (DataFrame), labels (Series)            │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: QUALITY CONTROL (QualityControl)                       │
│ - Library size checks                                          │
│ - Missing value analysis                                       │
│ - Outlier detection                                             │
│ Output: QC report, filtered_data (DataFrame)                    │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: DATA FILTERING (QualityControl)                        │
│ - Low variance gene removal                                     │
│ - Low expression gene removal                                   │
│ - High missing rate removal                                     │
│ Output: filtered_data (DataFrame)                              │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: NORMALIZATION (Normalization)                          │
│ - Log transformation                                            │
│ - Quantile normalization                                       │
│ - Batch effect correction (ComBat/Limma)                        │
│ Output: normalized_data (DataFrame)                           │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│ STEP 5:          │          │ STEP 6:           │
│ STATISTICAL      │          │ MACHINE LEARNING  │
│ ANALYSIS         │          │ SELECTION        │
│                  │          │                  │
│ - t-test         │          │ - Filter methods │
│ - Wilcoxon       │          │ - Wrapper methods│
│ - ANOVA          │          │ - Embedded methods│
│ - Multiple       │          │ - Stability      │
│   testing        │          │   selection      │
│   correction     │          │ - Ensemble       │
│                  │          │                  │
│ Output:          │          │ Output:          │
│ - Significant    │          │ - Consensus      │
│   features       │          │   features        │
│ - P-values       │          │ - ML scores      │
│ - Fold changes   │          │ - Method counts│
└──────────────────┘          └──────────────────┘
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: BIOMARKER LIST GENERATION                              │
│ - Combine statistical significant features                     │
│ - Combine ML consensus features                                 │
│ - Calculate weighted final scores                              │
│ - Rank biomarkers                                              │
│ Output: biomarker_list (List[Dict])                           │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ CLINICAL     │ │ PATHWAY      │ │ REPORT       │
│ ANNOTATION   │ │ ANALYSIS     │ │ GENERATION   │
│              │ │              │ │              │
│ - COSMIC     │ │ - GSEA       │ │ - HTML report│
│ - ClinVar    │ │ - ORA        │ │ - PDF report │
│ - OncoKB     │ │ - KEGG       │ │ - Visualizations│
│              │ │ - Reactome   │ │              │
│ Output:      │ │ Output:      │ │ Output:      │
│ - Annotated  │ │ - Enriched   │ │ - Reports    │
│   biomarkers │ │   pathways   │ │ - Files     │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 4.2 Data Format Standardization

All components use **standardized data formats**:

#### Input Format
- **Expression Data**: `pandas.DataFrame` with genes as index, samples as columns
- **Labels**: `pandas.Series` with sample IDs as index, class labels as values
- **Metadata**: `Dict[str, Any]` with optional batch information, etc.

#### Output Format
- **Results**: `Dict[str, Any]` with standardized keys:
  - `"method_results"`: Results from each method
  - `"summary"`: Summary statistics
  - `"plots"`: Visualization objects (optional)
  - `"significant_features"`: List of significant genes/features

---

## 5. API Integration Layer

### 5.1 REST API Endpoints

**Location**: `backend/app/api/routes/biomarker_routes.py`

The API layer provides HTTP endpoints that trigger the genomics analysis:

#### Main Endpoints

```python
# Start analysis
@router.post("/run")
async def start_pipeline(
    expression_file: UploadFile,
    labels_file: UploadFile,
    run_name: str,
    config: str,
    ...
):
    # 1. Save uploaded files
    # 2. Create AnalysisRun record in database
    # 3. Start background Celery task
    background_tasks.add_task(run_biomarker_analysis, run_id, config_dict)
    return {"run_id": run_id, "status": "started"}

# Get run status
@router.get("/runs/{run_id}/status")
async def get_run_status(run_id: str, ...):
    analysis_run = db.query(AnalysisRun).filter(...).first()
    return {
        "run_id": run_id,
        "status": analysis_run.status,
        "progress": analysis_run.progress,
        ...
    }

# Get results
@router.get("/runs/{run_id}/results")
async def get_run_results(run_id: str, ...):
    # Query biomarker results from database
    results = db.query(BiomarkerResult).filter(...).all()
    return {"biomarkers": results_data, ...}
```

### 5.2 Background Task Integration

**Location**: `backend/app/services/tasks/biomarker_tasks.py`

Celery tasks execute the genomics analysis asynchronously:

```python
@celery_app.task(bind=True)
def run_biomarker_analysis(self, run_id, expression_file_path, label_file_path, parameters):
    # 1. Update database status
    analysis_run.status = RunStatus.RUNNING.value
    
    # 2. Send WebSocket progress update
    manager.send_to_run(run_id, {"progress": 0, "status": "Starting..."})
    
    # 3. Initialize pipeline
    pipeline = BiomarkerPipeline()
    
    # 4. Run pipeline (THIS EXECUTES ALL GENOMICS ANALYSIS)
    results = pipeline.run_pipeline(
        expression_file=expression_file_path,
        labels_file=label_file_path,
        **parameters
    )
    
    # 5. Store results in database
    # 6. Update status to COMPLETED
    # 7. Send final WebSocket update
    
    return {"run_id": run_id, "status": "completed", "results": results}
```

### 5.3 Progress Callback Integration

The pipeline supports **progress callbacks** that integrate with WebSocket:

```python
# In biomarker_tasks.py
def update_progress(run_id, progress, status, task_id):
    # Update Celery task state
    current_task.update_state(
        state="PROGRESS",
        meta={"progress": progress, "status": status}
    )
    
    # Send WebSocket update
    manager.send_to_run(run_id, {
        "type": "progress_update",
        "progress": progress,
        "status": status,
        "task_id": task_id
    })
```

---

## 6. Real-Time Communication

### 6.1 WebSocket Manager

**Location**: `backend/app/websocket/manager.py`

The WebSocket manager provides **real-time bidirectional communication**:

```python
class ConnectionManager:
    def __init__(self):
        # Store connections by run_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, run_id: str):
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = set()
        self.active_connections[run_id].add(websocket)
    
    async def send_to_run(self, run_id: str, message: dict):
        """Send progress update to all connections for a run"""
        if run_id in self.active_connections:
            message_str = json.dumps(message)
            for websocket in self.active_connections[run_id]:
                await websocket.send_text(message_str)
```

### 6.2 Progress Update Integration

Progress updates are sent at **key pipeline stages**:

```python
# In biomarker_tasks.py
manager.send_to_run(run_id, {
    "type": "progress_update",
    "progress": 0,
    "status": "Starting biomarker analysis...",
    "task_id": self.request.id
})

# After each major step
manager.send_to_run(run_id, {
    "type": "progress_update",
    "progress": 20,
    "status": "Loading data...",
    "current_step": "data_loading"
})

manager.send_to_run(run_id, {
    "type": "progress_update",
    "progress": 50,
    "status": "Performing statistical analysis...",
    "current_step": "statistical_analysis"
})

manager.send_to_run(run_id, {
    "type": "progress_update",
    "progress": 70,
    "status": "Running machine learning selection...",
    "current_step": "ml_selection"
})
```

---

## 7. Database Integration

### 7.1 Analysis Run Tracking

**Location**: `backend/app/models/run_model.py`

The database tracks the **entire lifecycle** of each genomics analysis:

```python
class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    
    id = Column(String(36), primary_key=True)
    project_name = Column(String(200))
    status = Column(String(20))  # PENDING, RUNNING, COMPLETED, FAILED
    progress = Column(Float)     # 0.0 to 1.0
    current_step = Column(String(100))
    
    # Configuration
    analysis_type = Column(String(50))
    configuration = Column(JSON)  # All analysis parameters
    
    # File paths
    expression_file_path = Column(String(500))
    clinical_file_path = Column(String(500))
    
    # Results
    results_summary = Column(JSON)
    output_files = Column(JSON)
    
    # Relationships
    biomarker_results = relationship("BiomarkerResult", back_populates="analysis_run")
```

### 7.2 Biomarker Results Storage

**Location**: `backend/app/models/biomarker_model.py`

Each identified biomarker is stored with **all evidence**:

```python
class BiomarkerResult(Base):
    __tablename__ = "biomarker_results"
    
    id = Column(String(36), primary_key=True)
    run_id = Column(String(36), ForeignKey("analysis_runs.id"))
    gene_symbol = Column(String(50))
    
    # Statistical evidence
    p_value = Column(Float)
    adjusted_p_value = Column(Float)
    fold_change = Column(Float)
    effect_size = Column(Float)
    
    # ML evidence
    ml_score = Column(Float)
    consensus_score = Column(Float)
    selection_count = Column(Integer)
    
    # Combined score
    final_score = Column(Float)
    final_rank = Column(Integer)
    
    # Clinical annotations (JSON)
    clinical_annotations = Column(JSON)
    pathway_data = Column(JSON)
```

### 7.3 Result Querying

The API queries the database to retrieve results:

```python
@router.get("/runs/{run_id}/results")
async def get_run_results(run_id: str, db: Session = Depends(get_db)):
    # Get biomarker results
    results = db.query(BiomarkerResult).filter(
        BiomarkerResult.run_id == run_id
    ).all()
    
    # Format for frontend
    results_data = []
    for result in results:
        results_data.append({
            "gene": result.gene_symbol,
            "p_value": result.p_value,
            "fold_change": result.fold_change,
            "ml_score": result.ml_score,
            "final_score": result.final_score,
            "clinical_annotations": result.clinical_annotations,
            ...
        })
    
    return {"biomarkers": results_data}
```

---

## 8. Configuration Management

### 8.1 Unified Configuration System

**Location**: `backend/app/core/config.py`

All genomics analysis components share a **single configuration system**:

```python
class Settings(BaseSettings):
    # Statistical testing settings
    FDR_METHOD: str = "benjamini_hochberg"
    EFFECT_SIZE_METRIC: str = "cohens_d"
    
    # Machine learning settings
    CV_FOLDS: int = 5
    STABILITY_BOOTSTRAPS: int = 100
    FEATURE_SELECTION_THRESHOLD: float = 0.6
    
    # Preprocessing settings
    MIN_VARIANCE_GENES: int = 10000
    MAX_MISSING_RATE: float = 0.1
    BATCH_CORRECTION_METHOD: str = "combat"
    
    # External API settings
    COSMIC_API_KEY: Optional[str] = None
    ONCOKB_API_KEY: Optional[str] = None
```

### 8.2 Default Analysis Configuration

A **default configuration template** ensures consistency:

```python
DEFAULT_ANALYSIS_CONFIG = {
    "preprocessing": {
        "min_variance_genes": 10000,
        "log_transform": True,
        "batch_correction": "combat"
    },
    "statistical_testing": {
        "test_method": "welch_t",
        "fdr_method": "benjamini_hochberg",
        "multiple_testing_correction": True
    },
    "machine_learning": {
        "models": ["logistic_l1", "random_forest", "xgboost"],
        "cv_folds": 5,
        "feature_selection": {
            "method": "rfe",
            "n_features": [50, 100, 200],
            "stability_threshold": 0.6
        }
    },
    "annotation": {
        "pathway_databases": ["KEGG", "REACTOME"],
        "clinical_databases": ["COSMIC", "CLINVAR", "ONCOKB"]
    }
}
```

### 8.3 Configuration Propagation

Configuration is **propagated** to all components:

```python
# In BiomarkerPipeline.__init__()
self.config = config or {}
self.stats_pipeline = StatisticalPipeline(self.config)  # Pass config
self.ml_pipeline = MLSelectionPipeline(self.config)     # Pass config
```

---

## 9. Error Handling & Recovery

### 9.1 Error Handling at Each Level

#### Pipeline Level

```python
def run_pipeline(self, ...):
    try:
        # Execute pipeline steps
        ...
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        # Update database status
        analysis_run.set_error(str(e))
        # Send WebSocket error update
        manager.send_to_run(run_id, {
            "type": "error",
            "message": str(e)
        })
        raise
```

#### Component Level

```python
# In StatisticalPipeline
def run_statistical_analysis(self, ...):
    for method in analysis_methods:
        try:
            method_result = self.stats_analyzer.differential_expression_analysis(...)
            results["method_results"][method] = method_result
        except Exception as e:
            logger.error(f"Failed to run {method}: {str(e)}")
            results["method_results"][method] = {"error": str(e)}
            # Continue with other methods
```

### 9.2 Graceful Degradation

The system continues even if **some components fail**:

- If one statistical method fails, others continue
- If ML method fails, statistical results are still used
- If clinical annotation fails, biomarkers are still generated
- If pathway analysis fails, other results are still available

---

## 10. Performance Optimization

### 10.1 Caching Strategy

**Location**: `backend/app/services/cache_service.py`

Results are cached to avoid recomputation:

```python
# Cache statistical results
@cache_result(expire=3600)
def run_statistical_analysis(self, ...):
    # Expensive computation
    ...

# Cache ML results
@cache_result(expire=3600)
def run_ml_selection(self, ...):
    # Expensive computation
    ...
```

### 10.2 Parallel Processing

Some components support **parallel processing**:

```python
# In MLSelectionPipeline
def run_ml_selection(self, ...):
    # Run multiple methods in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(self.feature_selector.filter_methods, ...),
            executor.submit(self.feature_selector.wrapper_methods, ...),
            executor.submit(self.feature_selector.embedded_methods, ...)
        }
        # Collect results
        ...
```

### 10.3 Background Processing

All long-running analyses execute in **background Celery tasks**:

- Non-blocking API responses
- Scalable worker pool
- Task retry on failure
- Progress tracking

---

## Summary: Integration Points

### Key Integration Points

1. **BiomarkerPipeline** → Orchestrates all components
2. **StatisticalPipeline + MLSelectionPipeline** → Combined in biomarker list generation
3. **Database Models** → Store all results with relationships
4. **API Routes** → Trigger and retrieve analysis
5. **Celery Tasks** → Execute analysis asynchronously
6. **WebSocket Manager** → Real-time progress updates
7. **Configuration System** → Unified settings across components
8. **Error Handling** → Graceful degradation at each level

### Data Flow Summary

```
User Upload → API → Celery Task → BiomarkerPipeline
    ↓
DataIO → QualityControl → Normalization
    ↓
StatisticalPipeline ──┐
                      ├─→ Biomarker List Generation
MLSelectionPipeline ──┘
    ↓
Clinical Annotation → Pathway Analysis → Report Generation
    ↓
Database Storage ← WebSocket Updates ← API Results
```

---

## Conclusion

The **Cancer Genomics Analysis Suite** is fully integrated into the Cancer Biomarker Identifier platform through:

1. **Modular component architecture** with clear interfaces
2. **Unified pipeline orchestration** via BiomarkerPipeline
3. **Standardized data formats** for seamless data flow
4. **Real-time communication** via WebSocket
5. **Persistent storage** in PostgreSQL
6. **Asynchronous processing** via Celery
7. **Comprehensive error handling** with graceful degradation
8. **Unified configuration** system

All components work together as a **cohesive genomics analysis system** that provides end-to-end biomarker discovery capabilities.

