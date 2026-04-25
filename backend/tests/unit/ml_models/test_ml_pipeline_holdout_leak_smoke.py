"""Fast unit tests for graph adjacency resolution (CI-safe). Full E2E: conference ``scripts/paper/robustness_compare.py``."""

import numpy as np
import pandas as pd

from app.ml_models.ml_pipeline import MLPipeline


def test_resolve_graph_adjacency_subsets_from_full_matrix():
    X = pd.DataFrame(
        np.random.default_rng(0).normal(size=(12, 5)),
        columns=list("ABCDE"),
    )
    X_sel = X[["B", "D", "E"]]
    A_full = np.ones((5, 5)) * 0.1
    np.fill_diagonal(A_full, 1.0)
    sub = MLPipeline._resolve_graph_adjacency(X, X_sel, None, A_full)
    assert sub is not None
    assert sub.shape == (3, 3)


def test_resolve_graph_adjacency_passes_through_selected_sized():
    X = pd.DataFrame(np.random.randn(8, 4), columns=list("WXYZ"))
    X_sel = X
    A = np.eye(4)
    sub = MLPipeline._resolve_graph_adjacency(X, X_sel, A, None)
    assert sub.shape == (4, 4)


def test_run_stratified_holdout_evaluation_smoke_tiny_synthetic():
    """Fast regression guard: full holdout path without heavy bootstrap/CV."""
    rng = np.random.default_rng(42)
    n_samples, n_genes = 36, 12
    X = pd.DataFrame(
        rng.normal(size=(n_samples, n_genes)),
        columns=[f"G{i}" for i in range(n_genes)],
    )
    y = pd.Series(rng.integers(0, 2, size=n_samples), index=X.index)

    pipe = MLPipeline(random_state=0, n_jobs=1)
    out = pipe.run_stratified_holdout_evaluation(
        X,
        y,
        test_size=0.25,
        n_features=6,
        n_bootstrap=2,
        consensus_methods=["random_forest", "f_test"],
        optimize_hyperparameters=False,
        cv_folds=2,
        train_shallow_gcn=False,
    )
    assert "evaluation" in out
    assert "per_model" in out["evaluation"]
    assert len(out["evaluation"]["per_model"]) >= 1
