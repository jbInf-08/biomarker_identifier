"""Self-contained coverage tests for app.data_processing.feature_selection.

Run with --noconftest: no shared fixtures are used, all data is built inline.
"""

import json
import os

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_local.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "True")

from app.data_processing.feature_selection import (  # noqa: E402
    FeatureSelection,
    _flatten_linear_coefs,
)

N_GENES = 12
N_SAMPLES = 30


def make_expression(n_genes=N_GENES, n_samples=N_SAMPLES, seed=0, nonneg=True):
    """genes x samples matrix (rows = features, columns = samples)."""
    rng = np.random.RandomState(seed)
    values = rng.rand(n_genes, n_samples) * 5.0
    # Give a few genes much larger variance so ordering is deterministic-ish.
    values[0] *= 10
    values[1] *= 6
    if not nonneg:
        values = values - 20.0
    return pd.DataFrame(
        values,
        index=[f"GENE{i}" for i in range(n_genes)],
        columns=[f"S{j}" for j in range(n_samples)],
    )


def make_binary_labels(n_samples=N_SAMPLES, dtype="int"):
    half = n_samples // 2
    vals = [0] * half + [1] * (n_samples - half)
    if dtype == "object":
        vals = ["ctrl" if v == 0 else "case" for v in vals]
    return pd.Series(vals, index=[f"S{j}" for j in range(n_samples)])


def make_continuous_labels(n_samples=N_SAMPLES, seed=1):
    rng = np.random.RandomState(seed)
    # > 10 unique numeric values -> regression branches
    return pd.Series(
        rng.rand(n_samples) * 100.0, index=[f"S{j}" for j in range(n_samples)]
    )


def fs_new():
    return FeatureSelection()


def _make_importance_estimator(n_features):
    """Estimator stub exposing feature_importances_ but no coef_.

    Used to reach the `else` branch of the embedded selectors, which the real
    sklearn linear models never trigger (they always expose coef_).
    """
    importances = np.zeros(n_features)
    importances[0] = 0.7
    importances[2] = 0.3

    class _ImportanceEstimator:
        def __init__(self, *args, **kwargs):
            self.feature_importances_ = importances

        def fit(self, X, y):
            return self

    return _ImportanceEstimator


# ---------------------------------------------------------------------------
# module-level helper
# ---------------------------------------------------------------------------


class TestFlattenLinearCoefs:
    def test_one_dimensional_passthrough(self):
        arr = np.array([1.0, -2.0, 3.0])
        out = _flatten_linear_coefs(arr)
        assert out.shape == (3,)
        assert out[1] == pytest.approx(-2.0)

    def test_two_dimensional_takes_max_abs_across_classes(self):
        arr = np.array([[1.0, -5.0], [-3.0, 2.0]])
        out = _flatten_linear_coefs(arr)
        assert out.shape == (2,)
        assert out[0] == pytest.approx(3.0)
        assert out[1] == pytest.approx(5.0)

    def test_accepts_list_input(self):
        out = _flatten_linear_coefs([[0.0, 1.0]])
        assert out.shape == (2,)


# ---------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_config(self):
        fs = FeatureSelection()
        assert fs.config == {}
        assert fs.selection_results == {}
        assert fs.selected_features == []
        assert fs.feature_scores == {}

    def test_custom_config(self):
        fs = FeatureSelection({"alpha": 0.1})
        assert fs.config["alpha"] == 0.1


# ---------------------------------------------------------------------------
# filter methods
# ---------------------------------------------------------------------------


class TestFilterMethods:
    def test_default_methods_all_run(self):
        fs = FeatureSelection()
        data = make_expression()
        labels = make_binary_labels()
        res = fs.filter_methods(data, labels, n_features=4)
        assert set(res.keys()) == {"variance", "f_test", "mutual_info", "correlation"}
        for name, block in res.items():
            assert "error" not in block, f"{name} unexpectedly errored: {block}"
            assert isinstance(block["selected_features"], list)
            assert block["n_selected"] == len(block["selected_features"])

    def test_legacy_singular_method_kwarg(self):
        fs = FeatureSelection()
        res = fs.filter_methods(
            make_expression(), make_binary_labels(), method="variance", n_features=3
        )
        assert list(res.keys()) == ["variance"]
        assert res["variance"]["method"] == "variance"

    def test_explicit_methods_win_over_legacy_kwarg(self):
        fs = FeatureSelection()
        res = fs.filter_methods(
            make_expression(),
            make_binary_labels(),
            methods=["correlation"],
            method="variance",
            n_features=2,
        )
        assert list(res.keys()) == ["correlation"]

    def test_unknown_method_is_skipped(self):
        fs = FeatureSelection()
        res = fs.filter_methods(
            make_expression(), make_binary_labels(), methods=["not_a_method"]
        )
        assert res == {}

    def test_exception_is_captured_as_error_entry(self):
        fs = FeatureSelection()
        data = make_expression()
        # label vector shorter than the sample axis -> sklearn raises
        labels = pd.Series([0, 1, 0, 1, 0])
        res = fs.filter_methods(data, labels, methods=["f_test"], n_features=3)
        assert "error" in res["f_test"]
        assert isinstance(res["f_test"]["error"], str)

    def test_anova_and_chi2_methods(self):
        fs = FeatureSelection()
        data = make_expression()
        labels = make_binary_labels()
        res = fs.filter_methods(data, labels, methods=["anova", "chi2"], n_features=5)
        assert res["anova"]["method"] == "anova"
        assert res["chi2"]["method"] == "chi2"
        assert len(res["anova"]["selected_features"]) == 5
        assert len(res["chi2"]["selected_features"]) == 5


class TestVarianceFilter:
    def test_auto_threshold_from_n_features(self):
        fs = FeatureSelection()
        data = make_expression()
        out = fs._variance_filter(data, n_features=3)
        assert out["method"] == "variance"
        assert out["threshold"] > 0
        assert len(out["feature_scores"]) == N_GENES
        assert set(out["selected_features"]).issubset(set(data.index))
        assert out["n_selected"] == len(out["selected_features"])

    def test_explicit_threshold(self):
        fs = FeatureSelection()
        data = make_expression()
        out = fs._variance_filter(data, n_features=3, threshold=0.0)
        assert out["threshold"] == 0.0
        # every gene has non-zero variance
        assert out["n_selected"] == N_GENES

    def test_huge_threshold_raises_from_sklearn(self):
        fs = FeatureSelection()
        # sklearn's VarianceThreshold raises when nothing survives the cut
        with pytest.raises(ValueError, match="variance threshold"):
            fs._variance_filter(make_expression(), n_features=3, threshold=1e9)

    def test_extra_kwargs_ignored(self):
        fs = FeatureSelection()
        out = fs._variance_filter(make_expression(), n_features=2, bogus="x")
        assert out["method"] == "variance"


class TestFTestFilter:
    def test_classification_branch_numeric_labels(self):
        fs = FeatureSelection()
        data = make_expression()
        out = fs._f_test_filter(data, make_binary_labels(), n_features=4)
        assert out["method"] == "f_test"
        assert len(out["selected_features"]) == 4
        assert len(out["p_values"]) == N_GENES
        assert all(0.0 <= v <= 1.0 for v in out["p_values"].values())

    def test_classification_branch_object_labels(self):
        fs = FeatureSelection()
        out = fs._f_test_filter(
            make_expression(), make_binary_labels(dtype="object"), n_features=3
        )
        assert out["n_selected"] == 3

    def test_regression_branch_continuous_labels(self):
        fs = FeatureSelection()
        out = fs._f_test_filter(
            make_expression(), make_continuous_labels(), n_features=3
        )
        assert out["n_selected"] == 3
        assert len(out["feature_scores"]) == N_GENES


class TestMutualInfoFilter:
    def test_classification_branch(self):
        fs = FeatureSelection()
        out = fs._mutual_info_filter(
            make_expression(), make_binary_labels(), n_features=3
        )
        assert out["method"] == "mutual_info"
        assert out["n_selected"] == 3
        assert all(v >= 0 for v in out["feature_scores"].values())

    def test_regression_branch(self):
        fs = FeatureSelection()
        out = fs._mutual_info_filter(
            make_expression(), make_continuous_labels(), n_features=2
        )
        assert out["n_selected"] == 2


class TestCorrelationFilter:
    def test_numeric_labels(self):
        fs = FeatureSelection()
        out = fs._correlation_filter(
            make_expression(), make_continuous_labels(), n_features=5
        )
        assert out["method"] == "correlation"
        assert out["n_selected"] == 5
        assert all(0.0 <= v <= 1.0 for v in out["feature_scores"].values())

    def test_object_labels_use_label_encoding(self):
        fs = FeatureSelection()
        out = fs._correlation_filter(
            make_expression(), make_binary_labels(dtype="object"), n_features=3
        )
        assert out["n_selected"] == 3

    def test_constant_gene_yields_zero_score(self):
        fs = FeatureSelection()
        data = make_expression()
        data.loc["GENE0"] = 1.0  # zero variance -> corrcoef is nan -> scored 0
        out = fs._correlation_filter(data, make_continuous_labels(), n_features=N_GENES)
        assert out["feature_scores"]["GENE0"] == 0

    def test_n_features_larger_than_available(self):
        fs = FeatureSelection()
        out = fs._correlation_filter(
            make_expression(), make_binary_labels(), n_features=999
        )
        assert out["n_selected"] == N_GENES


class TestAnovaFilter:
    def test_two_groups(self):
        fs = FeatureSelection()
        out = fs._anova_filter(make_expression(), make_binary_labels(), n_features=4)
        assert out["method"] == "anova"
        assert out["n_selected"] == 4
        assert len(out["p_values"]) == N_GENES

    def test_single_class_labels_hit_bare_except(self):
        fs = FeatureSelection()
        data = make_expression()
        labels = pd.Series([1] * N_SAMPLES, index=data.columns)
        out = fs._anova_filter(data, labels, n_features=3)
        # f_oneway with a single group raises -> fallbacks are recorded
        assert set(out["feature_scores"].values()) == {0}
        assert set(out["p_values"].values()) == {1.0}
        assert out["n_selected"] == 3

    def test_three_groups(self):
        fs = FeatureSelection()
        data = make_expression()
        labels = pd.Series([i % 3 for i in range(N_SAMPLES)], index=data.columns)
        out = fs._anova_filter(data, labels, n_features=2)
        assert out["n_selected"] == 2


class TestChi2Filter:
    def test_non_negative_data_used_as_is(self):
        fs = FeatureSelection()
        out = fs._chi2_filter(make_expression(), make_binary_labels(), n_features=4)
        assert out["method"] == "chi2"
        assert out["n_selected"] == 4
        assert len(out["p_values"]) == N_GENES

    def test_negative_data_is_shifted(self):
        fs = FeatureSelection()
        data = make_expression(nonneg=False)
        assert data.min().min() < 0
        out = fs._chi2_filter(data, make_binary_labels(), n_features=3)
        assert out["n_selected"] == 3
        assert all(v >= 0 for v in out["feature_scores"].values())


# ---------------------------------------------------------------------------
# wrapper methods
# ---------------------------------------------------------------------------


class TestWrapperMethods:
    def test_rfe_only(self):
        fs = FeatureSelection()
        res = fs.wrapper_methods(
            make_expression(), make_binary_labels(), methods=["rfe"], n_features=3
        )
        assert res["rfe"]["n_selected"] == 3
        assert res["rfe"]["estimator_type"] == "logistic"

    def test_unknown_wrapper_skipped(self):
        fs = FeatureSelection()
        res = fs.wrapper_methods(
            make_expression(), make_binary_labels(), methods=["nope"]
        )
        assert res == {}

    def test_wrapper_error_captured(self):
        fs = FeatureSelection()
        res = fs.wrapper_methods(
            make_expression(),
            pd.Series([0, 1, 0, 1, 0]),  # inconsistent sample count
            methods=["rfe"],
            n_features=3,
        )
        assert "error" in res["rfe"]

    def test_default_methods_include_sequential(self):
        fs = FeatureSelection()
        data = make_expression(n_genes=5, n_samples=20)
        labels = make_binary_labels(20)
        res = fs.wrapper_methods(data, labels, n_features=2)
        assert set(res.keys()) == {"rfe", "sequential_forward", "sequential_backward"}
        for block in res.values():
            assert "error" not in block


class TestRfeWrapper:
    @pytest.mark.parametrize(
        "estimator_type", ["logistic", "svm", "unknown_falls_back"]
    )
    def test_classification_estimators(self, estimator_type):
        fs = FeatureSelection()
        out = fs._rfe_wrapper(
            make_expression(),
            make_binary_labels(),
            n_features=3,
            estimator_type=estimator_type,
        )
        assert out["method"] == "rfe"
        assert out["estimator_type"] == estimator_type
        assert out["n_selected"] == 3
        assert len(out["feature_ranking"]) == N_GENES
        assert min(out["feature_ranking"].values()) == 1

    def test_linear_estimator_with_continuous_labels(self):
        fs = FeatureSelection()
        out = fs._rfe_wrapper(
            make_expression(),
            make_continuous_labels(),
            n_features=4,
            estimator_type="linear",
        )
        assert out["n_selected"] == 4


class TestSequentialWrappers:
    def test_forward_selection(self):
        fs = FeatureSelection()
        data = make_expression(n_genes=5, n_samples=20)
        out = fs._sequential_forward_wrapper(data, make_binary_labels(20), n_features=2)
        assert out["method"] == "sequential_forward"
        assert out["n_selected"] == 2
        assert len(set(out["selected_features"])) == 2

    def test_forward_caps_at_available_features(self):
        fs = FeatureSelection()
        data = make_expression(n_genes=3, n_samples=20)
        out = fs._sequential_forward_wrapper(
            data, make_binary_labels(20), n_features=50
        )
        assert out["n_selected"] == 3

    def test_forward_breaks_when_every_fit_fails(self):
        fs = FeatureSelection()
        data = make_expression(n_genes=4, n_samples=20)
        # one-class labels make cross_val_score raise for every candidate
        labels = pd.Series([1] * 20, index=data.columns)
        out = fs._sequential_forward_wrapper(data, labels, n_features=2)
        assert out["selected_features"] == []
        assert out["n_selected"] == 0

    def test_backward_selection(self):
        fs = FeatureSelection()
        data = make_expression(n_genes=5, n_samples=20)
        out = fs._sequential_backward_wrapper(
            data, make_binary_labels(20), n_features=3
        )
        assert out["method"] == "sequential_backward"
        assert out["n_selected"] == 3
        assert set(out["selected_features"]).issubset(set(data.index))

    def test_backward_noop_when_already_small_enough(self):
        fs = FeatureSelection()
        data = make_expression(n_genes=3, n_samples=20)
        out = fs._sequential_backward_wrapper(
            data, make_binary_labels(20), n_features=5
        )
        assert out["n_selected"] == 3

    def test_backward_breaks_when_every_fit_fails(self):
        fs = FeatureSelection()
        data = make_expression(n_genes=4, n_samples=20)
        labels = pd.Series([1] * 20, index=data.columns)
        out = fs._sequential_backward_wrapper(data, labels, n_features=1)
        # nothing can be scored, so the full set is returned unchanged
        assert out["n_selected"] == 4


# ---------------------------------------------------------------------------
# embedded methods
# ---------------------------------------------------------------------------


class TestEmbeddedMethods:
    def test_all_default_methods(self):
        fs = FeatureSelection()
        data = make_expression()
        labels = make_binary_labels()
        res = fs.embedded_methods(data, labels)
        assert set(res.keys()) == {"lasso", "elastic_net", "random_forest", "svm"}
        for name, block in res.items():
            assert "error" not in block, f"{name} errored: {block}"

    def test_kwargs_are_filtered_per_method(self):
        fs = FeatureSelection()
        res = fs.embedded_methods(
            make_expression(),
            make_binary_labels(),
            methods=["lasso", "elastic_net", "random_forest", "svm"],
            alpha=0.05,
            l1_ratio=0.3,
            n_estimators=5,
            C=0.5,
            unrelated="ignored",
        )
        assert res["lasso"]["alpha"] == 0.05
        assert res["elastic_net"]["l1_ratio"] == 0.3
        assert res["random_forest"]["n_estimators"] == 5
        assert res["svm"]["C"] == 0.5

    def test_unknown_embedded_method_skipped(self):
        fs = FeatureSelection()
        res = fs.embedded_methods(
            make_expression(), make_binary_labels(), methods=["mystery"]
        )
        assert res == {}

    def test_embedded_error_captured(self):
        fs = FeatureSelection()
        data = make_expression()
        labels = make_binary_labels()
        res = fs.embedded_methods(data, labels, methods=["lasso"], alpha=0.0)
        # C = 1/alpha -> ZeroDivisionError inside the method
        assert "error" in res["lasso"]


class TestLassoEmbedded:
    def test_classification_branch(self):
        fs = FeatureSelection()
        out = fs._lasso_embedded(make_expression(), make_binary_labels(), alpha=0.1)
        assert out["method"] == "lasso"
        assert out["alpha"] == 0.1
        assert len(out["feature_scores"]) == N_GENES
        assert out["n_selected"] == len(out["selected_features"])

    def test_regression_branch(self):
        fs = FeatureSelection()
        out = fs._lasso_embedded(make_expression(), make_continuous_labels(), alpha=1.0)
        assert out["method"] == "lasso"
        assert all(v >= 0 for v in out["feature_scores"].values())

    def test_object_labels(self):
        fs = FeatureSelection()
        out = fs._lasso_embedded(
            make_expression(), make_binary_labels(dtype="object"), alpha=0.5
        )
        assert isinstance(out["selected_features"], list)

    def test_estimator_without_coef_uses_feature_importances(self, monkeypatch):
        import app.data_processing.feature_selection as mod

        monkeypatch.setattr(mod, "Lasso", _make_importance_estimator(N_GENES))
        out = fs_new()._lasso_embedded(make_expression(), make_continuous_labels())
        assert out["selected_features"] == ["GENE0", "GENE2"]
        assert out["n_selected"] == 2


class TestElasticNetEmbedded:
    def test_classification_branch(self):
        fs = FeatureSelection()
        out = fs._elastic_net_embedded(
            make_expression(), make_binary_labels(), alpha=1.0, l1_ratio=0.5
        )
        assert out["method"] == "elastic_net"
        assert out["l1_ratio"] == 0.5
        assert len(out["feature_scores"]) == N_GENES

    def test_regression_branch(self):
        fs = FeatureSelection()
        out = fs._elastic_net_embedded(
            make_expression(), make_continuous_labels(), alpha=1.0, l1_ratio=0.2
        )
        assert out["alpha"] == 1.0
        assert out["n_selected"] == len(out["selected_features"])

    def test_estimator_without_coef_uses_feature_importances(self, monkeypatch):
        import app.data_processing.feature_selection as mod

        monkeypatch.setattr(mod, "ElasticNet", _make_importance_estimator(N_GENES))
        out = fs_new()._elastic_net_embedded(
            make_expression(), make_continuous_labels()
        )
        assert out["selected_features"] == ["GENE0", "GENE2"]


class TestRandomForestEmbedded:
    def test_classification_branch(self):
        fs = FeatureSelection()
        out = fs._random_forest_embedded(
            make_expression(), make_binary_labels(), n_estimators=10
        )
        assert out["method"] == "random_forest"
        assert out["n_estimators"] == 10
        assert out["importance_threshold"] == pytest.approx(1.0 / N_GENES, rel=1e-6)
        assert len(out["feature_scores"]) == N_GENES

    def test_regression_branch(self):
        fs = FeatureSelection()
        out = fs._random_forest_embedded(
            make_expression(), make_continuous_labels(), n_estimators=10
        )
        assert out["n_selected"] == len(out["selected_features"])
        assert sum(out["feature_scores"].values()) == pytest.approx(1.0, abs=1e-6)


class TestSvmEmbedded:
    def test_classification_branch_binary(self):
        fs = FeatureSelection()
        out = fs._svm_embedded(make_expression(), make_binary_labels(), C=0.1)
        assert out["method"] == "svm"
        assert out["C"] == 0.1
        assert len(out["feature_scores"]) == N_GENES

    def test_regression_branch_uses_1d_coef(self):
        fs = FeatureSelection()
        out = fs._svm_embedded(make_expression(), make_continuous_labels(), C=1.0)
        assert out["n_selected"] == len(out["selected_features"])
        assert all(v >= 0 for v in out["feature_scores"].values())

    def test_multiclass_classification(self):
        fs = FeatureSelection()
        data = make_expression()
        labels = pd.Series([i % 3 for i in range(N_SAMPLES)], index=data.columns)
        out = fs._svm_embedded(data, labels, C=1.0)
        # coef_ is (n_classes, n_features); only the first row is used
        assert len(out["feature_scores"]) == N_GENES


# ---------------------------------------------------------------------------
# stability selection
# ---------------------------------------------------------------------------


class TestStabilitySelection:
    def test_happy_path(self):
        fs = FeatureSelection()
        out = fs.stability_selection(
            make_expression(), make_binary_labels(), n_bootstrap=3, threshold=0.5
        )
        assert out["method"] == "stability_selection"
        assert out["n_bootstrap"] == 3
        assert len(out["selection_probabilities"]) == N_GENES
        assert all(0.0 <= p <= 1.0 for p in out["selection_probabilities"].values())
        assert out["n_selected"] == len(out["selected_features"])

    def test_threshold_zero_selects_everything(self):
        fs = FeatureSelection()
        out = fs.stability_selection(
            make_expression(), make_binary_labels(), n_bootstrap=2, threshold=0.0
        )
        assert out["n_selected"] == N_GENES

    def test_alpha_kwarg_forwarded(self):
        fs = FeatureSelection()
        out = fs.stability_selection(
            make_expression(),
            make_binary_labels(),
            n_bootstrap=2,
            threshold=0.9,
            alpha=1.0,
            ignored_kwarg="x",
        )
        assert out["threshold"] == 0.9

    def test_too_few_samples_returns_error_block(self):
        fs = FeatureSelection()
        data = make_expression(n_genes=3, n_samples=1)
        labels = pd.Series([0], index=data.columns)
        out = fs.stability_selection(data, labels, n_bootstrap=5)
        assert out["error"].startswith("Not enough samples")
        assert out["selected_features"] == []
        assert out["n_selected"] == 0

    def test_single_class_gives_no_successful_bootstraps(self):
        fs = FeatureSelection()
        data = make_expression(n_genes=4, n_samples=10)
        labels = pd.Series([1] * 10, index=data.columns)
        out = fs.stability_selection(data, labels, n_bootstrap=3)
        assert out["error"] == "No successful bootstrap iterations"
        assert out["n_selected"] == 0

    def test_all_bootstraps_failing_is_handled(self, monkeypatch):
        fs = FeatureSelection()

        def boom(*args, **kwargs):
            raise RuntimeError("lasso exploded")

        monkeypatch.setattr(fs, "_lasso_embedded", boom)
        out = fs.stability_selection(
            make_expression(n_genes=3, n_samples=10),
            make_binary_labels(10),
            n_bootstrap=2,
        )
        assert out["error"] == "No successful bootstrap iterations"


# ---------------------------------------------------------------------------
# ensemble selection
# ---------------------------------------------------------------------------


class TestEnsembleSelection:
    def test_default_methods(self):
        fs = FeatureSelection()
        out = fs.ensemble_selection(
            make_expression(), make_binary_labels(), n_features=4
        )
        assert out["method"] == "ensemble"
        assert set(out["individual_methods"].keys()) == {
            "f_test",
            "mutual_info",
            "lasso",
            "random_forest",
        }
        assert len(out["feature_votes"]) == N_GENES
        assert out["n_selected"] == len(out["selected_features"])

    def test_explicit_methods_and_threshold(self):
        fs = FeatureSelection()
        out = fs.ensemble_selection(
            make_expression(),
            make_binary_labels(),
            methods=["variance", "svm"],
            voting_threshold=1.0,
            n_features=3,
        )
        assert set(out["individual_methods"].keys()) == {"variance", "svm"}
        assert out["min_votes"] == 2
        assert out["voting_threshold"] == 1.0

    def test_no_recognised_methods_selects_all_features(self):
        fs = FeatureSelection()
        out = fs.ensemble_selection(
            make_expression(), make_binary_labels(), methods=["bogus"]
        )
        assert out["individual_methods"] == {}
        assert out["min_votes"] == 0
        # every feature has 0 votes >= 0 -> all selected
        assert out["n_selected"] == N_GENES

    def test_errored_methods_do_not_count_toward_n_methods(self):
        fs = FeatureSelection()
        out = fs.ensemble_selection(
            make_expression(),
            make_binary_labels(),
            methods=["variance", "lasso"],
            threshold=1e9,  # makes the variance filter blow up
            voting_threshold=1.0,
        )
        assert "error" in out["individual_methods"]["variance"]
        # only lasso counts as a successful method
        assert out["min_votes"] == 1


# ---------------------------------------------------------------------------
# summary + persistence
# ---------------------------------------------------------------------------


class TestSelectionSummary:
    def test_empty_results(self):
        fs = FeatureSelection()
        assert fs.get_selection_summary() == {"status": "No selection performed"}

    def test_populated_results_union_features(self):
        fs = FeatureSelection()
        fs.selection_results = {
            "a": {"selected_features": ["G1", "G2"]},
            "b": {"selected_features": ["G2", "G3"]},
            "c": {"error": "boom"},
        }
        summary = fs.get_selection_summary()
        assert summary["methods_applied"] == ["a", "b", "c"]
        assert summary["total_features_selected"] == 3
        assert summary["method_results"] is fs.selection_results


class TestSaveSelectionResults:
    def test_writes_json(self, tmp_path):
        fs = FeatureSelection()
        fs.selection_results = {
            "variance": {
                "selected_features": ["G1"],
                "threshold": np.float64(0.5),
            }
        }
        target = tmp_path / "results.json"
        returned = fs.save_selection_results(str(target))
        assert returned == str(target)
        payload = json.loads(target.read_text())
        assert payload["variance"]["selected_features"] == ["G1"]

    def test_empty_results_still_writes(self, tmp_path):
        fs = FeatureSelection()
        target = tmp_path / "empty.json"
        fs.save_selection_results(str(target))
        assert json.loads(target.read_text()) == {}

    def test_bad_path_reraises(self, tmp_path):
        fs = FeatureSelection()
        bad = tmp_path / "missing_dir" / "nested" / "out.json"
        with pytest.raises(OSError):
            fs.save_selection_results(str(bad))


# ---------------------------------------------------------------------------
# end-to-end-ish integration over a small matrix
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_results_can_be_stored_and_summarised(self, tmp_path):
        fs = FeatureSelection()
        data = make_expression(n_genes=8, n_samples=24)
        labels = make_binary_labels(24)

        fs.selection_results.update(
            fs.filter_methods(
                data, labels, methods=["variance", "f_test"], n_features=3
            )
        )
        fs.selection_results.update(
            fs.embedded_methods(data, labels, methods=["random_forest"], n_estimators=5)
        )

        summary = fs.get_selection_summary()
        assert set(summary["methods_applied"]) == {
            "variance",
            "f_test",
            "random_forest",
        }
        assert summary["total_features_selected"] >= 1

        out = tmp_path / "e2e.json"
        fs.save_selection_results(str(out))
        assert out.exists()
