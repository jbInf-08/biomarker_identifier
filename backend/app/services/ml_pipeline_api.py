"""
Helpers for exposing MLPipeline via the HTTP API (multipart uploads → X, y, graph).
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.ml_models.graph_augmented import adjacency_from_named_edges


def expression_labels_to_xy(
    expression_df: pd.DataFrame,
    labels_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Build samples × genes matrix and aligned labels (same conventions as model-training route).
    """
    gene_col = next(
        (
            c
            for c in expression_df.columns
            if c.lower() in ("gene", "gene_id", "gene_symbol")
        ),
        None,
    )
    if gene_col:
        expression_df = expression_df.set_index(gene_col)
    X = expression_df.select_dtypes(include=[np.number]).T
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
    if len(common) < 4:
        raise ValueError("Insufficient samples for ML pipeline (need at least 4)")
    X = X.loc[common].dropna(how="all")
    y = y.reindex(X.index).dropna()
    y_series = y.astype(int) if y.dtype != object else pd.Series(
        pd.Categorical(y).codes, index=y.index
    )
    return X, y_series


def graph_edges_file_to_adjacency(
    gene_columns: List[str],
    edges_bytes: bytes,
) -> np.ndarray:
    """
    TSV/CSV with columns: gene_a, gene_b, weight (weight optional, default 1).
    """
    df = pd.read_csv(io.BytesIO(edges_bytes), sep=None, engine="python")
    if df.shape[1] < 2:
        raise ValueError("Graph edges file needs at least two columns (gene_a, gene_b)")
    edges: List[Tuple[str, str, float]] = []
    for _, row in df.iterrows():
        a, b = str(row.iloc[0]), str(row.iloc[1])
        w = float(row.iloc[2]) if len(row) > 2 else 1.0
        edges.append((a, b, w))
    return adjacency_from_named_edges(gene_columns, edges)


def summarize_binary_metrics_for_api(
    results: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Pull PR-AUC, MCC, balanced accuracy, minority recall from pipeline or holdout payloads.
    """
    out: Dict[str, Any] = {"binary_task": True, "metrics": {}}
    # run_stratified_holdout_evaluation
    if "evaluation" in results and "per_model" in results["evaluation"]:
        per = results["evaluation"]["per_model"]
        out["metrics"]["stratified_holdout_per_model"] = {
            k: {
                "average_precision": v.get("average_precision"),
                "matthews_corrcoef": v.get("matthews_corrcoef"),
                "balanced_accuracy": v.get("balanced_accuracy"),
                "recall_minority_class": v.get("recall_minority_class"),
                "accuracy_may_be_misleading": v.get("accuracy_may_be_misleading"),
            }
            for k, v in per.items()
        }
    if "holdout_test_evaluation" in results:
        per = results["holdout_test_evaluation"].get("per_model", {})
        out["metrics"]["per_model_holdout_test"] = {
            k: {
                "average_precision": v.get("average_precision"),
                "matthews_corrcoef": v.get("matthews_corrcoef"),
                "balanced_accuracy": v.get("balanced_accuracy"),
                "recall_minority_class": v.get("recall_minority_class"),
                "accuracy_may_be_misleading": v.get("accuracy_may_be_misleading"),
            }
            for k, v in per.items()
        }
    if "pipeline_summary" in results:
        pm = results["pipeline_summary"].get("performance_metrics", {})
        if pm:
            out["metrics"]["cv_summary"] = {
                "average_precision": pm.get("average_precision"),
                "matthews_corrcoef": pm.get("matthews_corrcoef"),
                "balanced_accuracy": pm.get("balanced_accuracy"),
            }
        htm = results["pipeline_summary"].get("holdout_test_metrics")
        if htm:
            out["metrics"]["best_model_holdout_test"] = {
                "average_precision": htm.get("average_precision"),
                "matthews_corrcoef": htm.get("matthews_corrcoef"),
                "balanced_accuracy": htm.get("balanced_accuracy"),
                "recall_minority_class": htm.get("recall_minority_class"),
            }
    return out
