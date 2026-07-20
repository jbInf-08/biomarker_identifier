"""
Self-contained unit tests for ``app.ml_models.ml_pipeline``.

Every heavy collaborator (feature selection, model training, nested CV,
permutation testing, SHAP, GCNs) is replaced by a deterministic stub so the
whole module runs in a couple of seconds while still exercising every branch,
error handler and early return of :class:`MLPipeline`.

These tests use no fixtures from ``tests/conftest.py`` and therefore run with
``--noconftest``.
"""

import numpy as np
import pandas as pd
import pytest

from app.ml_models import ml_pipeline as mlp_mod
from app.ml_models.ml_pipeline import MLPipeline

RANDOM_STATE = 0


# ---------------------------------------------------------------------------
# Deterministic test data
# ---------------------------------------------------------------------------


def make_xy(n_samples: int = 40, n_features: int = 8, seed: int = 0):
    """Small, balanced, fully deterministic binary classification frame."""
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(
        rng.normal(size=(n_samples, n_features)),
        columns=[f"G{i}" for i in range(n_features)],
    )
    y = pd.Series(np.tile([0, 1], n_samples // 2), index=X.index, name="label")
    return X, y


# ---------------------------------------------------------------------------
# Stub collaborators
# ---------------------------------------------------------------------------


class StubModel:
    """Minimal estimator: alternating predictions, valid 2-column proba."""

    def __init__(self, name="stub"):
        self.name = name

    def fit(self, X, y):  # pragma: no cover - trivial
        return self

    def predict(self, X):
        return np.tile([0, 1], int(np.ceil(len(X) / 2)))[: len(X)]

    def predict_proba(self, X):
        p = np.linspace(0.1, 0.9, len(X))
        return np.column_stack([1.0 - p, p])


class StubModelNoProba:
    """Estimator without ``predict_proba`` (exercises the score=None path)."""

    def predict(self, X):
        return np.zeros(len(X), dtype=int)


class StubConsensusSelector:
    """Stands in for ``ConsensusFeatureSelector``."""

    def __init__(self, random_state=42, n_jobs=-1, keep=3):
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.keep = keep
        self.consensus_results_ = {}
        self.fit_calls = []

    def fit(self, X, y, n_bootstrap=100, n_features=50, consensus_methods=None):
        self.fit_calls.append(
            {
                "n_rows": len(X),
                "n_bootstrap": n_bootstrap,
                "n_features": n_features,
                "consensus_methods": consensus_methods,
            }
        )
        self.cols_ = list(X.columns)[: self.keep]
        self.consensus_results_ = {
            "features": list(self.cols_),
            "mean_scores": {c: 0.5 for c in self.cols_},
            "selection_frequency": {c: 0.9 for c in self.cols_},
        }
        return self

    def transform(self, X):
        return X[self.cols_]

    def get_consensus_summary(self):
        return pd.DataFrame(
            {"feature": self.cols_, "mean_score": [0.5] * len(self.cols_)}
        )


class StubStandardSelector:
    """Stands in for ``FeatureSelector``."""

    def __init__(self, keep=3):
        self.keep = keep
        self.selected_features_ = {}

    def fit(self, X, y, n_features=50):
        self.cols_ = list(X.columns)[: self.keep]
        self.selected_features_ = {
            "features": list(self.cols_),
            "consensus_scores": {c: 0.4 for c in self.cols_},
            "stability_scores": {c: 0.7 for c in self.cols_},
        }
        return self

    def transform(self, X):
        return X[self.cols_]

    def get_feature_importance(self):
        return pd.DataFrame(
            {"feature": self.cols_, "importance": [1.0] * len(self.cols_)}
        )


class StubTrainer:
    """Stands in for ``ModelTrainer``; records constructor kwargs."""

    instances = []

    def __init__(self, random_state=42, n_jobs=-1, mlp_use_focal_loss=False):
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.mlp_use_focal_loss = mlp_use_focal_loss
        self.trained_models_ = {}
        self.train_calls = []
        StubTrainer.instances.append(self)

    def train_models(self, X, y, optimize_hyperparameters=True, cv_folds=5):
        self.train_calls.append(
            {
                "optimize_hyperparameters": optimize_hyperparameters,
                "cv_folds": cv_folds,
                "shape": X.shape,
            }
        )
        model_a = StubModel("rf")
        model_b = StubModel("lr")
        self.trained_models_ = {"random_forest": model_a, "logistic": model_b}
        return {
            "random_forest": {"best_score": 0.88, "model": model_a},
            "logistic": {"best_score": 0.71, "model": model_b},
        }

    def get_best_model(self):
        return "random_forest", self.trained_models_["random_forest"]


class StubEvaluator:
    def __init__(self, best_name="random_forest", roc_auc=0.85):
        self.best_name = best_name
        self.roc_auc = roc_auc

    def evaluate_models(self, models, X, y, cv_folds=5):
        return {
            self.best_name: {
                "cv_results": {
                    "accuracy": {"mean": 0.8},
                    "precision_macro": {"mean": 0.79},
                    "recall_macro": {"mean": 0.78},
                    "f1_macro": {"mean": 0.77},
                    "roc_auc": {"mean": self.roc_auc},
                    "average_precision": {"mean": 0.76},
                    "balanced_accuracy": {"mean": 0.75},
                    "matthews_corrcoef": {"mean": 0.5},
                }
            }
        }


class StubCrossValidator:
    def nested_cross_validation(self, X, y, cv_folds=5):
        return {"outer_scores": [0.8, 0.82], "cv_folds": cv_folds}


class StubPermutationTester:
    def __init__(self, significant=True, p_value=0.001):
        self.significant = significant
        self.p_value = p_value

    def model_performance_permutation_test(self, model, X, y, n_permutations=1000):
        return {
            "p_value": self.p_value,
            "significant": self.significant,
            "effect_size": 1.25,
            "n_permutations": n_permutations,
        }


class StubShapExplainer:
    def __init__(self, fail_fit=False, fail_interactions=False):
        self.fail_fit = fail_fit
        self.fail_interactions = fail_interactions

    def fit_explainer(self, model, X, sample_size=None):
        if self.fail_fit:
            raise RuntimeError("explainer unavailable")
        self.sample_size = sample_size

    def explain_global(self, X, max_display=20):
        return {
            "top_features": [{"feature": "G0", "importance": 0.9}],
            "feature_importance": [
                {"feature": "G0", "importance": 0.9},
                {"feature": "G1", "importance": 0.4},
            ],
            "summary_stats": {"total_features": X.shape[1]},
        }

    def explain_local(self, X, sample_indices=None):
        return {"n_samples": len(list(sample_indices))}

    def explain_interactions(self, X, max_display=20):
        if self.fail_interactions:
            raise RuntimeError("interactions unsupported")
        return {"pairs": []}


# ---------------------------------------------------------------------------
# Pipeline wiring helper
# ---------------------------------------------------------------------------


def build_pipeline(
    monkeypatch,
    *,
    keep=3,
    shap_fail_fit=False,
    shap_fail_interactions=False,
    permutation_significant=True,
    roc_auc=0.85,
):
    """MLPipeline with every collaborator replaced by a stub."""
    StubTrainer.instances = []
    monkeypatch.setattr(mlp_mod, "ModelTrainer", StubTrainer)
    monkeypatch.setattr(
        mlp_mod,
        "ConsensusFeatureSelector",
        lambda random_state=42, n_jobs=-1: StubConsensusSelector(
            random_state=random_state, n_jobs=n_jobs, keep=keep
        ),
    )

    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.consensus_selector = StubConsensusSelector(keep=keep)
    pipe.feature_selector = StubStandardSelector(keep=keep)
    pipe.model_evaluator = StubEvaluator(roc_auc=roc_auc)
    pipe.cross_validator = StubCrossValidator()
    pipe.permutation_tester = StubPermutationTester(significant=permutation_significant)
    pipe.shap_explainer = StubShapExplainer(
        fail_fit=shap_fail_fit, fail_interactions=shap_fail_interactions
    )
    return pipe


# ===========================================================================
# __init__
# ===========================================================================


def test_init_sets_components_and_empty_state():
    pipe = MLPipeline(random_state=7, n_jobs=2)
    assert pipe.random_state == 7
    assert pipe.n_jobs == 2
    assert pipe.pipeline_results_ == {}
    assert pipe.selected_features_ is None
    assert pipe.trained_models_ == {}
    assert pipe.best_model_ is None
    assert pipe.explanations_ == {}
    assert pipe.model_selection_log_ == {}
    for attr in (
        "feature_selector",
        "consensus_selector",
        "model_trainer",
        "model_evaluator",
        "cross_validator",
        "permutation_tester",
        "shap_explainer",
    ):
        assert getattr(pipe, attr) is not None


def test_init_defaults():
    pipe = MLPipeline()
    assert pipe.random_state == 42
    assert pipe.n_jobs == -1


# ===========================================================================
# _resolve_graph_adjacency
# ===========================================================================


def test_resolve_adjacency_returns_none_when_nothing_supplied():
    X, _ = make_xy(10, 4)
    assert MLPipeline._resolve_graph_adjacency(X, X, None, None) is None


def test_resolve_adjacency_passthrough_when_only_post_selection_given():
    X, _ = make_xy(10, 4)
    A = np.eye(4)
    out = MLPipeline._resolve_graph_adjacency(X, X, A, None)
    assert out is A


def test_resolve_adjacency_subsets_pre_selection_matrix():
    X, _ = make_xy(10, 4)
    A_full = np.arange(16, dtype=float).reshape(4, 4)
    X_sel = X[["G1", "G3"]]
    out = MLPipeline._resolve_graph_adjacency(X, X_sel, None, A_full)
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(A_full[1, 1])
    assert out[1, 1] == pytest.approx(A_full[3, 3])
    assert out[0, 1] == pytest.approx(A_full[1, 3])


def test_resolve_adjacency_pre_selection_wrong_shape_raises():
    X, _ = make_xy(10, 4)
    bad = np.eye(3)
    with pytest.raises(ValueError, match="n_genes, n_genes"):
        MLPipeline._resolve_graph_adjacency(X, X, None, bad)


def test_resolve_adjacency_pre_selection_takes_priority_over_post():
    X, _ = make_xy(10, 4)
    A_full = np.eye(4) * 2.0
    A_post = np.zeros((2, 2))
    X_sel = X[["G0", "G2"]]
    out = MLPipeline._resolve_graph_adjacency(X, X_sel, A_post, A_full)
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(2.0)


# ===========================================================================
# run_complete_pipeline - happy paths
# ===========================================================================


def test_run_complete_pipeline_consensus_happy_path(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)

    results = pipe.run_complete_pipeline(
        X, y, n_features=3, n_bootstrap=5, cv_folds=2, n_permutations=10
    )

    assert "error" not in results
    assert results["feature_selection"]["method"] == "consensus"
    assert results["feature_selection"]["n_bootstrap"] == 5
    assert results["feature_selection"]["selected_features"] == ["G0", "G1", "G2"]
    assert isinstance(results["feature_selection"]["consensus_summary"], list)
    assert results["model_selection"]["criteria"] == "best cross-validation score"
    assert set(results["model_selection"]["candidate_models"]) == {
        "random_forest",
        "logistic",
    }
    assert results["best_model"]["name"] == "random_forest"
    assert results["best_model"]["type"] == "StubModel"
    assert results["best_model"]["performance"] == pytest.approx(0.88)
    assert results["cross_validation"]["cv_folds"] == 2
    assert results["permutation_testing"]["n_permutations"] == 10
    assert results["shap_explanations"]["global"]["top_features"]
    assert results["pipeline_summary"]["pipeline_status"] == "completed"
    assert "total_pipeline_seconds" in results["timing"]
    assert "pipeline_completed" in results["timestamps"]
    # results are cached on the instance
    assert pipe.pipeline_results_ is results
    assert pipe.selected_features_ == ["G0", "G1", "G2"]
    assert pipe.best_model_ is not None


def test_run_complete_pipeline_standard_selection_path(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        use_consensus_selection=False,
        cv_folds=2,
        n_permutations=5,
        run_shap_analysis=False,
        run_nested_cross_validation=False,
    )

    assert "error" not in results
    assert results["feature_selection"]["method"] == "standard"
    assert results["feature_selection"]["feature_importance"][0]["feature"] == "G0"
    assert results["cross_validation"] == {"skipped": True}
    assert results["shap_explanations"] == {"skipped": True}
    assert "cross_validation_seconds" not in results["timing"]


def test_run_complete_pipeline_config_is_echoed(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=0,
        run_shap_analysis=False,
        run_nested_cross_validation=False,
        consensus_methods=["f_test"],
        mlp_use_focal_loss=True,
        optimize_hyperparameters=False,
    )

    cfg = results["pipeline_config"]
    assert cfg["n_features"] == 3
    assert cfg["consensus_methods"] == ["f_test"]
    assert cfg["mlp_use_focal_loss"] is True
    assert cfg["optimize_hyperparameters"] is False
    assert cfg["graph_adjacency_pre_selection"] is False
    assert cfg["leak_safe_mode"] is False
    assert cfg["random_state"] == RANDOM_STATE
    # focal-loss flag is forwarded to the freshly built trainer
    assert StubTrainer.instances[-1].mlp_use_focal_loss is True
    # optimize_hyperparameters is forwarded to train_models
    assert StubTrainer.instances[-1].train_calls[0]["optimize_hyperparameters"] is False


def test_run_complete_pipeline_skips_permutation_when_zero(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)

    results = pipe.run_complete_pipeline(
        X, y, n_features=3, cv_folds=2, n_permutations=0, run_shap_analysis=False
    )

    assert results["permutation_testing"] == {"skipped": True}
    assert results["pipeline_summary"]["statistical_significance"] == {"skipped": True}


def test_run_complete_pipeline_skips_permutation_when_none(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)

    results = pipe.run_complete_pipeline(
        X, y, n_features=3, cv_folds=2, n_permutations=None, run_shap_analysis=False
    )

    assert results["permutation_testing"] == {"skipped": True}


# ===========================================================================
# run_complete_pipeline - SHAP branches
# ===========================================================================


def test_run_complete_pipeline_shap_interaction_failure_is_captured(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch, shap_fail_interactions=True)

    results = pipe.run_complete_pipeline(
        X, y, n_features=3, cv_folds=2, n_permutations=5
    )

    interactions = results["shap_explanations"]["interactions"]
    assert "Interactions not supported" in interactions["error"]
    # the rest of the SHAP block still succeeded
    assert (
        results["shap_explanations"]["global"]["summary_stats"]["total_features"] == 3
    )
    assert results["pipeline_summary"]["feature_insights"]["top_feature"] == "G0"


def test_run_complete_pipeline_shap_failure_is_captured(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch, shap_fail_fit=True)

    results = pipe.run_complete_pipeline(
        X, y, n_features=3, cv_folds=2, n_permutations=5
    )

    assert results["shap_explanations"] == {"error": "explainer unavailable"}
    # pipeline still completes
    assert results["pipeline_summary"]["pipeline_status"] == "completed"
    assert results["pipeline_summary"]["feature_insights"] == {}


# ===========================================================================
# run_complete_pipeline - graph augmentation branches
# ===========================================================================


def test_run_complete_pipeline_applies_graph_augmentation(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)
    calls = {}

    def fake_augment(X_sel, cols, adj, mode=None):
        calls["mode"] = mode
        calls["cols"] = list(cols)
        calls["adj_shape"] = adj.shape
        return X_sel

    monkeypatch.setattr(mlp_mod, "augment_expression_with_graph", fake_augment)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=0,
        run_shap_analysis=False,
        run_nested_cross_validation=False,
        graph_adjacency=np.eye(3),
        graph_augment_mode="concat",
    )

    assert "error" not in results
    assert calls["mode"] == "concat"
    assert calls["cols"] == ["G0", "G1", "G2"]
    assert calls["adj_shape"] == (3, 3)


def test_run_complete_pipeline_uses_pre_selection_adjacency(monkeypatch):
    X, y = make_xy(n_features=8)
    pipe = build_pipeline(monkeypatch)
    seen = {}

    def fake_augment(X_sel, cols, adj, mode=None):
        seen["adj_shape"] = adj.shape
        return X_sel

    monkeypatch.setattr(mlp_mod, "augment_expression_with_graph", fake_augment)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=0,
        run_shap_analysis=False,
        run_nested_cross_validation=False,
        graph_adjacency_pre_selection=np.eye(8),
        graph_augment_mode="smooth_only",
    )

    assert "error" not in results
    assert seen["adj_shape"] == (3, 3)
    assert results["pipeline_config"]["graph_adjacency_pre_selection"] is True


def test_run_complete_pipeline_adjacency_ignored_without_mode(monkeypatch):
    """Adjacency present but ``graph_augment_mode`` falsy -> augmentation skipped."""
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)

    def boom(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("augmentation should not run")

    monkeypatch.setattr(mlp_mod, "augment_expression_with_graph", boom)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=0,
        run_shap_analysis=False,
        run_nested_cross_validation=False,
        graph_adjacency=np.eye(3),
        graph_augment_mode=None,
    )
    assert "error" not in results


def test_run_complete_pipeline_adjacency_shape_mismatch_is_caught(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=0,
        run_shap_analysis=False,
        graph_adjacency=np.eye(5),  # selected has 3 columns
        graph_augment_mode="concat",
    )

    assert "Resolved graph adjacency must match selected feature columns" in (
        results["error"]
    )
    assert "pipeline_failed" in results["timestamps"]
    assert "pipeline_summary" not in results


# ===========================================================================
# run_complete_pipeline - failure handling
# ===========================================================================


def test_run_complete_pipeline_wraps_unexpected_exception(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)

    def boom(*args, **kwargs):
        raise RuntimeError("selector exploded")

    pipe.consensus_selector.fit = boom

    results = pipe.run_complete_pipeline(
        X, y, n_features=3, cv_folds=2, n_permutations=0, run_shap_analysis=False
    )

    assert results["error"] == "selector exploded"
    assert "pipeline_failed" in results["timestamps"]


# ===========================================================================
# leak-safe pipeline
# ===========================================================================


def test_leak_safe_pipeline_consensus_happy_path(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=5,
        leak_safe_mode=True,
        leak_safe_test_size=0.25,
    )

    assert "error" not in results
    assert results["leak_safe_mode"] is True
    assert results["leak_safe_split"]["n_train"] == 30
    assert results["leak_safe_split"]["n_test"] == 10
    assert results["leak_safe_split"]["test_size_fraction"] == 0.25
    assert results["feature_selection"]["scope"] == "train_only"
    assert results["feature_selection"]["method"] == "consensus"
    assert "per_model" in results["holdout_test_evaluation"]
    # best model appears in the holdout report -> copied into the summary
    assert "holdout_test_metrics" in results["pipeline_summary"]
    assert results["pipeline_summary"]["pipeline_status"] == "completed"
    assert "total_pipeline_seconds" in results["timing"]
    assert pipe.pipeline_results_ is results
    # consensus fitted only on the training rows
    assert pipe.consensus_selector.fit_calls[0]["n_rows"] == 30


def test_leak_safe_pipeline_standard_selection_and_no_shap(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=5,
        use_consensus_selection=False,
        run_shap_analysis=False,
        leak_safe_mode=True,
    )

    assert "error" not in results
    assert results["feature_selection"]["method"] == "standard"
    assert results["feature_selection"]["scope"] == "train_only"
    assert "consensus_summary" not in results["feature_selection"]
    assert results["shap_explanations"] == {"skipped": True}


def test_leak_safe_pipeline_shap_interaction_failure(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch, shap_fail_interactions=True)

    results = pipe.run_complete_pipeline(
        X, y, n_features=3, cv_folds=2, n_permutations=5, leak_safe_mode=True
    )

    assert results["shap_explanations"]["interactions"] == {
        "error": "interactions unsupported"
    }
    assert "shap_analysis_seconds" in results["timing"]


def test_leak_safe_pipeline_shap_failure(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch, shap_fail_fit=True)

    results = pipe.run_complete_pipeline(
        X, y, n_features=3, cv_folds=2, n_permutations=5, leak_safe_mode=True
    )

    assert results["shap_explanations"] == {"error": "explainer unavailable"}


def test_leak_safe_pipeline_graph_augmentation(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)
    calls = []

    def fake_augment(frame, cols, adj, mode=None):
        calls.append((frame.shape, mode))
        return frame

    monkeypatch.setattr(mlp_mod, "augment_expression_with_graph", fake_augment)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=5,
        run_shap_analysis=False,
        leak_safe_mode=True,
        graph_adjacency=np.eye(3),
        graph_augment_mode="concat",
    )

    assert "error" not in results
    # both train and test matrices are augmented with the same adjacency
    assert len(calls) == 2
    assert calls[0][1] == "concat" and calls[1][1] == "concat"


def test_leak_safe_pipeline_adjacency_mismatch_is_caught(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=5,
        run_shap_analysis=False,
        leak_safe_mode=True,
        graph_adjacency=np.eye(6),
        graph_augment_mode="concat",
    )

    assert (
        results["error"] == "Resolved graph adjacency must match selected train columns"
    )
    assert "pipeline_failed" in results["timestamps"]


def test_leak_safe_pipeline_wraps_unexpected_exception(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)
    pipe.cross_validator.nested_cross_validation = lambda *a, **k: (
        _ for _ in ()
    ).throw(RuntimeError("cv exploded"))

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=5,
        run_shap_analysis=False,
        leak_safe_mode=True,
    )

    assert results["error"] == "cv exploded"


def test_leak_safe_pipeline_skips_holdout_metrics_when_best_missing(monkeypatch):
    """Best model absent from the fitted dict -> no ``holdout_test_metrics`` key."""
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)

    original = StubTrainer.train_models

    def train_without_best(self, X_, y_, optimize_hyperparameters=True, cv_folds=5):
        out = original(self, X_, y_, optimize_hyperparameters, cv_folds)
        out["random_forest"]["model"] = None  # filtered out of ``fitted``
        return out

    monkeypatch.setattr(StubTrainer, "train_models", train_without_best)

    results = pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=5,
        run_shap_analysis=False,
        leak_safe_mode=True,
    )

    assert "error" not in results
    assert "random_forest" not in results["holdout_test_evaluation"]["per_model"]
    assert "logistic" in results["holdout_test_evaluation"]["per_model"]
    assert "holdout_test_metrics" not in results["pipeline_summary"]


# ===========================================================================
# run_stratified_holdout_evaluation
# ===========================================================================


def test_stratified_holdout_basic(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)

    out = pipe.run_stratified_holdout_evaluation(
        X, y, test_size=0.25, n_features=3, n_bootstrap=2, cv_folds=2
    )

    assert out["n_train"] == 30
    assert out["n_test"] == 10
    assert out["holdout_config"]["test_size"] == 0.25
    assert out["holdout_config"]["train_shallow_gcn"] is False
    assert out["holdout_config"]["train_deep_gcn"] is False
    assert set(out["evaluation"]["per_model"]) == {"random_forest", "logistic"}
    assert "training_summary" in out
    # McNemar is auto-added for >= 2 models
    assert out["evaluation"]["mcnemar"]


def test_stratified_holdout_with_mcnemar_pairs_and_augmentation(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)
    seen = []

    def fake_augment(frame, cols, adj, mode=None):
        seen.append(mode)
        return frame

    monkeypatch.setattr(mlp_mod, "augment_expression_with_graph", fake_augment)

    out = pipe.run_stratified_holdout_evaluation(
        X,
        y,
        test_size=0.25,
        n_features=3,
        n_bootstrap=2,
        cv_folds=2,
        graph_adjacency=np.eye(3),
        graph_augment_mode="concat",
        mcnemar_pairs=[("random_forest", "logistic")],
        optimize_hyperparameters=True,
    )

    assert seen == ["concat", "concat"]
    assert "random_forest_vs_logistic" in out["evaluation"]["mcnemar"]
    assert out["holdout_config"]["graph_augment_mode"] == "concat"


def test_stratified_holdout_adjacency_mismatch_raises(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)

    with pytest.raises(ValueError, match="must match selected features"):
        pipe.run_stratified_holdout_evaluation(
            X,
            y,
            test_size=0.25,
            n_features=3,
            n_bootstrap=2,
            cv_folds=2,
            graph_adjacency=np.eye(7),
            graph_augment_mode="concat",
        )


class _StubGCN:
    def __init__(self, adjacency=None, random_state=0):
        self.adjacency = adjacency
        self.random_state = random_state

    def fit(self, X, y):
        self.n_features_ = X.shape[1]
        return self

    def predict(self, X):
        return np.tile([1, 0], int(np.ceil(len(X) / 2)))[: len(X)]

    def predict_proba(self, X):
        p = np.linspace(0.2, 0.8, len(X))
        return np.column_stack([1.0 - p, p])


def test_stratified_holdout_shallow_gcn_branch(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)
    from app.ml_models import graph_augmented

    monkeypatch.setattr(graph_augmented, "ShallowGeneGCNClassifier", _StubGCN)

    out = pipe.run_stratified_holdout_evaluation(
        X,
        y,
        test_size=0.25,
        n_features=3,
        n_bootstrap=2,
        cv_folds=2,
        graph_adjacency=np.eye(3),
        train_shallow_gcn=True,
    )

    assert "shallow_gcn" in out["evaluation"]["per_model"]
    assert out["holdout_config"]["train_shallow_gcn"] is True


def test_stratified_holdout_deep_gcn_branch(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)
    from app.ml_models import graph_augmented

    monkeypatch.setattr(graph_augmented, "DeepGeneGCNClassifier", _StubGCN)

    out = pipe.run_stratified_holdout_evaluation(
        X,
        y,
        test_size=0.25,
        n_features=3,
        n_bootstrap=2,
        cv_folds=2,
        graph_adjacency=np.eye(3),
        train_deep_gcn=True,
        train_shallow_gcn=True,  # deep takes precedence
    )

    assert "deep_gcn" in out["evaluation"]["per_model"]
    assert "shallow_gcn" not in out["evaluation"]["per_model"]


def test_stratified_holdout_deep_gcn_adjacency_mismatch_raises(monkeypatch):
    """Adjacency matches the augmented matrix but not the expression matrix."""
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)
    from app.ml_models import graph_augmented

    monkeypatch.setattr(graph_augmented, "DeepGeneGCNClassifier", _StubGCN)

    # Return an adjacency that passes the augmentation check but not the GCN one
    # by making the selector emit fewer columns than the adjacency after augment.
    def fake_augment(frame, cols, adj, mode=None):
        return frame

    monkeypatch.setattr(mlp_mod, "augment_expression_with_graph", fake_augment)

    with pytest.raises(ValueError, match="GCN adjacency must match selected genes"):
        pipe.run_stratified_holdout_evaluation(
            X,
            y,
            test_size=0.25,
            n_features=3,
            n_bootstrap=2,
            cv_folds=2,
            graph_adjacency=np.eye(4),
            train_deep_gcn=True,
        )


def test_stratified_holdout_shallow_gcn_adjacency_mismatch_raises(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)
    from app.ml_models import graph_augmented

    monkeypatch.setattr(graph_augmented, "ShallowGeneGCNClassifier", _StubGCN)
    monkeypatch.setattr(
        mlp_mod, "augment_expression_with_graph", lambda f, c, a, mode=None: f
    )

    with pytest.raises(ValueError, match="GCN adjacency must match selected genes"):
        pipe.run_stratified_holdout_evaluation(
            X,
            y,
            test_size=0.25,
            n_features=3,
            n_bootstrap=2,
            cv_folds=2,
            graph_adjacency=np.eye(4),
            train_shallow_gcn=True,
        )


def test_stratified_holdout_gcn_flag_ignored_without_adjacency(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)

    out = pipe.run_stratified_holdout_evaluation(
        X,
        y,
        test_size=0.25,
        n_features=3,
        n_bootstrap=2,
        cv_folds=2,
        train_shallow_gcn=True,
    )

    assert "shallow_gcn" not in out["evaluation"]["per_model"]


def test_stratified_holdout_drops_models_without_estimator(monkeypatch):
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)

    original = StubTrainer.train_models

    def train_partial(self, X_, y_, optimize_hyperparameters=True, cv_folds=5):
        out = original(self, X_, y_, optimize_hyperparameters, cv_folds)
        out["logistic"]["model"] = None
        return out

    monkeypatch.setattr(StubTrainer, "train_models", train_partial)

    out = pipe.run_stratified_holdout_evaluation(
        X, y, test_size=0.25, n_features=3, n_bootstrap=2, cv_folds=2
    )

    assert set(out["evaluation"]["per_model"]) == {"random_forest"}
    assert out["evaluation"]["mcnemar"] == {}


def test_holdout_report_handles_model_without_predict_proba(monkeypatch):
    """Guards the ``score is None`` branch reached through the holdout report."""
    X, y = make_xy(n_samples=40)
    pipe = build_pipeline(monkeypatch)

    original = StubTrainer.train_models

    def train_no_proba(self, X_, y_, optimize_hyperparameters=True, cv_folds=5):
        out = original(self, X_, y_, optimize_hyperparameters, cv_folds)
        out["logistic"]["model"] = StubModelNoProba()
        self.trained_models_["logistic"] = out["logistic"]["model"]
        return out

    monkeypatch.setattr(StubTrainer, "train_models", train_no_proba)

    out = pipe.run_stratified_holdout_evaluation(
        X, y, test_size=0.25, n_features=3, n_bootstrap=2, cv_folds=2
    )

    assert "logistic" in out["evaluation"]["per_model"]


# ===========================================================================
# _generate_pipeline_summary
# ===========================================================================


def test_generate_summary_minimal_results():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["A", "B"]
    pipe.trained_models_ = {"m": object()}

    summary = pipe._generate_pipeline_summary(
        {"best_model": {"name": "m", "type": "X", "performance": 0.5}}
    )

    assert summary["pipeline_status"] == "completed"
    assert summary["total_features_selected"] == 2
    assert summary["models_trained"] == 1
    assert summary["performance_metrics"] == {}
    assert summary["statistical_significance"] == {}
    assert summary["feature_insights"] == {}


def test_generate_summary_best_model_absent_from_evaluation():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["A"]

    summary = pipe._generate_pipeline_summary(
        {
            "best_model": {"name": "missing", "type": "X", "performance": 0.5},
            "model_evaluation": {"other": {"cv_results": {}}},
        }
    )

    assert summary["performance_metrics"] == {}


def test_generate_summary_uses_metric_defaults_for_missing_keys():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["A"]

    summary = pipe._generate_pipeline_summary(
        {
            "best_model": {"name": "m", "type": "X", "performance": 0.5},
            "model_evaluation": {"m": {"cv_results": {"accuracy": {"mean": 0.9}}}},
        }
    )

    assert summary["performance_metrics"]["accuracy"] == pytest.approx(0.9)
    assert summary["performance_metrics"]["roc_auc"] == 0
    assert summary["performance_metrics"]["matthews_corrcoef"] == 0


def test_generate_summary_significance_and_insights():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["A"]

    summary = pipe._generate_pipeline_summary(
        {
            "best_model": {"name": "m", "type": "X", "performance": 0.5},
            "permutation_testing": {
                "significant": True,
                "p_value": 0.002,
                "effect_size": 2.0,
            },
            "shap_explanations": {
                "global": {
                    "top_features": [{"feature": "A", "importance": 0.3}],
                    "summary_stats": {"total_features": 4},
                }
            },
        }
    )

    assert summary["statistical_significance"]["model_significant"] is True
    assert summary["statistical_significance"]["p_value"] == pytest.approx(0.002)
    assert summary["feature_insights"]["top_feature"] == "A"
    assert summary["feature_insights"]["total_features_analyzed"] == 4


def test_generate_summary_empty_shap_top_features():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["A"]

    summary = pipe._generate_pipeline_summary(
        {
            "best_model": {"name": "m", "type": "X", "performance": 0.5},
            "shap_explanations": {"global": {"top_features": []}},
        }
    )

    assert summary["feature_insights"] == {}


def test_generate_summary_shap_error_block_is_ignored():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["A"]

    summary = pipe._generate_pipeline_summary(
        {
            "best_model": {"name": "m", "type": "X", "performance": 0.5},
            "shap_explanations": {"error": "boom"},
        }
    )

    assert summary["feature_insights"] == {}


# ===========================================================================
# get_feature_importance_summary
# ===========================================================================


def test_feature_importance_summary_requires_run():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    with pytest.raises(ValueError, match="Pipeline not run"):
        pipe.get_feature_importance_summary()


def test_feature_importance_summary_unfitted_consensus_raises_attribute_error():
    """Known rough edge: ``ConsensusFeatureSelector`` has no ``consensus_results_``
    until ``fit`` runs, so the summary explodes on an un-fitted selector."""
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["G0"]
    with pytest.raises(AttributeError):
        pipe.get_feature_importance_summary()


def test_feature_importance_summary_all_sources():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["G0", "G1"]
    pipe.feature_selector = StubStandardSelector()
    pipe.feature_selector.selected_features_ = {
        "features": ["G0"],
        "consensus_scores": {"G0": 0.4},
        "stability_scores": {"G0": 0.7},
    }
    pipe.consensus_selector = StubConsensusSelector()
    pipe.consensus_selector.consensus_results_ = {
        "features": ["G0"],
        "mean_scores": {"G0": 0.55},
        "selection_frequency": {"G0": 0.95},
    }
    pipe.pipeline_results_ = {
        "shap_explanations": {
            "global": {
                "feature_importance": [
                    {"feature": "G1", "importance": 0.11},
                    {"feature": "G0", "importance": 0.22},
                ]
            }
        }
    }

    df = pipe.get_feature_importance_summary()

    assert list(df["feature"]) == ["G0", "G1"]
    row0 = df.set_index("feature").loc["G0"]
    assert row0["selection_consensus_score"] == pytest.approx(0.4)
    assert row0["selection_stability_score"] == pytest.approx(0.7)
    assert row0["consensus_mean_score"] == pytest.approx(0.55)
    assert row0["consensus_frequency"] == pytest.approx(0.95)
    assert row0["shap_importance"] == pytest.approx(0.22)
    # G1 is absent from every selector map -> only the SHAP value is filled in
    row1 = df.set_index("feature").loc["G1"]
    assert row1["shap_importance"] == pytest.approx(0.11)
    assert pd.isna(row1["consensus_mean_score"])


def test_feature_importance_summary_without_shap_section():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["G0"]
    pipe.feature_selector = StubStandardSelector()
    pipe.consensus_selector = StubConsensusSelector()
    pipe.pipeline_results_ = {"shap_explanations": {"global": {}}}

    df = pipe.get_feature_importance_summary()

    assert list(df.columns) == ["feature"]
    assert len(df) == 1


def test_feature_importance_summary_empty_selector_state():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.selected_features_ = ["G0"]
    pipe.feature_selector = StubStandardSelector()  # selected_features_ == {}
    pipe.consensus_selector = StubConsensusSelector()  # consensus_results_ == {}
    pipe.pipeline_results_ = {}

    df = pipe.get_feature_importance_summary()

    assert df.to_dict("records") == [{"feature": "G0"}]


# ===========================================================================
# save / load
# ===========================================================================


def test_save_pipeline_results_requires_results(tmp_path):
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    with pytest.raises(ValueError, match="No pipeline results to save"):
        pipe.save_pipeline_results(str(tmp_path / "out.joblib"))


def test_save_and_load_round_trip(tmp_path):
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.pipeline_results_ = {"pipeline_summary": {"pipeline_status": "completed"}}
    pipe.selected_features_ = ["G0", "G1"]
    pipe.explanations_ = {"global": {"top_features": []}}
    pipe.best_model_ = StubModel("rf")

    path = tmp_path / "results.joblib"
    pipe.save_pipeline_results(str(path))
    assert path.exists()

    other = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    other.load_pipeline_results(str(path))

    assert other.selected_features_ == ["G0", "G1"]
    assert other.pipeline_results_["pipeline_summary"]["pipeline_status"] == "completed"
    assert other.explanations_ == {"global": {"top_features": []}}


def test_save_pipeline_results_with_no_best_model(tmp_path):
    import joblib

    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.pipeline_results_ = {"a": 1}
    pipe.selected_features_ = ["G0"]
    path = tmp_path / "nb.joblib"
    pipe.save_pipeline_results(str(path))

    assert joblib.load(path)["best_model_name"] is None


# ===========================================================================
# get_pipeline_report
# ===========================================================================


def test_get_pipeline_report_requires_results():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    with pytest.raises(ValueError, match="No pipeline results available"):
        pipe.get_pipeline_report()


def test_get_pipeline_report_from_full_run(monkeypatch):
    X, y = make_xy()
    pipe = build_pipeline(monkeypatch)
    pipe.run_complete_pipeline(
        X,
        y,
        n_features=3,
        cv_folds=2,
        n_permutations=5,
        run_nested_cross_validation=False,
    )

    report = pipe.get_pipeline_report()

    assert set(report) == {
        "executive_summary",
        "feature_selection_summary",
        "model_performance",
        "statistical_validation",
        "feature_importance",
        "timing_analysis",
        "recommendations",
    }
    assert report["executive_summary"]["pipeline_status"] == "completed"
    assert isinstance(report["feature_importance"], list)
    assert isinstance(report["recommendations"], list)


# ===========================================================================
# _generate_recommendations
# ===========================================================================


def test_recommendations_empty_when_nothing_to_flag():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.pipeline_results_ = {
        "pipeline_summary": {
            "performance_metrics": {"roc_auc": 0.8},
            "statistical_significance": {"model_significant": True},
        }
    }
    pipe.selected_features_ = [f"G{i}" for i in range(20)]

    assert pipe._generate_recommendations() == []


def test_recommendations_low_auc_and_few_features():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.pipeline_results_ = {
        "pipeline_summary": {"performance_metrics": {"roc_auc": 0.6}}
    }
    pipe.selected_features_ = ["G0"]

    recs = pipe._generate_recommendations()

    assert any("below 0.7 ROC-AUC" in r for r in recs)
    assert any("Few features selected" in r for r in recs)


def test_recommendations_high_auc_and_many_features():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.pipeline_results_ = {
        "pipeline_summary": {
            "performance_metrics": {"roc_auc": 0.95},
            "statistical_significance": {"model_significant": False},
        }
    }
    pipe.selected_features_ = [f"G{i}" for i in range(150)]

    recs = pipe._generate_recommendations()

    assert any("Excellent model performance" in r for r in recs)
    assert any("not statistically significant" in r for r in recs)
    assert any("Many features selected" in r for r in recs)


def test_recommendations_without_summary_or_features():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.pipeline_results_ = {"timing": {}}
    pipe.selected_features_ = []

    assert pipe._generate_recommendations() == []


def test_recommendations_summary_without_metrics_sections():
    pipe = MLPipeline(random_state=RANDOM_STATE, n_jobs=1)
    pipe.pipeline_results_ = {"pipeline_summary": {}}
    pipe.selected_features_ = None

    assert pipe._generate_recommendations() == []
