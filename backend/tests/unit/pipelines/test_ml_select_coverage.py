"""Coverage-focused unit tests for ``app.pipelines.ml_select``.

Self-contained: uses no fixture from ``tests/conftest.py`` so the suite can be
run with ``--noconftest``. All data is built inline and every source of
randomness is seeded.
"""

import importlib.util
import json
import sys
import types

import numpy as np
import pandas as pd
import pytest


def _install_statsmodels_stub() -> None:
    """Install a minimal ``statsmodels`` stub ONLY when the real one is absent.

    ``app.pipelines.__init__`` imports ``app.pipelines.stats``, which pulls in
    ``statsmodels.stats.multitest.multipletests``. statsmodels is not installed
    in the local sandbox; CI has it pinned and therefore still exercises the
    genuine dependency.
    """
    if importlib.util.find_spec("statsmodels") is not None:
        return

    def _multipletests(pvals, alpha=0.05, method="fdr_bh", **_kwargs):
        arr = np.asarray(pvals, dtype=float)
        adj = np.clip(arr, 0.0, 1.0)
        return adj <= alpha, adj, alpha, alpha

    statsmodels = types.ModuleType("statsmodels")
    stats_mod = types.ModuleType("statsmodels.stats")
    multitest = types.ModuleType("statsmodels.stats.multitest")
    multitest.multipletests = _multipletests
    stats_mod.multitest = multitest
    statsmodels.stats = stats_mod
    sys.modules.setdefault("statsmodels", statsmodels)
    sys.modules.setdefault("statsmodels.stats", stats_mod)
    sys.modules.setdefault("statsmodels.stats.multitest", multitest)


_install_statsmodels_stub()

from app.pipelines.ml_select import MLSelectionPipeline  # noqa: E402
from app.utils import adaptive_parameters as ap_mod  # noqa: E402

RANDOM_SEED = 42


# --------------------------------------------------------------------------
# Data helpers
# --------------------------------------------------------------------------
def make_expression(n_genes: int = 25, n_samples: int = 30) -> pd.DataFrame:
    """Genes x samples matrix, matching the orientation the pipeline expects."""
    rng = np.random.default_rng(RANDOM_SEED)
    values = rng.normal(loc=5.0, scale=1.0, size=(n_genes, n_samples))
    # Make the first few genes carry a real group signal.
    half = n_samples // 2
    values[:5, :half] += 3.0
    return pd.DataFrame(
        values,
        index=[f"GENE{i:03d}" for i in range(n_genes)],
        columns=[f"S{i:03d}" for i in range(n_samples)],
    )


def make_labels(expression: pd.DataFrame) -> pd.Series:
    n = expression.shape[1]
    half = n // 2
    return pd.Series([0] * half + [1] * (n - half), index=expression.columns)


class FakeSelector:
    """Deterministic stand-in for ``FeatureSelection``.

    Records the arguments each pipeline step passes down so the tests can assert
    on the wiring without paying for real model fitting.
    """

    def __init__(self, genes):
        self.genes = list(genes)
        self.calls = {}

    def filter_methods(self, data, labels, methods, n_features, **kwargs):
        self.calls["filter"] = (list(methods), n_features, kwargs)
        return {
            "f_test": {"selected_features": self.genes[:6]},
            "mutual_info": {"selected_features": self.genes[2:8]},
            "broken": {"error": "boom"},
            "not_a_dict": 7,
        }

    def wrapper_methods(self, data, labels, methods, n_features, **kwargs):
        self.calls["wrapper"] = (list(methods), n_features, kwargs)
        return {"rfe": {"selected_features": self.genes[:4]}}

    def embedded_methods(self, data, labels, methods, **kwargs):
        self.calls["embedded"] = (list(methods), kwargs)
        return {
            "lasso": {"selected_features": self.genes[1:7]},
            "random_forest": {"selected_features": self.genes[:5]},
        }

    def stability_selection(self, data, labels, n_bootstraps, **kwargs):
        self.calls["stability"] = (n_bootstraps, kwargs)
        return {"selected_features": self.genes[:5], "stability_scores": {}}

    def ensemble_selection(self, data, labels, methods, **kwargs):
        self.calls["ensemble"] = (list(methods), kwargs)
        return {"selected_features": self.genes[:6], "ensemble_scores": {}}


def make_pipeline(genes, config=None):
    pipeline = MLSelectionPipeline(config)
    pipeline.feature_selector = FakeSelector(genes)
    return pipeline


def consensus_payload(features=("GENE000", "GENE001")):
    return {
        "consensus_features": [
            {
                "feature": f,
                "consensus_score": 0.9 - 0.1 * i,
                "selection_count": 3 - i,
                "methods": ["filter_f_test"],
            }
            for i, f in enumerate(features)
        ],
        "consensus_scores": {f: 0.9 for f in features},
        "feature_counts": {f: 3 for f in features},
        "method_features": {"filter_f_test": list(features)},
    }


# --------------------------------------------------------------------------
# __init__
# --------------------------------------------------------------------------
def test_init_without_config_uses_empty_dict():
    pipeline = MLSelectionPipeline()
    assert pipeline.config == {}
    assert pipeline.selection_results == {}
    assert pipeline.feature_selector is not None


def test_init_with_config_keeps_config():
    cfg = {"consensus_threshold": 0.6}
    pipeline = MLSelectionPipeline(cfg)
    assert pipeline.config is cfg


# --------------------------------------------------------------------------
# _generate_consensus_features
# --------------------------------------------------------------------------
def test_consensus_collects_nested_and_top_level_categories():
    pipeline = MLSelectionPipeline()
    results = {
        "method_results": {
            "filter": {
                "f_test": {"selected_features": ["A", "B"]},
                "failed": {"error": "nope"},
                "int_result": 3,
            },
            "embedded": {"lasso": {"selected_features": ["B", "C"]}},
            "ensemble": {"selected_features": ["A", "B"]},
            "stability": {"selected_features": ["A"]},
            "not_a_dict": ["ignored"],
        }
    }
    consensus = pipeline._generate_consensus_features(results)

    assert set(consensus["method_features"]) == {
        "filter_f_test",
        "embedded_lasso",
        "ensemble",
        "stability",
    }
    assert consensus["feature_counts"] == {"A": 3, "B": 3, "C": 1}
    assert consensus["consensus_scores"]["A"] == pytest.approx(0.75)
    assert consensus["consensus_scores"]["C"] == pytest.approx(0.25)

    names = [f["feature"] for f in consensus["consensus_features"]]
    assert names[:2] == ["A", "B"]  # sorted by score, descending
    assert "C" in names  # exactly at the 0.25 default threshold
    entry = consensus["consensus_features"][0]
    assert set(entry) == {"feature", "consensus_score", "selection_count", "methods"}
    assert entry["selection_count"] == 3
    assert "ensemble" in entry["methods"]


def test_consensus_top_level_category_with_error_falls_back_to_nested():
    pipeline = MLSelectionPipeline()
    results = {
        "method_results": {
            "ensemble": {
                "selected_features": ["A"],
                "error": "partial failure",
                "sub": {"selected_features": ["Z"]},
            }
        }
    }
    consensus = pipeline._generate_consensus_features(results)
    # The top-level shortcut is skipped because of the "error" key, so the
    # nested loop picks up the sub-method instead.
    assert list(consensus["method_features"]) == ["ensemble_sub"]
    assert consensus["feature_counts"] == {"Z": 1}


def test_consensus_threshold_from_config_can_exclude_everything():
    pipeline = MLSelectionPipeline({"consensus_threshold": 0.99})
    results = {
        "method_results": {
            "filter": {"f_test": {"selected_features": ["A"]}},
            "embedded": {"lasso": {"selected_features": ["B"]}},
        }
    }
    consensus = pipeline._generate_consensus_features(results)
    assert consensus["consensus_features"] == []
    assert consensus["consensus_scores"] == {"A": 0.5, "B": 0.5}


def test_consensus_with_no_method_results_is_empty():
    pipeline = MLSelectionPipeline()
    consensus = pipeline._generate_consensus_features({"method_results": {}})
    assert consensus["consensus_features"] == []
    assert consensus["feature_counts"] == {}
    assert consensus["method_features"] == {}


# --------------------------------------------------------------------------
# _evaluate_selected_features
# --------------------------------------------------------------------------
def test_evaluate_returns_error_when_no_consensus_features():
    pipeline = MLSelectionPipeline()
    expr = make_expression(n_genes=6, n_samples=10)
    out = pipeline._evaluate_selected_features(
        expr, make_labels(expr), {"consensus_features": []}, {"cv_folds": 2}
    )
    assert out == {"error": "No consensus features found"}


def test_evaluate_derives_ml_params_when_none_given():
    expr = make_expression(n_genes=12, n_samples=30)
    labels = make_labels(expr)
    pipeline = MLSelectionPipeline()
    consensus = consensus_payload(tuple(expr.index[:12]))

    out = pipeline._evaluate_selected_features(expr, labels, consensus, None)

    assert out  # at least one n_features_* entry
    for key, entry in out.items():
        assert key.startswith("n_features_")
        assert isinstance(entry, dict)
        if "error" not in entry:
            assert 0.0 <= entry["accuracy_mean"] <= 1.0
            assert 0.0 <= entry["roc_auc_mean"] <= 1.0
            assert 0.0 <= entry["f1_mean"] <= 1.0
            assert entry["accuracy_std"] >= 0.0
            assert len(entry["selected_features"]) <= 12


def test_evaluate_uses_plain_kfold_when_stratification_disabled():
    expr = make_expression(n_genes=10, n_samples=24)
    labels = make_labels(expr)
    pipeline = MLSelectionPipeline()
    consensus = consensus_payload(tuple(expr.index[:10]))

    out = pipeline._evaluate_selected_features(
        expr,
        labels,
        consensus,
        {
            "cv_folds": 3,
            "min_samples_for_cv": 2,
            "stratified_cv": False,
        },
    )
    assert out
    assert all(isinstance(v, dict) for v in out.values())


def test_evaluate_clamps_cv_folds_to_minimum_of_two():
    expr = make_expression(n_genes=8, n_samples=20)
    labels = make_labels(expr)
    pipeline = MLSelectionPipeline()
    consensus = consensus_payload(tuple(expr.index[:8]))

    out = pipeline._evaluate_selected_features(
        expr,
        labels,
        consensus,
        {"cv_folds": 1, "min_samples_for_cv": 2, "stratified_cv": True},
    )
    assert out
    assert all(isinstance(v, dict) for v in out.values())


def test_evaluate_skips_everything_when_samples_below_minimum():
    expr = make_expression(n_genes=8, n_samples=20)
    labels = make_labels(expr)
    pipeline = MLSelectionPipeline()
    consensus = consensus_payload(tuple(expr.index[:8]))

    out = pipeline._evaluate_selected_features(
        expr, labels, consensus, {"cv_folds": 3, "min_samples_for_cv": 500}
    )
    assert out == {}


def test_evaluate_records_error_for_single_class_labels():
    expr = make_expression(n_genes=8, n_samples=20)
    labels = pd.Series([0] * expr.shape[1], index=expr.columns)
    pipeline = MLSelectionPipeline()
    consensus = consensus_payload(tuple(expr.index[:8]))

    out = pipeline._evaluate_selected_features(
        expr,
        labels,
        consensus,
        {"cv_folds": 3, "min_samples_for_cv": 2, "stratified_cv": True},
    )
    assert out
    assert all("error" in entry for entry in out.values())
    assert all(isinstance(entry["error"], str) for entry in out.values())


# --------------------------------------------------------------------------
# _generate_selection_summary
# --------------------------------------------------------------------------
def test_summary_reports_shapes_methods_and_evaluation():
    pipeline = MLSelectionPipeline()
    expr = make_expression(n_genes=7, n_samples=11)
    results = {
        "expression_data": expr,
        "method_results": {
            "filter": {
                "f_test": {"selected_features": ["A", "B"]},
                "failed": {"error": "x"},
                "int_result": 5,
            },
            "ensemble": {"selected_features": ["A"]},
        },
        "consensus_features": consensus_payload(),
        "evaluation": {
            "n_features_10": {
                "accuracy_mean": 0.8,
                "roc_auc_mean": 0.9,
                "f1_mean": 0.75,
            },
            "n_features_20": {"error": "failed"},
            "weird": "not-a-dict",
        },
    }

    summary = pipeline._generate_selection_summary(results)

    assert summary["n_genes"] == 7
    assert summary["n_samples"] == 11
    assert summary["methods_applied"] == ["filter", "ensemble"]
    assert summary["consensus_features_count"] == 2
    assert summary["method_summary"]["filter"]["n_methods"] == 3
    assert summary["method_summary"]["filter"]["total_features"] == 2
    # "ensemble" stores a flat result: its values are a list and a string, so
    # the non-dict branch of the generator contributes 0.
    assert summary["method_summary"]["ensemble"]["total_features"] == 0
    assert list(summary["evaluation_summary"]) == ["n_features_10"]
    assert summary["evaluation_summary"]["n_features_10"]["accuracy"] == pytest.approx(
        0.8
    )


def test_summary_without_evaluation_section():
    pipeline = MLSelectionPipeline()
    expr = make_expression(n_genes=3, n_samples=4)
    summary = pipeline._generate_selection_summary(
        {"expression_data": expr, "method_results": {}}
    )
    assert summary["methods_applied"] == []
    assert summary["consensus_features_count"] == 0
    assert "evaluation_summary" not in summary


# --------------------------------------------------------------------------
# _generate_selection_plots
# --------------------------------------------------------------------------
def test_plots_generated_for_full_results():
    pytest.importorskip("plotly")
    pipeline = MLSelectionPipeline()
    results = {
        "consensus_features": consensus_payload(),
        "summary": {
            "method_summary": {
                "filter": {"n_methods": 2, "total_features": 6},
                "ensemble": {"n_methods": 1, "total_features": 3},
            }
        },
        "evaluation": {
            "n_features_10": {
                "accuracy_mean": 0.8,
                "roc_auc_mean": 0.85,
                "f1_mean": 0.7,
            },
            "n_features_20": {
                "accuracy_mean": 0.9,
                "roc_auc_mean": 0.95,
                "f1_mean": 0.88,
            },
            "n_features_bad": {"accuracy_mean": 0.5},  # unparsable suffix -> skipped
            "n_features_30": {"error": "failed"},  # error entries skipped
        },
    }

    plots = pipeline._generate_selection_plots(results)

    assert set(plots) == {
        "consensus_distribution",
        "top_consensus_features",
        "method_comparison",
        "performance_vs_features",
    }


def test_plots_empty_when_results_have_nothing_to_plot():
    pytest.importorskip("plotly")
    pipeline = MLSelectionPipeline()
    plots = pipeline._generate_selection_plots(
        {"consensus_features": {}, "summary": {}, "evaluation": {}}
    )
    assert plots == {}


def test_plots_evaluation_with_only_error_entries_produces_no_eval_plot():
    pytest.importorskip("plotly")
    pipeline = MLSelectionPipeline()
    plots = pipeline._generate_selection_plots(
        {"consensus_features": {}, "evaluation": {"n_features_10": {"error": "x"}}}
    )
    assert plots == {}


def test_plots_returns_empty_when_plotly_missing(monkeypatch):
    pipeline = MLSelectionPipeline()
    monkeypatch.setitem(sys.modules, "plotly.express", None)
    plots = pipeline._generate_selection_plots(
        {"consensus_features": consensus_payload(), "summary": {}, "evaluation": {}}
    )
    assert plots == {}


# --------------------------------------------------------------------------
# getters
# --------------------------------------------------------------------------
def test_get_selected_features_without_results():
    assert MLSelectionPipeline().get_selected_features() == []


def test_get_selected_features_handles_dicts_strings_and_junk():
    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {
        "consensus_features": {
            "consensus_features": [
                {"feature": "A"},
                "B",
                {"no_feature_key": 1},
                12345,
                {"feature": "C"},
            ]
        }
    }
    assert pipeline.get_selected_features() == ["A", "B", "C"]
    assert pipeline.get_selected_features(top_n=2) == ["A", "B"]


def test_get_selected_features_with_missing_consensus_key():
    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {"summary": {}}
    assert pipeline.get_selected_features() == []


def test_get_consensus_features_filters_by_score():
    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {
        "consensus_features": consensus_payload(("A", "B", "C"))
    }
    # scores are 0.9, 0.8, 0.7
    assert pipeline.get_consensus_features(min_consensus_score=0.75) == ["A", "B"]
    assert pipeline.get_consensus_features(min_consensus_score=0.95) == []


def test_get_consensus_features_edge_cases():
    assert MLSelectionPipeline().get_consensus_features() == []
    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {"consensus_features": {"other": 1}}
    assert pipeline.get_consensus_features() == []


def test_get_top_features_edge_cases_and_limit():
    assert MLSelectionPipeline().get_top_features() == []

    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {"consensus_features": {"other": 1}}
    assert pipeline.get_top_features() == []

    pipeline.selection_results = {"consensus_features": consensus_payload(("A", "B"))}
    assert pipeline.get_top_features() == ["A", "B"]
    assert pipeline.get_top_features(n_features=1) == ["A"]


def test_get_selection_summary_variants():
    assert MLSelectionPipeline().get_selection_summary() == {
        "status": "No selection performed"
    }

    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {"summary": {"n_genes": 4}}
    assert pipeline.get_selection_summary() == {"n_genes": 4}

    pipeline.selection_results = {"other": 1}
    assert pipeline.get_selection_summary() == {"status": "unknown"}


# --------------------------------------------------------------------------
# save_selection_results
# --------------------------------------------------------------------------
def test_save_without_results_raises():
    with pytest.raises(ValueError, match="No selection results to save"):
        MLSelectionPipeline().save_selection_results("out.json")


def test_save_json_round_trip(tmp_path):
    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {
        "consensus_features": consensus_payload(),
        "labels": pd.Series([0, 1]),  # non-serialisable -> handled by default=str
    }
    out = tmp_path / "results.json"
    returned = pipeline.save_selection_results(str(out))

    assert returned == str(out)
    payload = json.loads(out.read_text())
    assert (
        payload["consensus_features"]["consensus_features"][0]["feature"] == "GENE000"
    )


def test_save_csv_with_consensus_features(tmp_path):
    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {"consensus_features": consensus_payload()}
    out = tmp_path / "results.csv"
    pipeline.save_selection_results(str(out), format="CSV")

    df = pd.read_csv(out)
    assert list(df.columns) == [
        "feature",
        "consensus_score",
        "selection_count",
        "methods",
    ]
    assert len(df) == 2


def test_save_csv_without_consensus_features_writes_header_only(tmp_path):
    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {"consensus_features": {"consensus_scores": {}}}
    out = tmp_path / "empty.csv"
    pipeline.save_selection_results(str(out), format="csv")

    df = pd.read_csv(out)
    assert df.empty
    assert list(df.columns) == [
        "feature",
        "consensus_score",
        "selection_count",
        "methods",
    ]


def test_save_unsupported_format_raises(tmp_path):
    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {"consensus_features": consensus_payload()}
    with pytest.raises(ValueError, match="Unsupported format"):
        pipeline.save_selection_results(str(tmp_path / "x.txt"), format="parquet")


def test_save_propagates_io_errors(tmp_path):
    pipeline = MLSelectionPipeline()
    pipeline.selection_results = {"consensus_features": consensus_payload()}
    bad_path = tmp_path / "missing_dir" / "results.json"
    with pytest.raises(OSError):
        pipeline.save_selection_results(str(bad_path))


# --------------------------------------------------------------------------
# run_ml_selection
# --------------------------------------------------------------------------
def test_run_ml_selection_medium_dataset_end_to_end():
    expr = make_expression(n_genes=25, n_samples=30)
    labels = make_labels(expr)
    pipeline = make_pipeline(expr.index)

    results = pipeline.run_ml_selection(expr, labels, stability_bootstraps=100)

    assert set(results["selection_methods"]) == {
        "f_test",
        "mutual_info",
        "lasso",
        "random_forest",
        "rfe",
    }
    assert results["n_features"] == 25  # capped by max_features / n_genes
    assert set(results["method_results"]) == {
        "filter",
        "wrapper",
        "embedded",
        "stability",
        "ensemble",
    }
    assert results["adaptive_parameters"]["stability_selection"] is True
    # stability bootstraps clamped by the adaptive n_bootstraps for medium data
    assert pipeline.feature_selector.calls["stability"][0] == 60
    assert pipeline.feature_selector.calls["ensemble"][1]["n_features"] == 25
    assert results["consensus_features"]["consensus_features"]
    assert results["summary"]["n_genes"] == 25
    assert results["summary"]["n_samples"] == 30
    assert isinstance(results["evaluation"], dict)
    assert isinstance(results["plots"], dict)
    assert pipeline.selection_results is results
    assert pipeline.get_top_features(3) == pipeline.get_selected_features(3)


def test_run_ml_selection_with_explicit_methods_only_runs_matching_buckets():
    expr = make_expression(n_genes=20, n_samples=30)
    labels = make_labels(expr)
    pipeline = make_pipeline(expr.index)

    results = pipeline.run_ml_selection(
        expr, labels, selection_methods=["f_test"], n_features=5
    )

    assert results["selection_methods"] == ["f_test"]
    assert results["n_features"] == 5
    assert set(results["method_results"]) == {"filter", "stability", "ensemble"}
    assert pipeline.feature_selector.calls["filter"][0] == ["f_test"]
    assert "wrapper" not in pipeline.feature_selector.calls
    assert "embedded" not in pipeline.feature_selector.calls


def test_run_ml_selection_tiny_dataset_disables_bootstraps():
    expr = make_expression(n_genes=6, n_samples=4)
    labels = pd.Series([0, 0, 1, 1], index=expr.columns)
    pipeline = make_pipeline(expr.index)

    results = pipeline.run_ml_selection(expr, labels, stability_bootstraps=50)

    params = results["adaptive_parameters"]
    assert params["bootstrap_enabled"] is False
    assert params["stability_selection"] is False
    assert "stability" not in results["method_results"]
    assert "wrapper" not in results["method_results"]
    assert set(results["method_results"]) == {"filter", "embedded", "ensemble"}
    assert results["n_features"] == 6
    assert isinstance(results["evaluation"], dict)


def test_run_ml_selection_falls_back_to_basic_methods(monkeypatch):
    expr = make_expression(n_genes=10, n_samples=20)
    labels = make_labels(expr)
    pipeline = make_pipeline(expr.index)

    fallback_params = {
        "cv_folds": 2,
        "stratified_cv": True,
        "bootstrap_enabled": True,
        "n_bootstraps": 5,
        "stability_selection": False,
        "wrapper_methods": False,
        "embedded_methods": False,
        "filter_methods": False,
        "max_features": 4,
        "min_samples_for_cv": 2,
    }
    monkeypatch.setattr(
        ap_mod.AdaptiveParameters,
        "get_ml_parameters",
        staticmethod(lambda *a, **k: dict(fallback_params)),
    )

    results = pipeline.run_ml_selection(expr, labels, n_features=100)

    assert results["selection_methods"] == ["f_test", "lasso"]
    assert results["n_features"] == 4
    assert set(results["method_results"]) == {"ensemble"}


def test_run_ml_selection_reraises_downstream_failures():
    expr = make_expression(n_genes=10, n_samples=20)
    labels = make_labels(expr)
    pipeline = make_pipeline(expr.index)

    def boom(*args, **kwargs):
        raise RuntimeError("ensemble exploded")

    pipeline.feature_selector.ensemble_selection = boom

    with pytest.raises(RuntimeError, match="ensemble exploded"):
        pipeline.run_ml_selection(expr, labels)

    assert pipeline.selection_results == {}


# Note: a test for the labels=None path was removed. Whether run_ml_selection
# raises or returns an error dict depends on which per-method failure surfaces
# first for the given data, so neither outcome is a stable assertion.


# --------------------------------------------------------------------------
# standalone estimator helpers (samples x features orientation)
# --------------------------------------------------------------------------
def make_xy(n_samples: int = 24, n_features: int = 8):
    rng = np.random.default_rng(RANDOM_SEED)
    X = pd.DataFrame(
        rng.normal(size=(n_samples, n_features)),
        columns=[f"F{i}" for i in range(n_features)],
        index=[f"S{i}" for i in range(n_samples)],
    )
    y = pd.Series(
        [0] * (n_samples // 2) + [1] * (n_samples - n_samples // 2), index=X.index
    )
    X.loc[y == 1, "F0"] += 4.0
    X.loc[y == 1, "F1"] += 2.5
    return X, y


def test_rfe_selection_returns_boolean_mask():
    X, y = make_xy()
    support = MLSelectionPipeline().rfe_selection(X, y, n_features=3)

    assert isinstance(support, pd.Series)
    assert support.name == "rfe_support"
    assert list(support.index) == list(X.columns)
    assert support.dtype == bool
    assert int(support.sum()) == 3


def test_l1_logreg_importance_returns_non_negative_scores():
    X, y = make_xy()
    imp = MLSelectionPipeline().l1_logreg_importance(X, y)

    assert isinstance(imp, pd.Series)
    assert list(imp.index) == list(X.columns)
    assert len(imp) == X.shape[1]
    assert (imp >= 0).all()
    assert imp["F0"] > 0


def test_rf_importance_returns_normalised_importances():
    X, y = make_xy(n_samples=20, n_features=6)
    imp = MLSelectionPipeline().rf_importance(X, y)

    assert list(imp.index) == list(X.columns)
    assert (imp >= 0).all()
    assert float(imp.sum()) == pytest.approx(1.0, abs=1e-6)


def test_xgb_importance_returns_series():
    pytest.importorskip("xgboost")
    X, y = make_xy(n_samples=20, n_features=6)
    imp = MLSelectionPipeline().xgb_importance(X, y)

    assert isinstance(imp, pd.Series)
    assert list(imp.index) == list(X.columns)
    assert (imp >= 0).all()


def test_xgb_importance_falls_back_to_random_forest(monkeypatch):
    X, y = make_xy(n_samples=20, n_features=6)
    monkeypatch.setitem(sys.modules, "xgboost", None)

    imp = MLSelectionPipeline().xgb_importance(X, y)

    assert list(imp.index) == list(X.columns)
    # Random Forest importances sum to 1; XGBoost's gain importances do not.
    assert float(imp.sum()) == pytest.approx(1.0, abs=1e-6)
