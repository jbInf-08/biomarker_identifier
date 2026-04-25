"""Tests for evaluation_utils (McNemar, imbalance metrics)."""

import numpy as np
import pytest

from app.ml_models.evaluation_utils import (
    bootstrap_paired_auc_delta,
    compute_binary_classification_metrics,
    holdout_multimodel_report,
    mcnemar_test,
)


def test_mcnemar_perfect_agreement():
    y = np.array([0, 1, 0, 1])
    a = np.array([0, 1, 0, 1])
    b = np.array([0, 1, 0, 1])
    r = mcnemar_test(y, a, b)
    assert r["pvalue"] == 1.0
    assert (
        r["table"]["n01_a_wrong_b_right"] + r["table"]["n10_a_right_b_wrong"] == 0
    )


def test_compute_metrics_imbalance_warning():
    y_true = np.array([0] * 100 + [1] * 2)
    y_pred = np.zeros(102, dtype=int)
    m = compute_binary_classification_metrics(
        y_true, y_pred, np.linspace(0.01, 0.1, 102)
    )
    assert m["accuracy_may_be_misleading"] is True


def test_holdout_multimodel_report():
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    import pandas as pd

    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(80, 6)))
    y = pd.Series((rng.random(80) > 0.6).astype(int))
    lr = LogisticRegression(max_iter=500, random_state=0).fit(X, y)
    rf = RandomForestClassifier(n_estimators=20, random_state=0).fit(X, y)
    rep = holdout_multimodel_report(
        {"lr": lr, "rf": rf},
        X,
        y,
        mcnemar_pairs=[("lr", "rf")],
    )
    assert "lr" in rep["per_model"]
    assert "mcnemar" in rep


def test_bootstrap_paired_auc_delta_runs():
    y = np.array([0, 0, 1, 1, 0, 1, 0, 1])
    s1 = np.linspace(0.1, 0.9, 8)
    s2 = s1 + 0.05
    out = bootstrap_paired_auc_delta(y, s1, s2, n_bootstrap=50, random_state=1)
    assert "median_delta" in out
