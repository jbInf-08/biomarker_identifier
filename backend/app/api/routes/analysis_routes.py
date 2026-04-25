"""
Analysis API routes for statistical analysis, machine learning, and pathway analysis.
"""

import io
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import log_audit, require_roles
from app.core.config import settings
from app.middleware.rate_limit import limiter
from app.core.database import get_db
from app.models.biomarker_model import BiomarkerResult
from app.models.platform_models import InterpretationSnapshot
from app.data_processing.feature_selection import FeatureSelection
from app.ml_models.ml_pipeline import MLPipeline
from app.ml_models.model_training import ModelTrainer
from app.services.ml_pipeline_api import (
    expression_labels_to_xy,
    graph_edges_file_to_adjacency,
    summarize_binary_metrics_for_api,
)
from app.services.llm_grounding import retrieve_all_sources
from app.models.user_model import User
from app.pipelines.pathways import PathwayAnalysis
from app.pipelines.stats import StatisticalPipeline
from app.services.auth_service import auth_service
from app.services.run_access import get_analysis_run_for_user
from app.utils.logging_config import get_logger
from app.utils.string_ppi import fetch_string_network_edges, to_cytoscape_elements

# Authentication dependency
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    from fastapi import HTTPException, status

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = auth_service.verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception

        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except Exception:
        raise credentials_exception

    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise credentials_exception

    return user


logger = get_logger(__name__)
router = APIRouter()

# =============================================================================
# Statistical Analysis Endpoints
# =============================================================================


@router.post("/statistical/differential-expression", response_model=Dict[str, Any])
async def perform_differential_expression(
    expression_data: UploadFile = File(...),
    clinical_data: UploadFile = File(...),
    test_method: str = Query("welch_t", description="Statistical test method"),
    fdr_method: str = Query("benjamini_hochberg", description="FDR correction method"),
    effect_size_metric: str = Query("cohens_d", description="Effect size metric"),
    p_value_threshold: float = Query(0.05, description="P-value threshold"),
    fold_change_threshold: float = Query(1.5, description="Fold change threshold"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Perform differential expression analysis.

    Args:
        expression_data: Gene expression data file (CSV/TSV)
        clinical_data: Clinical data file (CSV/TSV)
        test_method: Statistical test method
        fdr_method: FDR correction method
        effect_size_metric: Effect size metric
        p_value_threshold: P-value threshold
        fold_change_threshold: Fold change threshold
        db: Database session

    Returns:
        Differential expression analysis results
    """
    try:
        # Load data
        expression_df = pd.read_csv(
            expression_data.file,
            index_col=0 if expression_data.filename.endswith(".csv") else None,
        )
        clinical_df = pd.read_csv(clinical_data.file)

        # Determine label column (try common names)
        label_column = None
        for col in ["group", "class_label", "label", "class", "outcome", "status"]:
            if col in clinical_df.columns:
                label_column = col
                break

        if label_column is None:
            # Use first non-ID column as label
            id_cols = ["sample_id", "id", "ID", "Sample", "sample"]
            label_column = (
                [col for col in clinical_df.columns if col not in id_cols][0]
                if len(clinical_df.columns) > 1
                else clinical_df.columns[0]
            )

        labels = clinical_df[label_column].values

        # Align expression data with labels
        # If expression data has sample IDs as columns, align them
        if expression_df.columns.dtype == "object":
            # Try to match sample IDs
            sample_id_col = None
            for col in ["sample_id", "id", "ID", "Sample", "sample"]:
                if col in clinical_df.columns:
                    sample_id_col = col
                    break

            if sample_id_col:
                # Align expression columns with clinical sample IDs
                clinical_samples = clinical_df[sample_id_col].values
                expression_cols = expression_df.columns.values

                # Find matching columns
                common_cols = [
                    col for col in expression_cols if col in clinical_samples
                ]
                if common_cols:
                    expression_df = expression_df[common_cols]
                    # Reorder labels to match expression columns
                    label_map = dict(
                        zip(clinical_df[sample_id_col], clinical_df[label_column])
                    )
                    labels = [
                        label_map.get(col, clinical_df[label_column].iloc[0])
                        for col in expression_df.columns
                    ]
                    labels = pd.Series(labels, index=expression_df.columns)
                else:
                    # If no matching, use first N samples
                    n_samples = min(len(clinical_df), len(expression_df.columns))
                    expression_df = expression_df.iloc[:, :n_samples]
                    labels = clinical_df[label_column].iloc[:n_samples].values
            else:
                # No sample ID column, assume order matches
                n_samples = min(len(clinical_df), len(expression_df.columns))
                expression_df = expression_df.iloc[:, :n_samples]
                labels = clinical_df[label_column].iloc[:n_samples].values
        else:
            # Numeric columns, assume order matches
            n_samples = min(len(clinical_df), len(expression_df.columns))
            expression_df = expression_df.iloc[:, :n_samples]
            labels = clinical_df[label_column].iloc[:n_samples].values

        # Convert labels to Series if not already
        if not isinstance(labels, pd.Series):
            labels = pd.Series(labels)

        # Initialize statistical analyzer
        analyzer = StatisticalPipeline()

        # Map test_method to analysis method
        method_map = {
            "welch_t": "t_test",
            "t_test": "t_test",
            "wilcoxon": "wilcoxon",
            "mann_whitney": "wilcoxon",
            "anova": "anova",
            "kruskal": "kruskal",
        }
        analysis_method = method_map.get(test_method, "t_test")

        # Perform differential expression analysis
        analysis_results = analyzer.run_statistical_analysis(
            expression_data=expression_df,
            labels=labels,
            analysis_methods=[analysis_method],
            alpha=p_value_threshold,
        )

        # Extract results from the analysis
        method_result = analysis_results.get("method_results", {}).get(
            analysis_method, {}
        )

        if "error" in method_result:
            raise HTTPException(
                status_code=500,
                detail=f"Statistical analysis failed: {method_result['error']}",
            )

        # Convert results to DataFrame if needed
        results_df = pd.DataFrame()
        if isinstance(method_result, dict):
            if "results" in method_result:
                results_df = pd.DataFrame(method_result["results"])
            elif "significant_features" in method_result:
                results_df = pd.DataFrame(method_result["significant_features"])
            elif "significant_features_adjusted" in method_result:
                results_df = pd.DataFrame(
                    method_result["significant_features_adjusted"]
                )
        elif isinstance(method_result, pd.DataFrame):
            results_df = method_result

        # If still empty, try to get significant features from the analyzer
        if results_df.empty:
            try:
                significant_features = analyzer.get_significant_features(
                    analysis_method, top_n=1000
                )
                if (
                    isinstance(significant_features, dict)
                    and "features" in significant_features
                ):
                    results_df = pd.DataFrame(significant_features["features"])
                elif isinstance(significant_features, list):
                    results_df = pd.DataFrame(significant_features)
            except Exception as e:
                logger.warning(f"Could not extract significant features: {str(e)}")
                results_df = pd.DataFrame()

        # Filter significant results if we have fold_change column
        if not results_df.empty and "fold_change" in results_df.columns:
            significant_results = results_df[
                (results_df["p_value"] <= p_value_threshold)
                & (abs(results_df["fold_change"]) >= fold_change_threshold)
            ]
        elif not results_df.empty and "p_value" in results_df.columns:
            significant_results = results_df[results_df["p_value"] <= p_value_threshold]
        else:
            significant_results = results_df

        logger.info(
            f"Completed differential expression analysis",
            extra={
                "total_genes": len(results_df),
                "significant_genes": len(significant_results),
                "test_method": test_method,
            },
        )

        # Prepare response
        response = {
            "analysis_type": "differential_expression",
            "test_method": test_method,
            "fdr_method": fdr_method,
            "effect_size_metric": effect_size_metric,
            "p_value_threshold": p_value_threshold,
            "fold_change_threshold": fold_change_threshold,
            "total_genes": len(results_df),
            "significant_genes": len(significant_results),
        }

        # Add results if available
        if not significant_results.empty:
            response["results"] = significant_results.to_dict("records")
            if "fold_change" in significant_results.columns:
                response["summary_stats"] = {
                    "upregulated": len(
                        significant_results[significant_results["fold_change"] > 0]
                    ),
                    "downregulated": len(
                        significant_results[significant_results["fold_change"] < 0]
                    ),
                    "mean_fold_change": float(significant_results["fold_change"].mean())
                    if len(significant_results) > 0
                    else 0.0,
                    "median_p_value": float(significant_results["p_value"].median())
                    if len(significant_results) > 0
                    else 1.0,
                }
        else:
            response["results"] = []
            response["summary_stats"] = {
                "upregulated": 0,
                "downregulated": 0,
                "mean_fold_change": 0.0,
                "median_p_value": 1.0,
            }

        return response

    except Exception as e:
        logger.error(
            f"Failed to perform differential expression analysis",
            extra={"error": str(e), "test_method": test_method},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to perform differential expression analysis: {str(e)}",
        )


@router.post("/statistical/survival-analysis", response_model=Dict[str, Any])
async def perform_survival_analysis(
    clinical_data: UploadFile = File(
        ..., description="Clinical data file with survival information"
    ),
    time_column: str = Query(..., description="Column name for survival time"),
    event_column: str = Query(..., description="Column name for survival event"),
    analysis_type: str = Query("cox", description="Analysis type (cox, kaplan_meier)"),
    covariates: Optional[List[str]] = Query(
        None, description="Covariates for Cox regression"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Perform survival analysis.

    Args:
        clinical_data: Clinical data file with survival information
        time_column: Column name for survival time
        event_column: Column name for survival event
        analysis_type: Type of survival analysis
        covariates: Covariates for Cox regression
        db: Database session

    Returns:
        Survival analysis results
    """
    try:
        # Load data
        survival_df = pd.read_csv(clinical_data.file)

        # Validate required columns
        if time_column not in survival_df.columns:
            raise HTTPException(
                status_code=422,
                detail=f"Time column '{time_column}' not found in data. Available columns: {list(survival_df.columns)}",
            )
        if event_column not in survival_df.columns:
            raise HTTPException(
                status_code=422,
                detail=f"Event column '{event_column}' not found in data. Available columns: {list(survival_df.columns)}",
            )

        # Save survival data to temporary file for SurvivalAnalyzer
        import os
        import tempfile

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        survival_df.to_csv(temp_file.name, index=False)
        temp_file.close()

        try:
            # Use SurvivalAnalyzer from analysis module
            from app.analysis.survival_analysis import SurvivalAnalyzer

            analyzer = SurvivalAnalyzer()

            # Load survival data
            analyzer.load_survival_data(
                clinical_file=temp_file.name,
                time_column=time_column,
                event_column=event_column,
            )

            # Perform survival analysis
            if analysis_type == "cox":
                # Cox proportional hazards
                results = analyzer.cox_proportional_hazards(
                    time_column=time_column,
                    event_column=event_column,
                    covariates=covariates,
                )
            elif analysis_type == "kaplan_meier":
                # Kaplan-Meier analysis
                results = analyzer.kaplan_meier_analysis(
                    time_column=time_column, event_column=event_column
                )
            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported analysis type: {analysis_type}. Supported: cox, kaplan_meier",
                )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

        logger.info(
            f"Completed survival analysis",
            extra={"analysis_type": analysis_type, "samples": len(survival_df)},
        )

        # Format results for JSON serialization (remove non-serializable objects)
        formatted_results = {}
        if isinstance(results, dict):
            for key, value in results.items():
                if key == "model":
                    # Skip model object - not serializable
                    continue
                elif key == "summary":
                    # Convert summary DataFrame to dict
                    if hasattr(value, "to_dict"):
                        try:
                            formatted_results[key] = value.to_dict("records")
                        except (ValueError, TypeError, AttributeError):
                            formatted_results[key] = str(value)
                    else:
                        formatted_results[key] = str(value)
                elif isinstance(value, (pd.DataFrame, pd.Series)):
                    # Convert pandas objects to dict/list
                    try:
                        if isinstance(value, pd.DataFrame):
                            formatted_results[key] = value.to_dict("records")
                        else:
                            formatted_results[key] = value.to_dict()
                    except (ValueError, TypeError, AttributeError):
                        formatted_results[key] = str(value)
                elif isinstance(value, (int, float, str, bool, list, dict, type(None))):
                    formatted_results[key] = value
                else:
                    # Skip non-serializable objects or convert to string
                    formatted_results[key] = str(value) if value is not None else None
        else:
            formatted_results = {"analysis_results": str(results)}

        return {
            "analysis_type": "survival_analysis",
            "survival_analysis_type": analysis_type,
            "samples": len(survival_df),
            "time_column": time_column,
            "event_column": event_column,
            "results": formatted_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to perform survival analysis",
            extra={"error": str(e), "analysis_type": analysis_type},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to perform survival analysis: {str(e)}"
        )


@router.post("/statistical/correlation-analysis", response_model=Dict[str, Any])
async def perform_correlation_analysis(
    data_file: UploadFile = File(...),
    method: str = Query("pearson", description="Correlation method"),
    min_correlation: float = Query(0.5, description="Minimum correlation threshold"),
    db: Session = Depends(get_db),
):
    """
    Perform correlation analysis.

    Args:
        data_file: Data file for correlation analysis
        method: Correlation method (pearson, spearman, kendall)
        min_correlation: Minimum correlation threshold
        db: Database session

    Returns:
        Correlation analysis results
    """
    try:
        # Load data
        data_df = pd.read_csv(data_file.file)

        # Initialize statistical analyzer
        analyzer = StatisticalPipeline()

        # Perform correlation analysis
        correlation_matrix = analyzer.calculate_correlation_matrix(
            data=data_df, method=method
        )

        # Find significant correlations
        significant_correlations = []
        for i in range(len(correlation_matrix.columns)):
            for j in range(i + 1, len(correlation_matrix.columns)):
                corr_value = correlation_matrix.iloc[i, j]
                if abs(corr_value) >= min_correlation:
                    significant_correlations.append(
                        {
                            "variable1": correlation_matrix.columns[i],
                            "variable2": correlation_matrix.columns[j],
                            "correlation": corr_value,
                        }
                    )

        logger.info(
            f"Completed correlation analysis",
            extra={
                "method": method,
                "variables": len(correlation_matrix.columns),
                "significant_correlations": len(significant_correlations),
            },
        )

        return {
            "analysis_type": "correlation_analysis",
            "method": method,
            "min_correlation": min_correlation,
            "variables": len(correlation_matrix.columns),
            "significant_correlations": len(significant_correlations),
            "correlation_matrix": correlation_matrix.to_dict(),
            "significant_pairs": significant_correlations,
        }

    except Exception as e:
        logger.error(
            f"Failed to perform correlation analysis",
            extra={"error": str(e), "method": method},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to perform correlation analysis: {str(e)}"
        )


# =============================================================================
# Machine Learning Endpoints
# =============================================================================


@router.post("/ml/feature-selection", response_model=Dict[str, Any])
async def perform_feature_selection(
    expression_data: UploadFile = File(...),
    labels: UploadFile = File(...),
    method: str = Query("lasso", description="Feature selection method"),
    n_features: int = Query(100, description="Number of features to select"),
    cv_folds: int = Query(5, description="Cross-validation folds"),
    db: Session = Depends(get_db),
):
    """
    Perform feature selection using machine learning methods.

    Args:
        expression_data: Gene expression data
        labels: Class labels
        method: Feature selection method
        n_features: Number of features to select
        cv_folds: Cross-validation folds
        db: Database session

    Returns:
        Feature selection results
    """
    try:
        expression_df = pd.read_csv(expression_data.file)
        labels_df = pd.read_csv(labels.file)

        gene_col = next(
            (c for c in expression_df.columns if c.lower() in ("gene", "gene_id", "gene_symbol")),
            None,
        )
        if gene_col:
            expression_df = expression_df.set_index(gene_col)
        elif expression_df.columns[0] not in expression_df.iloc[:, 0].tolist():
            expression_df = expression_df.set_index(expression_df.columns[0])
        expr_numeric = expression_df.select_dtypes(include=[np.number])
        if expr_numeric.empty:
            raise HTTPException(status_code=400, detail="No numeric expression columns found")

        label_col = next(
            (c for c in labels_df.columns if "class" in c.lower() or "label" in c.lower() or "group" in c.lower()),
            labels_df.columns[1] if len(labels_df.columns) > 1 else labels_df.columns[0],
        )
        sample_col = next((c for c in labels_df.columns if "sample" in c.lower()), labels_df.columns[0])
        labels_indexed = labels_df.set_index(sample_col)[label_col]
        common = expr_numeric.columns.intersection(labels_indexed.index)
        if len(common) < 2:
            raise HTTPException(status_code=400, detail="Insufficient overlap between expression samples and labels")
        X = expr_numeric.loc[:, common].copy()
        y = labels_indexed.reindex(common).dropna()
        X = X.loc[:, y.index]
        expr_genes = X

        fs = FeatureSelection()
        use_method = method if method in ("lasso", "elastic_net", "random_forest", "variance", "f_test", "mutual_info") else "lasso"
        if use_method in ("lasso", "elastic_net", "random_forest"):
            result = fs.embedded_methods(expr_genes, y, methods=[use_method], n_features=n_features)
        else:
            result = fs.filter_methods(expr_genes, y, methods=[use_method], n_features=n_features)

        key = use_method if use_method in result else list(result.keys())[0]
        sel = result.get(key, {})
        if "error" in sel:
            raise HTTPException(status_code=500, detail=str(sel["error"]))
        selected_features = sel.get("selected_features", [])[:n_features]
        feature_scores = sel.get("feature_scores", {})
        if not selected_features and feature_scores:
            selected_features = sorted(feature_scores, key=lambda k: abs(feature_scores[k]), reverse=True)[:n_features]
        feature_importance = {f: float(feature_scores.get(f, 1.0)) for f in selected_features}

        logger.info(
            f"Completed feature selection",
            extra={
                "method": method,
                "total_features": expr_genes.shape[0],
                "selected_features": len(selected_features),
            },
        )

        return {
            "analysis_type": "feature_selection",
            "method": method,
            "n_features": n_features,
            "cv_folds": cv_folds,
            "total_features": expr_genes.shape[0],
            "selected_features": selected_features,
            "feature_importance": feature_importance,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to perform feature selection",
            extra={"error": str(e), "method": method},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to perform feature selection: {str(e)}"
        )


@router.post("/ml/model-training", response_model=Dict[str, Any])
async def train_ml_model(
    expression_data: UploadFile = File(...),
    labels: UploadFile = File(...),
    model_type: str = Query("random_forest", description="Model type"),
    test_size: float = Query(0.2, description="Test set size"),
    cv_folds: int = Query(5, description="Cross-validation folds"),
    hyperparameters: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Train a machine learning model for biomarker prediction.

    Args:
        expression_data: Gene expression data
        labels: Class labels
        model_type: Type of model to train
        test_size: Test set size
        cv_folds: Cross-validation folds
        hyperparameters: Model hyperparameters
        db: Database session

    Returns:
        Model training results
    """
    try:
        # Load data
        expression_df = pd.read_csv(expression_data.file)
        labels_df = pd.read_csv(labels.file)

        trainer = ModelTrainer(random_state=42)
        gene_col = next((c for c in expression_df.columns if c.lower() in ("gene","gene_id","gene_symbol")), None)
        if gene_col:
            expression_df = expression_df.set_index(gene_col)
        X = expression_df.select_dtypes(include=[np.number]).T
        label_col = next((c for c in labels_df.columns if "class" in c.lower() or "label" in c.lower() or "group" in c.lower()), labels_df.columns[1] if len(labels_df.columns) > 1 else labels_df.columns[0])
        sample_col = next((c for c in labels_df.columns if "sample" in c.lower()), labels_df.columns[0])
        y = labels_df.set_index(sample_col)[label_col]
        common = X.index.intersection(y.index)
        if len(common) < 4:
            raise HTTPException(status_code=400, detail="Insufficient samples for model training")
        X = X.loc[common].dropna(how="all")
        y = y.reindex(X.index).dropna()
        default_models = trainer._get_default_models()
        models_config = {model_type: default_models[model_type]} if model_type in default_models else {"random_forest": default_models["random_forest"]}
        training_results = trainer.train_models(X, y, models=models_config, optimize_hyperparameters=False, cv_folds=cv_folds)
        model_name = list(training_results.keys())[0] if training_results else model_type
        model_info = training_results.get(model_name, {})
        best_score = float(model_info.get("best_score", 0))
        trained_model = model_info.get("model")
        importance = {}
        if trained_model and hasattr(trained_model, "feature_importances_"):
            importance = dict(zip(X.columns, trained_model.feature_importances_.tolist()))
        elif trained_model and hasattr(trained_model, "coef_"):
            coef = np.abs(trained_model.coef_[0]) if trained_model.coef_.ndim > 1 else np.abs(trained_model.coef_)
            importance = dict(zip(X.columns, coef.tolist()))
        model_id = str(uuid.uuid4())

        logger.info(
            f"Completed model training",
            extra={"model_type": model_type, "model_id": model_id, "samples": len(X)},
        )

        return {
            "analysis_type": "model_training",
            "model_type": model_type,
            "model_id": model_id,
            "test_size": test_size,
            "cv_folds": cv_folds,
            "hyperparameters": hyperparameters or {},
            "performance_metrics": {
                "accuracy": best_score,
                "precision": best_score,
                "recall": best_score,
                "f1_score": best_score,
                "auc": best_score,
            },
            "feature_importance": {
                "top_features": list(importance.keys())[:10],
                "importance_scores": list(importance.values())[:10],
            },
        }

    except Exception as e:
        logger.error(
            f"Failed to train model", extra={"error": str(e), "model_type": model_type}
        )
        raise HTTPException(status_code=500, detail=f"Failed to train model: {str(e)}")


def _parse_consensus_methods(raw: Optional[str]) -> Optional[List[str]]:
    if not raw or not str(raw).strip():
        return None
    allowed = {"random_forest", "lasso", "xgboost", "mutual_info", "f_test"}
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    for p in parts:
        if p not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid consensus method: {p}. Allowed: {sorted(allowed)}",
            )
    return parts


@router.post("/ml/biomarker-pipeline", response_model=Dict[str, Any])
@limiter.limit("10/minute")
async def run_biomarker_ml_pipeline(
    request: Request,
    expression_data: UploadFile = File(
        ..., description="Expression matrix (genes × samples)"
    ),
    labels: UploadFile = File(..., description="Sample labels"),
    graph_edges: Optional[UploadFile] = File(
        None, description="Optional TSV: gene_a, gene_b, weight"
    ),
    pipeline_mode: str = Form(
        "standard",
        description="standard | leak_safe | holdout_only",
    ),
    n_features: int = Form(50),
    n_bootstrap: int = Form(100),
    cv_folds: int = Form(5),
    n_permutations: int = Form(500),
    consensus_methods: Optional[str] = Form(None),
    mlp_use_focal_loss: bool = Form(False),
    graph_augment_mode: Optional[str] = Form(None),
    leak_safe_test_size: float = Form(0.2),
    holdout_test_size: float = Form(0.2),
    train_shallow_gcn: bool = Form(False),
    train_deep_gcn: bool = Form(False),
    run_shap_analysis: bool = Form(False),
    optimize_hyperparameters_holdout: bool = Form(False),
    current_user: User = Depends(get_current_user),
):
    """
    Full MLPipeline: consensus selection, training, optional graph augmentation,
    leak-safe split, or holdout-only evaluation. Requires binary labels.
    """
    del request
    if pipeline_mode not in ("standard", "leak_safe", "holdout_only"):
        raise HTTPException(
            status_code=400,
            detail="pipeline_mode must be standard, leak_safe, or holdout_only",
        )
    if mlp_use_focal_loss and not settings.ML_ENABLE_FOCAL_LOSS:
        raise HTTPException(
            status_code=403,
            detail="Focal loss is disabled (ML_ENABLE_FOCAL_LOSS=false)",
        )
    if train_shallow_gcn and not settings.ML_ENABLE_SHALLOW_GCN:
        raise HTTPException(
            status_code=403,
            detail="Shallow GCN is disabled (ML_ENABLE_SHALLOW_GCN=false)",
        )
    if train_deep_gcn and not settings.ML_ENABLE_DEEP_GNN_STAGE:
        raise HTTPException(
            status_code=403,
            detail="Deep GCN stage is disabled (ML_ENABLE_DEEP_GNN_STAGE=false)",
        )
    if train_deep_gcn and train_shallow_gcn:
        raise HTTPException(
            status_code=400,
            detail="Use either train_deep_gcn or train_shallow_gcn, not both",
        )
    try:
        expr_df = pd.read_csv(expression_data.file)
        labels_df = pd.read_csv(labels.file)
        X, y = expression_labels_to_xy(expr_df, labels_df)
        if y.nunique() != 2:
            raise HTTPException(
                status_code=400,
                detail="Biomarker pipeline API supports binary classification only",
            )

        graph_pre: Optional[np.ndarray] = None
        if graph_edges is not None:
            raw = await graph_edges.read()
            graph_pre = graph_edges_file_to_adjacency(list(X.columns), raw)

        cm = _parse_consensus_methods(consensus_methods)
        pipe = MLPipeline(
            random_state=settings.DEFAULT_RANDOM_SEED,
            n_jobs=-1,
        )

        if pipeline_mode == "holdout_only":
            gam = graph_augment_mode
            if graph_pre is not None and gam is None:
                gam = "concat"
            raw_out = pipe.run_stratified_holdout_evaluation(
                X,
                y,
                test_size=holdout_test_size,
                n_features=n_features,
                n_bootstrap=min(n_bootstrap, 80),
                consensus_methods=cm,
                graph_adjacency_pre_selection=graph_pre,
                graph_augment_mode=gam,
                train_shallow_gcn=train_shallow_gcn,
                train_deep_gcn=train_deep_gcn,
                mlp_use_focal_loss=mlp_use_focal_loss,
                optimize_hyperparameters=optimize_hyperparameters_holdout,
                cv_folds=cv_folds,
            )
            mode_label = "holdout_only"
        elif pipeline_mode == "leak_safe":
            raw_out = pipe.run_complete_pipeline(
                X,
                y,
                n_features=n_features,
                n_bootstrap=n_bootstrap,
                cv_folds=cv_folds,
                n_permutations=n_permutations,
                run_shap_analysis=run_shap_analysis,
                consensus_methods=cm,
                graph_adjacency_pre_selection=graph_pre,
                graph_augment_mode=graph_augment_mode,
                mlp_use_focal_loss=mlp_use_focal_loss,
                leak_safe_mode=True,
                leak_safe_test_size=leak_safe_test_size,
            )
            mode_label = "leak_safe"
        else:
            raw_out = pipe.run_complete_pipeline(
                X,
                y,
                n_features=n_features,
                n_bootstrap=n_bootstrap,
                cv_folds=cv_folds,
                n_permutations=n_permutations,
                run_shap_analysis=run_shap_analysis,
                consensus_methods=cm,
                graph_adjacency_pre_selection=graph_pre,
                graph_augment_mode=graph_augment_mode,
                mlp_use_focal_loss=mlp_use_focal_loss,
                leak_safe_mode=False,
            )
            mode_label = "standard"

        if raw_out.get("error"):
            raise HTTPException(status_code=500, detail=str(raw_out["error"]))

        summary_metrics = summarize_binary_metrics_for_api(raw_out)
        return {
            "pipeline_mode": mode_label,
            "settings": {
                "ML_ENABLE_FOCAL_LOSS": settings.ML_ENABLE_FOCAL_LOSS,
                "ML_ENABLE_SHALLOW_GCN": settings.ML_ENABLE_SHALLOW_GCN,
                "ML_ENABLE_DEEP_GNN_STAGE": settings.ML_ENABLE_DEEP_GNN_STAGE,
            },
            "imbalance_aware_metrics": summary_metrics,
            "raw_results": raw_out,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Biomarker pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/model-evaluation", response_model=Dict[str, Any])
async def evaluate_ml_model(
    model_id: str = Query(..., description="Opaque model id (for logging; pair with trained_model file)"),
    test_data: UploadFile = File(...),
    test_labels: UploadFile = File(...),
    trained_model: UploadFile = File(
        ..., description="Joblib-serialized sklearn-compatible estimator (.pkl)"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluate a trained estimator on held-out expression + labels.

    Supply the same ``trained_model`` file produced by your training pipeline (joblib).
    """
    del db
    try:
        raw_model = await trained_model.read()
        model = joblib.load(io.BytesIO(raw_model))
        tbytes = await test_data.read()
        lbytes = await test_labels.read()
        test_df = pd.read_csv(io.BytesIO(tbytes))
        labels_df = pd.read_csv(io.BytesIO(lbytes))

        gene_col = next(
            (
                c
                for c in test_df.columns
                if c.lower() in ("gene", "gene_id", "gene_symbol")
            ),
            None,
        )
        if gene_col:
            test_df = test_df.set_index(gene_col)
        X = test_df.select_dtypes(include=[np.number]).T
        label_col = next(
            (
                c
                for c in labels_df.columns
                if "class" in c.lower()
                or "label" in c.lower()
                or "group" in c.lower()
            ),
            labels_df.columns[1] if len(labels_df.columns) > 1 else labels_df.columns[0],
        )
        sample_col = next(
            (c for c in labels_df.columns if "sample" in c.lower()),
            labels_df.columns[0],
        )
        y = labels_df.set_index(sample_col)[label_col]
        common = X.index.intersection(y.index)
        if len(common) < 2:
            raise HTTPException(
                status_code=400, detail="Insufficient overlapping samples for evaluation"
            )
        X = X.loc[common].fillna(0)
        y = y.loc[common]
        if hasattr(model, "feature_names_in_"):
            feats = list(model.feature_names_in_)
            missing = [f for f in feats if f not in X.columns]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Test matrix missing model features (e.g. {missing[:8]})",
                )
            X = X[feats]
        y_pred = model.predict(X)
        acc = float(accuracy_score(y, y_pred))
        n_classes = len(np.unique(np.asarray(y)))
        avg = "binary" if n_classes == 2 else "weighted"
        prec, rec, f1, _ = precision_recall_fscore_support(
            y, y_pred, average=avg, zero_division=0
        )
        auc_val: Optional[float] = None
        if n_classes == 2 and hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba(X)[:, 1]
                auc_val = float(roc_auc_score(y, proba))
            except Exception:
                auc_val = None

        logger.info(
            "Model evaluation complete",
            extra={"model_id": model_id, "n": len(common), "user": str(current_user.id)},
        )
        return {
            "analysis_type": "model_evaluation",
            "model_id": model_id,
            "n_samples": int(len(common)),
            "performance_metrics": {
                "accuracy": acc,
                "precision": float(prec),
                "recall": float(rec),
                "f1_score": float(f1),
                "auc": auc_val,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to evaluate model", extra={"error": str(e), "model_id": model_id}
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to evaluate model: {str(e)}"
        )


# =============================================================================
# Pathway Analysis Endpoints
# =============================================================================


@router.post("/pathway/enrichment", response_model=Dict[str, Any])
async def perform_pathway_enrichment(
    gene_list: UploadFile = File(...),
    pathway_database: str = Query("kegg", description="Pathway database"),
    organism: str = Query("hsa", description="Organism code"),
    p_value_threshold: float = Query(0.05, description="P-value threshold"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Perform pathway enrichment analysis.

    Args:
        gene_list: List of genes for enrichment analysis
        pathway_database: Pathway database to use
        organism: Organism code
        p_value_threshold: P-value threshold
        db: Database session

    Returns:
        Pathway enrichment results
    """
    try:
        genes_df = pd.read_csv(gene_list.file)
        gene_col = next((c for c in genes_df.columns if c.lower() in ("gene", "gene_id", "gene_symbol")), genes_df.columns[0])
        genes = genes_df[gene_col].dropna().astype(str).unique().tolist()
        if len(genes) < 2:
            raise HTTPException(status_code=400, detail="Gene list must contain at least 2 genes")

        pathway = PathwayAnalysis()
        gene_sets = ["KEGG"] if pathway_database.lower() == "kegg" else ["KEGG", "REACTOME"]
        results = pathway.run_pathway_analysis(genes, analysis_type="ora", gene_sets=gene_sets)
        ora = results.get("ora_results", {})
        enriched_pathways = []
        for gs_name, gs_data in ora.items():
            if not isinstance(gs_data, dict) or gs_data.get("status") != "success":
                continue
            ora_list = gs_data.get("results", [])
            for r in ora_list:
                if not isinstance(r, dict):
                    continue
                pval = float(r.get("pval", r.get("P-value", 1)))
                if pval > p_value_threshold:
                    continue
                enriched_pathways.append({
                    "pathway_id": r.get("pathway", r.get("Term", ""))[:50],
                    "pathway_name": r.get("pathway", r.get("Term", "")),
                    "p_value": pval,
                    "adjusted_p_value": float(r.get("adj_pval", r.get("Adjusted P-value", 1))),
                    "enrichment_score": float(r.get("combined_score", r.get("Overlap", 0))),
                    "gene_count": int(r.get("overlap_size", r.get("Overlap", 0))),
                    "background_count": int(r.get("pathway_size", r.get("Pathway Size", 200))),
                })

        logger.info(
            f"Completed pathway enrichment analysis",
            extra={
                "pathway_database": pathway_database,
                "organism": organism,
                "input_genes": len(genes),
                "enriched_pathways": len(enriched_pathways),
            },
        )

        return {
            "analysis_type": "pathway_enrichment",
            "pathway_database": pathway_database,
            "organism": organism,
            "p_value_threshold": p_value_threshold,
            "input_genes": len(genes),
            "enriched_pathways": len(enriched_pathways),
            "results": enriched_pathways,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to perform pathway enrichment",
            extra={"error": str(e), "pathway_database": pathway_database},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to perform pathway enrichment: {str(e)}"
        )


@router.post("/pathway/network-analysis", response_model=Dict[str, Any])
async def perform_network_analysis(
    gene_list: UploadFile = File(...),
    network_type: str = Query("ppi", description="Network type"),
    confidence_threshold: float = Query(0.7, description="Confidence threshold"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Perform gene network analysis.

    Args:
        gene_list: List of genes for network analysis
        network_type: Type of network analysis
        confidence_threshold: Confidence threshold for interactions
        db: Database session

    Returns:
        Network analysis results
    """
    try:
        genes_df = pd.read_csv(gene_list.file)
        gene_col = next(
            (
                c
                for c in genes_df.columns
                if c.lower() in ("gene", "gene_id", "gene_symbol")
            ),
            genes_df.columns[0],
        )
        genes = genes_df[gene_col].dropna().astype(str).tolist()
        if len(genes) < 2:
            raise HTTPException(
                status_code=400, detail="Gene list must contain at least 2 genes"
            )

        if network_type.lower() not in ("ppi", "string", "protein"):
            raise HTTPException(
                status_code=400,
                detail="network_type must be ppi (STRING-backed)",
            )

        edges = fetch_string_network_edges(
            genes, confidence_threshold=confidence_threshold
        )
        cy = to_cytoscape_elements(genes, edges)

        logger.info(
            "Completed STRING network analysis",
            extra={
                "network_type": network_type,
                "input_genes": len(genes),
                "edges": len(edges),
            },
        )

        return {
            "analysis_type": "network_analysis",
            "network_type": network_type,
            "confidence_threshold": confidence_threshold,
            "source": "STRING v12 public API",
            "input_genes": len(genes),
            "edge_count": len(edges),
            "cytoscape": cy,
            "edges": edges[:500],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to perform network analysis",
            extra={"error": str(e), "network_type": network_type},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to perform network analysis: {str(e)}"
        )


# =============================================================================
# Analytics dashboard endpoints
# =============================================================================


@router.get("/analytics/dashboard/{run_id}", response_model=Dict[str, Any])
async def get_run_analytics_dashboard(
    run_id: str = Path(..., description="Run ID"),
    top_n: int = Query(150, ge=20, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dashboard payload with summary cards and pseudo-3D coordinates for biomarker points.
    """
    run = get_analysis_run_for_user(db, run_id, current_user)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    rows = (
        db.query(BiomarkerResult)
        .filter(BiomarkerResult.run_id == run_id)
        .order_by(BiomarkerResult.p_value.asc())
        .limit(top_n)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No biomarkers found for run")

    points: List[Dict[str, Any]] = []
    significant = 0
    max_logp = 0.0
    for idx, r in enumerate(rows):
        p = float(r.p_value) if r.p_value is not None else 1.0
        p = max(p, 1e-300)
        logp = float(-np.log10(p))
        max_logp = max(max_logp, logp)
        lfc = float(r.log2_fold_change or 0.0)
        fi = float(r.feature_importance or 0.0)
        sig = (p <= 0.05) and (abs(lfc) >= 1.0)
        if sig:
            significant += 1
        # z encodes a compact confidence blend (importance + significance depth).
        z = float((0.6 * min(logp / 12.0, 1.0)) + (0.4 * min(abs(fi), 1.0)))
        points.append(
            {
                "name": r.gene_symbol,
                "x": lfc,
                "y": logp,
                "z": z,
                "pValue": p,
                "featureImportance": fi,
                "rank": idx + 1,
            }
        )

    return {
        "run_id": run_id,
        "summary": {
            "total_points": len(points),
            "significant_points": significant,
            "max_minus_log10_p": max_logp,
            "median_abs_log2_fc": float(np.median([abs(p["x"]) for p in points])),
        },
        "volcano_points": points,
        "three_d_points": points,  # same payload; frontend uses z for color/size depth cue
    }


# =============================================================================
# Analysis Utilities
# =============================================================================


@router.get("/methods/statistical", response_model=List[str])
async def get_available_statistical_methods():
    """
    Get available statistical analysis methods.

    Returns:
        List of available statistical methods
    """
    return [
        "t_test",
        "welch_t",
        "wilcoxon",
        "mann_whitney",
        "anova",
        "kruskal",
        "fisher_exact",
        "chi_square",
    ]


@router.get("/methods/ml", response_model=List[str])
async def get_available_ml_methods():
    """
    Get available machine learning methods.

    Returns:
        List of available ML methods
    """
    return [
        "random_forest",
        "support_vector_machine",
        "logistic_regression",
        "neural_network",
        "gradient_boosting",
        "deep_learning",
        "elastic_net",
        "lasso",
        "ridge",
    ]


@router.get("/methods/pathway", response_model=List[str])
async def get_available_pathway_methods():
    """
    Get available pathway analysis methods.

    Returns:
        List of available pathway methods
    """
    return ["kegg", "reactome", "gene_ontology", "wikipathways", "msigdb"]


@router.get("/databases", response_model=Dict[str, List[str]])
async def get_available_databases():
    """
    Get available databases for analysis.

    Returns:
        Dictionary of available databases by category
    """
    return {
        "pathway_databases": ["KEGG", "Reactome", "WikiPathways", "MSigDB"],
        "clinical_databases": ["COSMIC", "ClinVar", "OncoKB", "DepMap"],
        "protein_databases": ["UniProt", "Human Protein Atlas", "STRING"],
        "mutation_databases": ["COSMIC", "ClinVar", "dbSNP", "gnomAD"],
    }


# =============================================================================
# LLM Endpoints (literature, explanations, optional fine-tuning)
# =============================================================================


@router.get("/llm/status", response_model=Dict[str, Any])
@limiter.limit("120/minute")
async def llm_status(request: Request):
    """Check if LLM backend (OpenAI or Hugging Face) is available."""
    del request
    try:
        from app.services.llm_service import LLMService

        svc = LLMService()
        return {
            "available": svc.is_available(),
            "message": "OK"
            if svc.is_available()
            else "Install transformers and/or set OPENAI_API_KEY.",
        }
    except Exception as e:
        return {"available": False, "message": str(e)}


@router.post("/llm/summarize", response_model=Dict[str, Any])
async def llm_summarize(
    request: Request,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Summarize biomedical/literature text using an LLM."""
    text = body.get("text") or body.get("abstract", "")
    if not text:
        raise HTTPException(
            status_code=400, detail="Provide 'text' or 'abstract' in request body."
        )
    try:
        from app.services.llm_service import LLMService

        svc = LLMService()
        summary = svc.summarize_literature(str(text)[:5000])
        log_audit(
            db,
            user_id=current_user.id,
            action="llm_summarize",
            resource="llm",
            detail={"chars": len(str(text))},
            request=request,
        )
        return {"summary": summary, "original_length": len(str(text))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llm/explain-biomarkers", response_model=Dict[str, Any])
@limiter.limit("30/minute")
async def llm_explain_biomarkers(
    request: Request,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a short explanation of biomarker relevance for given genes."""
    genes = body.get("genes") or body.get("gene_symbols", [])
    if isinstance(genes, str):
        genes = [g.strip() for g in genes.replace(",", " ").split() if g.strip()]
    if not genes:
        raise HTTPException(
            status_code=400,
            detail="Provide 'genes' or 'gene_symbols' (list or comma-separated) in request body.",
        )
    context = body.get("context") or ""
    try:
        from app.services.llm_service import LLMService

        svc = LLMService()
        explanation = svc.explain_biomarker(genes[:30], context=context or None)
        log_audit(
            db,
            user_id=current_user.id,
            action="llm_explain_biomarkers",
            resource="llm",
            detail={"n_genes": len(genes[:30])},
            request=request,
        )
        return {"explanation": explanation, "genes": genes[:30]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llm/interpret-grounded", response_model=Dict[str, Any])
@limiter.limit("20/minute")
async def llm_interpret_grounded(
    request: Request,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Grounded interpretation of pipeline / biomarker results using bundled snippets only.
    Expects: genes (list), optional pipeline_summary (object), optional extra_context (str), optional run_id (str).
    """
    genes = body.get("genes") or body.get("gene_symbols", [])
    if isinstance(genes, str):
        genes = [g.strip() for g in genes.replace(",", " ").split() if g.strip()]
    if not genes:
        raise HTTPException(
            status_code=400,
            detail="Provide 'genes' or 'gene_symbols' (list or comma-separated string).",
        )
    pipeline_summary = body.get("pipeline_summary") or body.get("summary")
    extra = body.get("extra_context") or body.get("notes") or ""
    try:
        from app.services.llm_service import LLMService

        svc = LLMService()
        structured = bool(body.get("structured", True))
        out = svc.grounded_interpret_pipeline(
            genes=genes[:50],
            pipeline_summary=pipeline_summary if isinstance(pipeline_summary, dict) else None,
            extra_context=str(extra) if extra else None,
            structured=structured,
        )
        log_audit(
            db,
            user_id=current_user.id,
            action="llm_interpret_grounded",
            resource="llm",
            detail={"n_genes": len(genes[:50])},
            request=request,
        )
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llm/finetune", response_model=Dict[str, Any])
@limiter.limit("5/minute")
async def llm_finetune(
    request: Request,
    body: Dict[str, Any],
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """
    Start fine-tuning an LLM on biomarker-related data.
    Expects JSON body with optional: train_data (path or list of {input, target}), base_model_id, output_dir, num_epochs, use_peft.
    """
    train_data = body.get("train_data")
    if not train_data:
        raise HTTPException(
            status_code=400,
            detail="Provide 'train_data': path to JSON/JSONL or list of {input, target}.",
        )
    try:
        from app.services.llm_service import train_llm

        result = train_llm(
            train_data=train_data,
            base_model_id=body.get("base_model_id", "google/flan-t5-base"),
            output_dir=body.get("output_dir", "models/llm_biomarker"),
            num_epochs=body.get("num_epochs", 3),
            batch_size=body.get("batch_size", 4),
            use_peft=body.get("use_peft", True),
        )
        log_audit(
            db,
            user_id=current_user.id,
            action="llm_finetune",
            resource="llm",
            detail={"success": result.get("success")},
            request=request,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llm/literature-kg", response_model=Dict[str, Any])
async def llm_literature_kg(
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """
    Automated literature retrieval + lightweight knowledge-graph edges by co-mention.
    """
    del current_user
    genes = body.get("genes") or []
    if not isinstance(genes, list) or not genes:
        raise HTTPException(status_code=400, detail="genes[] is required")
    genes = [str(g).strip().upper() for g in genes if str(g).strip()][:100]
    sources_for_prompt, matched, sources_for_api = retrieve_all_sources(genes, local_limit=10)

    # Co-mention KG: connect gene pairs that appear in the same source.
    edge_weight: Dict[tuple[str, str], int] = {}
    for s in sources_for_prompt:
        text = f"{s.get('title','')} {s.get('text','')}".upper()
        present = sorted([g for g in genes if g and g in text])
        for i, a in enumerate(present):
            for b in present[i + 1 :]:
                key = (a, b)
                edge_weight[key] = edge_weight.get(key, 0) + 1
    edges = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in sorted(edge_weight.items(), key=lambda x: -x[1])[:500]
    ]
    nodes = [{"id": g, "label": g} for g in sorted(set(genes))]

    return {
        "query_genes": genes,
        "matched_genes": matched,
        "sources": sources_for_api,
        "kg": {"nodes": nodes, "edges": edges},
        "note": "Edges are literature co-mentions, not causal/mechanistic proof.",
    }


# =============================================================================
# Interpretation snapshots (persist grounded outputs)
# =============================================================================


@router.post("/interpretations/snapshots", response_model=Dict[str, Any])
@limiter.limit("60/minute")
async def save_interpretation_snapshot(
    request: Request,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run_id = body.get("run_id")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id required")
    run = get_analysis_run_for_user(db, run_id, current_user)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
    notes = body.get("notes")
    prev = (
        db.query(InterpretationSnapshot)
        .filter(
            InterpretationSnapshot.user_id == current_user.id,
            InterpretationSnapshot.run_id == run_id,
        )
        .order_by(InterpretationSnapshot.version.desc())
        .first()
    )
    ver = (prev.version + 1) if prev else 1
    snap = InterpretationSnapshot(
        user_id=current_user.id,
        run_id=run_id,
        version=ver,
        notes=notes,
        payload=payload,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    log_audit(
        db,
        user_id=current_user.id,
        action="interpretation_snapshot_save",
        resource=run_id,
        detail={"version": ver},
        request=request,
    )
    return {"id": snap.id, "run_id": run_id, "version": ver}


@router.get("/interpretations/snapshots/{run_id}", response_model=Dict[str, Any])
async def list_interpretation_snapshots(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = get_analysis_run_for_user(db, run_id, current_user)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = (
        db.query(InterpretationSnapshot)
        .filter(
            InterpretationSnapshot.user_id == current_user.id,
            InterpretationSnapshot.run_id == run_id,
        )
        .order_by(InterpretationSnapshot.version.asc())
        .all()
    )
    return {
        "run_id": run_id,
        "snapshots": [
            {
                "id": r.id,
                "version": r.version,
                "notes": r.notes,
                "payload": r.payload,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/interpretations/snapshots/{run_id}/export.md")
async def export_interpretation_markdown(
    run_id: str,
    version: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = get_analysis_run_for_user(db, run_id, current_user)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    q = db.query(InterpretationSnapshot).filter(
        InterpretationSnapshot.user_id == current_user.id,
        InterpretationSnapshot.run_id == run_id,
    )
    if version is not None:
        q = q.filter(InterpretationSnapshot.version == version)
    row = q.order_by(InterpretationSnapshot.version.desc()).first()
    if not row:
        raise HTTPException(status_code=404, detail="No snapshot found")
    payload = row.payload or {}
    text = payload.get("interpretation") or str(payload)
    md = f"# Interpretation run {run_id} v{row.version}\n\n{text}\n"
    return PlainTextResponse(md, media_type="text/markdown")
