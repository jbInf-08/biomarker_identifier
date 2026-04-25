"""
Rigorous classification evaluation for biomarker workflows.

Separates *what* is measured (task, cohort, label definition) from *how* it is
computed (metrics, splits, statistical tests). Includes imbalance-aware metrics
and paired comparisons suitable for rare-positive settings.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    matthews_corrcoef,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)

DEFAULT_IMBALANCE_RATIO_WARN = 10.0


def label_prevalence(y: np.ndarray) -> Dict[str, Any]:
    """Class counts and imbalance ratio (majority count / minority count)."""
    y = np.asarray(y).ravel()
    bc = np.bincount(y.astype(int))
    if len(bc) < 2:
        return {
            "n_classes": int(len(bc)),
            "counts": bc.tolist(),
            "imbalance_ratio": float("inf"),
        }
    maj = int(bc.max())
    min_ = int(bc.min())
    ratio = maj / min_ if min_ > 0 else float("inf")
    return {
        "n_classes": int(len(bc)),
        "counts": bc.tolist(),
        "imbalance_ratio": float(ratio),
    }


def compute_binary_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_score: Optional[np.ndarray] = None,
    *,
    positive_label: int = 1,
    imbalance_warn_ratio: float = DEFAULT_IMBALANCE_RATIO_WARN,
) -> Dict[str, Any]:
    """
    Comprehensive metrics for binary classification.

    When class imbalance is extreme, ``accuracy`` can be misleading; we surface
    PR-AUC, balanced accuracy, MCC, and recall on the minority (positive) class.
    """
    y_true = np.asarray(y_true).ravel()
    y_pred = np.asarray(y_pred).ravel()
    prev = label_prevalence(y_true)
    metrics: Dict[str, Any] = {
        "task_prevalence": prev,
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "matthews_corrcoef": float(matthews_corrcoef(y_true, y_pred)),
    }

    # Minority class = smaller count (typical rare-positive setting)
    counts = prev.get("counts", [])
    if len(counts) >= 2:
        minority = int(np.argmin(counts))
        metrics["minority_class_label"] = minority
        metrics["recall_minority_class"] = float(
            recall_score(
                y_true,
                y_pred,
                pos_label=minority,
                average="binary",
                zero_division=0,
            )
        )
    else:
        metrics["recall_minority_class"] = float("nan")

    if positive_label == 1:
        metrics["recall_positive"] = float(
            recall_score(y_true, y_pred, pos_label=1, zero_division=0)
        )
    else:
        metrics["recall_positive"] = float(
            recall_score(y_true, y_pred, pos_label=positive_label, zero_division=0)
        )

    if y_score is not None:
        y_score = np.asarray(y_score).ravel()
        try:
            metrics["roc_auc"] = float(roc_auc_score(y_true, y_score))
        except ValueError as e:
            logger.debug("roc_auc skipped: %s", e)
            metrics["roc_auc"] = float("nan")
        try:
            metrics["average_precision"] = float(
                average_precision_score(y_true, y_score)
            )
        except ValueError as e:
            logger.debug("average_precision skipped: %s", e)
            metrics["average_precision"] = float("nan")
    else:
        metrics["roc_auc"] = float("nan")
        metrics["average_precision"] = float("nan")

    ratio = prev.get("imbalance_ratio", 1.0)
    metrics["accuracy_may_be_misleading"] = bool(ratio >= imbalance_warn_ratio)
    if metrics["accuracy_may_be_misleading"]:
        metrics["reporting_note"] = (
            f"Class imbalance ratio {ratio:.1f}:1 — prefer PR-AUC, MCC, "
            "balanced accuracy, and minority recall over headline accuracy."
        )
    return metrics


def mcnemar_test(
    y_true: np.ndarray,
    pred_a: np.ndarray,
    pred_b: np.ndarray,
) -> Dict[str, Any]:
    """
    McNemar's test on paired discriminators (same test set).

    2x2 table (rows: A correct/wrong, cols: B correct/wrong).
    Discordant cells are n01 (A wrong, B right) and n10 (A right, B wrong).
    """
    y_true = np.asarray(y_true).ravel()
    pred_a = np.asarray(pred_a).ravel()
    pred_b = np.asarray(pred_b).ravel()
    correct_a = pred_a == y_true
    correct_b = pred_b == y_true
    n11 = int(np.sum(correct_a & correct_b))
    n10 = int(np.sum(correct_a & ~correct_b))
    n01 = int(np.sum(~correct_a & correct_b))
    n00 = int(np.sum(~correct_a & ~correct_b))
    table = [[n00, n01], [n10, n11]]
    # McNemar chi-square (with continuity correction); compatible with older SciPy
    if n01 + n10 == 0:
        stat, pval = 0.0, 1.0
    else:
        stat = (abs(n01 - n10) - 1.0) ** 2 / (n01 + n10)
        pval = float(stats.chi2.sf(stat, df=1))
    # n01 = A wrong & B right; n10 = A right & B wrong (discordant pairs for McNemar)
    return {
        "statistic": float(stat),
        "pvalue": pval,
        "table": {
            "n00_both_wrong": n00,
            "n01_a_wrong_b_right": n01,
            "n10_a_right_b_wrong": n10,
            "n11_both_correct": n11,
        },
        "discordant_counts": {
            "a_right_b_wrong": n10,
            "a_wrong_b_right": n01,
        },
    }


def bootstrap_paired_auc_delta(
    y_true: np.ndarray,
    score_a: np.ndarray,
    score_b: np.ndarray,
    *,
    n_bootstrap: int = 1000,
    random_state: Optional[int] = None,
    stratified: bool = True,
) -> Dict[str, float]:
    """
    Bootstrap distribution of ROC-AUC(a) - ROC-AUC(b) on the same test labels.

    Paired resampling preserves sample pairing between scores.
    """
    rng = np.random.default_rng(random_state)
    y_true = np.asarray(y_true).ravel()
    score_a = np.asarray(score_a).ravel()
    score_b = np.asarray(score_b).ravel()
    n = len(y_true)
    deltas = []
    for _ in range(n_bootstrap):
        if stratified and len(np.unique(y_true)) == 2:
            idx0 = rng.choice(
                np.where(y_true == 0)[0], size=np.sum(y_true == 0), replace=True
            )
            idx1 = rng.choice(
                np.where(y_true == 1)[0], size=np.sum(y_true == 1), replace=True
            )
            idx = np.concatenate([idx0, idx1])
        else:
            idx = rng.choice(n, size=n, replace=True)
        if len(np.unique(y_true[idx])) < 2:
            continue
        try:
            auc_a = roc_auc_score(y_true[idx], score_a[idx])
            auc_b = roc_auc_score(y_true[idx], score_b[idx])
            deltas.append(auc_a - auc_b)
        except ValueError:
            continue
    if not deltas:
        return {"median_delta": float("nan"), "ci95_low": float("nan"), "ci95_high": float("nan")}
    d = np.array(deltas)
    q = np.quantile(d, [0.025, 0.5, 0.975])
    return {
        "median_delta": float(q[1]),
        "ci95_low": float(q[0]),
        "ci95_high": float(q[2]),
    }


def holdout_multimodel_report(
    fitted_models: Dict[str, Any],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    *,
    mcnemar_pairs: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Evaluate fitted classifiers on a held-out set with imbalance-aware metrics.

    Optionally runs McNemar on named pairs (same ``y_test``).
    """
    y_true = np.asarray(y_test).ravel()
    out: Dict[str, Any] = {"per_model": {}, "mcnemar": {}}
    preds: Dict[str, np.ndarray] = {}
    probs: Dict[str, np.ndarray] = {}

    for name, model in fitted_models.items():
        pred = model.predict(X_test)
        preds[name] = np.asarray(pred).ravel()
        if hasattr(model, "predict_proba"):
            pr = model.predict_proba(X_test)
            score = pr[:, 1] if pr.shape[1] > 1 else pr[:, 0]
        else:
            score = None
        probs[name] = np.asarray(score).ravel() if score is not None else None
        out["per_model"][name] = compute_binary_classification_metrics(
            y_true,
            preds[name],
            probs[name],
        )

    pairs = mcnemar_pairs or []
    if len(pairs) == 0 and len(fitted_models) >= 2:
        names = list(fitted_models.keys())
        pairs = [(names[0], names[1])]
    for a, b in pairs:
        if a in preds and b in preds:
            out["mcnemar"][f"{a}_vs_{b}"] = mcnemar_test(y_true, preds[a], preds[b])

    return out


def stratified_train_val_test_indices(
    y: np.ndarray,
    *,
    test_size: float = 0.15,
    val_size: float = 0.15,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    70/15/15-style stratified split indices (train / val / test).

    Fractions apply to the second split of remaining data for val.
    """
    from sklearn.model_selection import train_test_split

    y = np.asarray(y).ravel()
    idx = np.arange(len(y))
    train_val, test_idx, _, _ = train_test_split(
        idx, y, test_size=test_size, stratify=y, random_state=random_state
    )
    y_tv = y[train_val]
    rel_val = val_size / (1.0 - test_size)
    train_idx, val_idx, _, _ = train_test_split(
        train_val, y_tv, test_size=rel_val, stratify=y_tv, random_state=random_state
    )
    return train_idx, val_idx, test_idx
