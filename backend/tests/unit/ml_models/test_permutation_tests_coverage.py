"""Self-contained coverage tests for app.ml_models.permutation_tests.

These tests intentionally avoid the repo-level conftest fixtures so the file can be
run with ``--noconftest``. All data/fixtures are defined locally and every heavy or
non-deterministic dependency is either seeded or mocked.
"""

import sys
import types
import warnings
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from app.ml_models import permutation_tests as pt
from app.ml_models.permutation_tests import PermutationTester, PermutationTestSuite

MODULE = "app.ml_models.permutation_tests"


# --------------------------------------------------------------------------- #
# Local fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def xy():
    """Small, well-separated, deterministic binary classification frame."""
    rng = np.random.RandomState(0)
    n = 30
    y = np.array([0] * (n // 2) + [1] * (n // 2))
    X = rng.normal(size=(n, 4))
    # make feature 0 informative so baseline auc is high and stable
    X[:, 0] += y * 3.0
    X = pd.DataFrame(X, columns=["f0", "f1", "f2", "f3"])
    return X, pd.Series(y, name="target")


@pytest.fixture
def model():
    return LogisticRegression(max_iter=200, random_state=42)


@pytest.fixture
def tester():
    # n_jobs=1 keeps the suite fast on Windows (no process pool spin-up)
    return PermutationTester(random_state=42, n_jobs=1)


class FakeSelector:
    """Minimal stand-in for the project's feature selector interface."""

    def __init__(self, features=("f0", "f1"), fail_on=()):
        self._features = list(features)
        self._fail_on = set(fail_on)
        self.n_calls = 0
        self.selected_features_ = {}

    def fit(self, X, y, n_features=None):
        call = self.n_calls
        self.n_calls += 1
        if call in self._fail_on:
            raise RuntimeError(f"selector blew up on call {call}")
        if call == 0:
            picked = self._features
        else:
            # rotate the selection so overlap varies between permutations
            picked = self._features[call % len(self._features) :] or self._features
        self.selected_features_ = {"features": list(picked)}
        return self


@pytest.fixture
def fake_statsmodels():
    """Provide statsmodels.stats.multitest.multipletests.

    statsmodels is not installed in the local test environment, and
    ``multiple_comparison_correction`` imports it unconditionally (even for the
    bonferroni branch). If the real package is present we use it untouched;
    otherwise we install a faithful BH/Holm stub for the duration of the test.
    """
    try:  # pragma: no cover - depends on environment
        import statsmodels.stats.multitest  # noqa: F401

        yield
        return
    except ImportError:
        pass

    def multipletests(pvals, method="fdr_bh", **kwargs):
        p = np.asarray(pvals, dtype=float)
        n = p.size
        order = np.argsort(p)
        ranked = p[order]
        if method == "fdr_bh":
            adj = ranked * n / np.arange(1, n + 1)
            adj = np.minimum.accumulate(adj[::-1])[::-1]
        elif method == "holm":
            adj = ranked * (n - np.arange(n))
            adj = np.maximum.accumulate(adj)
        else:  # pragma: no cover - not exercised
            raise ValueError(method)
        adj = np.clip(adj, 0.0, 1.0)
        out = np.empty(n, dtype=float)
        out[order] = adj
        return adj < 0.05, out, 0.05, 0.05

    multitest_mod = types.ModuleType("statsmodels.stats.multitest")
    multitest_mod.multipletests = multipletests
    stats_mod = types.ModuleType("statsmodels.stats")
    stats_mod.multitest = multitest_mod
    root_mod = types.ModuleType("statsmodels")
    root_mod.stats = stats_mod

    added = {
        "statsmodels": root_mod,
        "statsmodels.stats": stats_mod,
        "statsmodels.stats.multitest": multitest_mod,
    }
    sys.modules.update(added)
    try:
        yield
    finally:
        for key in added:
            sys.modules.pop(key, None)


# --------------------------------------------------------------------------- #
# __init__
# --------------------------------------------------------------------------- #


def test_init_defaults():
    t = PermutationTester()
    assert t.random_state == 42
    assert t.n_jobs == -1
    assert t.permutation_results_ == {}


def test_init_custom():
    t = PermutationTester(random_state=7, n_jobs=2)
    assert t.random_state == 7
    assert t.n_jobs == 2


# --------------------------------------------------------------------------- #
# feature_importance_permutation_test
# --------------------------------------------------------------------------- #


def test_feature_importance_happy_path(tester, model, xy):
    X, y = xy
    np.random.seed(0)
    res = tester.feature_importance_permutation_test(
        model, X, y, n_permutations=10, cv_folds=3
    )

    assert set(res) == {
        "baseline_performance",
        "feature_results",
        "significance_results",
    }
    assert 0.0 <= res["baseline_performance"] <= 1.0
    assert set(res["feature_results"]) == set(X.columns)

    for feat, fr in res["feature_results"].items():
        assert set(fr) == {
            "baseline_performance",
            "permuted_performance",
            "importance",
            "baseline_scores",
            "permuted_scores",
        }
        assert fr["importance"] == pytest.approx(
            fr["baseline_performance"] - fr["permuted_performance"]
        )
        assert len(fr["baseline_scores"]) == 3
        assert len(fr["permuted_scores"]) == 3

    sig = res["significance_results"]
    assert sig["n_features"] == 4
    assert 0.0 <= sig["corrected_p_value"] <= 1.0
    # results are cached on the instance
    assert tester.permutation_results_["feature_importance"] is res


def test_feature_importance_uses_custom_scoring(tester, model, xy):
    X, y = xy
    np.random.seed(1)
    res = tester.feature_importance_permutation_test(
        model, X, y, n_permutations=5, scoring="accuracy", cv_folds=3
    )
    assert 0.0 <= res["baseline_performance"] <= 1.0


def test_feature_importance_single_feature_zero_std(tester, model):
    """One feature -> std of importances is 0 -> cohens_d short-circuits to 0."""
    rng = np.random.RandomState(3)
    y = pd.Series([0] * 12 + [1] * 12)
    X = pd.DataFrame({"only": rng.normal(size=24) + y.values * 2.0})
    np.random.seed(2)
    res = tester.feature_importance_permutation_test(
        model, X, y, n_permutations=3, cv_folds=3
    )
    sig = res["significance_results"]
    assert sig["n_features"] == 1
    assert sig["std_importance"] == pytest.approx(0.0)
    assert sig["cohens_d"] == 0
    # a single sample t-test on one observation is undefined
    assert np.isnan(sig["p_value"])
    assert sig["corrected_p_value"] == pytest.approx(1.0) or np.isnan(
        sig["corrected_p_value"]
    )


def test_feature_importance_per_feature_exception_is_swallowed(tester, model, xy):
    """A failure while scoring one feature is logged and that feature is skipped."""
    X, y = xy
    calls = {"n": 0}

    def side_effect(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # first per-feature call after the baseline
            raise RuntimeError("scoring exploded")
        return np.array([0.9, 0.8, 0.85])

    with patch(f"{MODULE}.cross_val_score", side_effect=side_effect):
        res = tester.feature_importance_permutation_test(
            model, X, y, n_permutations=5, cv_folds=3
        )

    assert "f0" not in res["feature_results"]
    assert set(res["feature_results"]) == {"f1", "f2", "f3"}
    assert res["significance_results"]["n_features"] == 3


def test_feature_importance_all_features_fail(tester, model, xy):
    """Every feature errors out -> empty results, NaN statistics, no crash."""
    X, y = xy

    def side_effect(*args, **kwargs):
        if side_effect.first:
            side_effect.first = False
            return np.array([0.9, 0.9, 0.9])
        raise RuntimeError("always fails")

    side_effect.first = True

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with patch(f"{MODULE}.cross_val_score", side_effect=side_effect):
            res = tester.feature_importance_permutation_test(
                model, X, y, n_permutations=5, cv_folds=3
            )

    assert res["feature_results"] == {}
    sig = res["significance_results"]
    assert sig["n_features"] == 0
    assert np.isnan(sig["mean_importance"])
    assert sig["significant_features"] == []


def test_feature_importance_baseline_failure_propagates(tester, model, xy):
    """Errors in the baseline CV are not caught by the per-feature handler."""
    X, y = xy
    with patch(f"{MODULE}.cross_val_score", side_effect=ValueError("bad cv")):
        with pytest.raises(ValueError, match="bad cv"):
            tester.feature_importance_permutation_test(model, X, y, cv_folds=3)


def test_feature_importance_single_class_labels_raises(tester, model, xy):
    """All-one-class targets make StratifiedKFold/scoring fail up front."""
    X, _ = xy
    y_one = pd.Series(np.zeros(len(X), dtype=int))
    with pytest.raises(Exception):
        tester.feature_importance_permutation_test(model, X, y_one, cv_folds=3)


# --------------------------------------------------------------------------- #
# _test_feature_significance (called directly for the branchy bits)
# --------------------------------------------------------------------------- #


def test_test_feature_significance_flags_outlier_feature(tester):
    feature_results = {f"f{i}": {"importance": 0.01} for i in range(8)}
    feature_results["star"] = {"importance": 5.0}

    sig = tester._test_feature_significance(feature_results, n_permutations=10)

    assert sig["n_features"] == 9
    assert sig["significant_features"] == ["star"]
    assert sig["std_importance"] > 0
    assert sig["cohens_d"] == pytest.approx(
        sig["mean_importance"] / sig["std_importance"]
    )
    assert 0.0 <= sig["corrected_p_value"] <= 1.0


def test_test_feature_significance_zero_variance_gives_zero_cohens_d(tester):
    feature_results = {"a": {"importance": 0.5}, "b": {"importance": 0.5}}
    sig = tester._test_feature_significance(feature_results, n_permutations=1)
    assert sig["std_importance"] == pytest.approx(0.0)
    assert sig["cohens_d"] == 0
    assert sig["significant_features"] == []


def test_test_feature_significance_bonferroni_caps_at_one(tester):
    feature_results = {
        "a": {"importance": 0.10},
        "b": {"importance": 0.11},
        "c": {"importance": 0.09},
        "d": {"importance": 0.12},
    }
    sig = tester._test_feature_significance(feature_results, n_permutations=1)
    assert sig["corrected_p_value"] <= 1.0
    assert sig["corrected_p_value"] >= sig["p_value"]


# --------------------------------------------------------------------------- #
# model_performance_permutation_test
# --------------------------------------------------------------------------- #


def test_model_performance_happy_path(tester, model, xy):
    X, y = xy
    np.random.seed(4)
    res = tester.model_performance_permutation_test(
        model, X, y, n_permutations=5, cv_folds=3
    )

    assert set(res) == {
        "baseline_performance",
        "baseline_scores",
        "permuted_scores",
        "p_value",
        "effect_size",
        "n_permutations",
        "significant",
    }
    assert len(res["permuted_scores"]) == 5
    assert len(res["baseline_scores"]) == 3
    assert 0.0 <= res["p_value"] <= 1.0
    assert res["n_permutations"] == 5
    assert res["significant"] == (res["p_value"] < 0.05)
    assert res["effect_size"] == pytest.approx(
        res["baseline_performance"] - np.mean(res["permuted_scores"])
    )
    assert tester.permutation_results_["model_performance"] is res


def test_model_performance_signal_is_significant(tester, model, xy):
    """With a strongly informative feature the permuted null never beats baseline."""
    X, y = xy
    np.random.seed(5)
    res = tester.model_performance_permutation_test(
        model, X, y, n_permutations=8, scoring="accuracy", cv_folds=3
    )
    assert res["p_value"] == pytest.approx(0.0)
    assert res["significant"] is np.True_ or res["significant"] is True
    assert res["effect_size"] > 0


def test_model_performance_permutation_exception_is_swallowed(tester, model, xy):
    X, y = xy
    calls = {"n": 0}

    def side_effect(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("permutation failed")
        return np.array([0.6, 0.5, 0.55])

    with patch(f"{MODULE}.cross_val_score", side_effect=side_effect):
        res = tester.model_performance_permutation_test(
            model, X, y, n_permutations=4, cv_folds=3
        )

    # 4 requested, 1 raised -> 3 recorded
    assert len(res["permuted_scores"]) == 3
    assert res["n_permutations"] == 4


def test_model_performance_all_permutations_fail(tester, model, xy):
    X, y = xy

    def side_effect(*args, **kwargs):
        if side_effect.first:
            side_effect.first = False
            return np.array([0.9, 0.9, 0.9])
        raise RuntimeError("nope")

    side_effect.first = True

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with patch(f"{MODULE}.cross_val_score", side_effect=side_effect):
            res = tester.model_performance_permutation_test(
                model, X, y, n_permutations=3, cv_folds=3
            )

    assert res["permuted_scores"] == []
    assert np.isnan(res["p_value"])
    assert np.isnan(res["effect_size"])


def test_model_performance_zero_permutations(tester, model, xy):
    X, y = xy
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = tester.model_performance_permutation_test(
            model, X, y, n_permutations=0, cv_folds=3
        )
    assert res["permuted_scores"] == []
    assert np.isnan(res["p_value"])
    assert res["n_permutations"] == 0


# --------------------------------------------------------------------------- #
# stability_permutation_test
# --------------------------------------------------------------------------- #


def test_stability_happy_path(tester, xy):
    X, y = xy
    selector = FakeSelector(features=["f0", "f1"])
    np.random.seed(6)

    res = tester.stability_permutation_test(
        X, y, selector, n_permutations=4, n_features=2
    )

    assert set(res) == {
        "baseline_features",
        "mean_stability",
        "std_stability",
        "stability_scores",
        "p_value",
        "t_statistic",
        "random_chance",
        "feature_frequencies",
        "n_permutations",
    }
    assert sorted(res["baseline_features"]) == ["f0", "f1"]
    assert len(res["stability_scores"]) == 4
    assert all(0.0 <= s <= 1.0 for s in res["stability_scores"])
    assert res["random_chance"] == pytest.approx(2 / 4)
    assert res["mean_stability"] == pytest.approx(np.mean(res["stability_scores"]))
    assert set(res["feature_frequencies"]) <= set(X.columns)
    assert tester.permutation_results_["stability"] is res


def test_stability_selector_exception_is_swallowed(tester, xy):
    X, y = xy
    # call 0 = baseline, calls 1..3 = permutations; fail the second permutation
    selector = FakeSelector(features=["f0", "f1"], fail_on=(2,))

    res = tester.stability_permutation_test(
        X, y, selector, n_permutations=3, n_features=2
    )

    assert len(res["stability_scores"]) == 2
    assert res["n_permutations"] == 3


def test_stability_all_permutations_fail(tester, xy):
    X, y = xy
    selector = FakeSelector(features=["f0", "f1"], fail_on=(1, 2, 3))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = tester.stability_permutation_test(
            X, y, selector, n_permutations=3, n_features=2
        )

    assert res["stability_scores"] == []
    assert np.isnan(res["mean_stability"])
    assert np.isnan(res["p_value"])


def test_stability_baseline_failure_propagates(tester, xy):
    X, y = xy
    selector = FakeSelector(fail_on=(0,))
    with pytest.raises(RuntimeError, match="call 0"):
        tester.stability_permutation_test(
            X, y, selector, n_permutations=2, n_features=2
        )


def test_stability_zero_permutations(tester, xy):
    X, y = xy
    selector = FakeSelector(features=["f0"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = tester.stability_permutation_test(
            X, y, selector, n_permutations=0, n_features=1
        )
    assert res["stability_scores"] == []
    assert res["feature_frequencies"] == {}


# --------------------------------------------------------------------------- #
# multiple_comparison_correction
# --------------------------------------------------------------------------- #


@pytest.mark.usefixtures("fake_statsmodels")
def test_correction_bonferroni(tester):
    out = tester.multiple_comparison_correction([0.01, 0.02, 0.5], method="bonferroni")
    assert out == pytest.approx([0.03, 0.06, 1.0])


@pytest.mark.usefixtures("fake_statsmodels")
def test_correction_bonferroni_is_the_default(tester):
    assert tester.multiple_comparison_correction([0.1, 0.2]) == pytest.approx(
        [0.2, 0.4]
    )


@pytest.mark.usefixtures("fake_statsmodels")
@pytest.mark.parametrize("method", ["fdr_bh", "holm"])
def test_correction_statsmodels_methods(tester, method):
    p_values = [0.001, 0.01, 0.03, 0.2, 0.9]
    out = tester.multiple_comparison_correction(p_values, method=method)
    out = list(out)
    assert len(out) == len(p_values)
    assert all(0.0 <= v <= 1.0 for v in out)
    # correction can only make p-values larger (or equal)
    assert all(c >= p - 1e-12 for c, p in zip(out, p_values))


@pytest.mark.usefixtures("fake_statsmodels")
def test_correction_unknown_method_raises(tester):
    with pytest.raises(ValueError, match="Unknown correction method: nope"):
        tester.multiple_comparison_correction([0.1, 0.2], method="nope")


@pytest.mark.usefixtures("fake_statsmodels")
def test_correction_empty_list_bonferroni(tester):
    assert tester.multiple_comparison_correction([], method="bonferroni") == []


# --------------------------------------------------------------------------- #
# get_permutation_summary
# --------------------------------------------------------------------------- #


def test_summary_empty_returns_empty_dataframe(tester):
    df = tester.get_permutation_summary()
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_summary_all_test_types_and_unknown_key(tester):
    tester.permutation_results_ = {
        "feature_importance": {
            "baseline_performance": 0.9,
            "significance_results": {
                "mean_importance": 0.05,
                "p_value": 0.004,
                "corrected_p_value": 0.012,
            },
        },
        "model_performance": {
            "baseline_performance": 0.88,
            "p_value": 0.01,
            "effect_size": 0.3,
            "significant": True,
        },
        "stability": {
            "mean_stability": 0.72,
            "p_value": 0.2,
            "random_chance": 0.1,
        },
        "something_else": {"ignored": True},
    }

    df = tester.get_permutation_summary()

    assert len(df) == 3  # unknown key hits the `continue` branch
    assert list(df["test_type"]) == [
        "Feature Importance",
        "Model Performance",
        "Feature Stability",
    ]
    assert list(df["significant"]) == [True, True, False]
    assert df.loc[0, "mean_importance"] == pytest.approx(0.05)
    assert df.loc[1, "effect_size"] == pytest.approx(0.3)
    assert df.loc[2, "random_chance"] == pytest.approx(0.1)


def test_summary_not_significant_feature_importance(tester):
    tester.permutation_results_ = {
        "feature_importance": {
            "baseline_performance": 0.5,
            "significance_results": {
                "mean_importance": 0.0,
                "p_value": 0.9,
                "corrected_p_value": 1.0,
            },
        }
    }
    df = tester.get_permutation_summary()
    assert df.loc[0, "significant"] is False or df.loc[0, "significant"] == False


def test_summary_only_unknown_keys_returns_empty_dataframe(tester):
    tester.permutation_results_ = {"mystery": {}}
    df = tester.get_permutation_summary()
    assert df.empty


# --------------------------------------------------------------------------- #
# save_results / load_results
# --------------------------------------------------------------------------- #


def test_save_results_without_results_raises(tester):
    with pytest.raises(ValueError, match="No results to save"):
        tester.save_results("unused.joblib")


def test_save_and_load_roundtrip(tester, tmp_path):
    tester.permutation_results_ = {
        "model_performance": {"p_value": 0.01, "significant": True}
    }
    target = tmp_path / "perm.joblib"

    tester.save_results(str(target))
    assert target.exists()

    other = PermutationTester(random_state=1, n_jobs=1)
    other.load_results(str(target))
    assert other.permutation_results_ == tester.permutation_results_


def test_load_results_missing_file_raises(tester, tmp_path):
    with pytest.raises(Exception):
        tester.load_results(str(tmp_path / "does_not_exist.joblib"))


# --------------------------------------------------------------------------- #
# PermutationTestSuite
# --------------------------------------------------------------------------- #


def test_suite_init_builds_tester():
    suite = PermutationTestSuite(random_state=11, n_jobs=3)
    assert isinstance(suite.tester, PermutationTester)
    assert suite.tester.random_state == 11
    assert suite.tester.n_jobs == 3


def test_suite_init_defaults():
    suite = PermutationTestSuite()
    assert suite.tester.random_state == 42
    assert suite.tester.n_jobs == -1


def test_run_full_validation_without_selector(xy, model):
    X, y = xy
    suite = PermutationTestSuite(random_state=42, n_jobs=1)

    with patch.object(
        suite.tester, "model_performance_permutation_test", return_value={"mp": 1}
    ) as mp, patch.object(
        suite.tester, "feature_importance_permutation_test", return_value={"fi": 1}
    ) as fi, patch.object(
        suite.tester, "stability_permutation_test"
    ) as st, patch.object(
        suite.tester, "get_permutation_summary", return_value=pd.DataFrame([{"a": 1}])
    ):
        res = suite.run_full_validation(model, X, y, n_permutations=20)

    assert set(res) == {"model_performance", "feature_importance", "summary"}
    st.assert_not_called()
    mp.assert_called_once_with(model, X, y, n_permutations=20)
    fi.assert_called_once_with(model, X, y, n_permutations=20)
    assert isinstance(res["summary"], pd.DataFrame)


def test_run_full_validation_with_selector(xy, model):
    X, y = xy
    suite = PermutationTestSuite(random_state=42, n_jobs=1)
    selector = MagicMock()

    with patch.object(
        suite.tester, "model_performance_permutation_test", return_value={"mp": 1}
    ), patch.object(
        suite.tester, "feature_importance_permutation_test", return_value={"fi": 1}
    ), patch.object(
        suite.tester, "stability_permutation_test", return_value={"st": 1}
    ) as st, patch.object(
        suite.tester, "get_permutation_summary", return_value=pd.DataFrame()
    ):
        res = suite.run_full_validation(
            model, X, y, feature_selector=selector, n_permutations=50
        )

    assert set(res) == {
        "model_performance",
        "feature_importance",
        "stability",
        "summary",
    }
    # n_permutations // 10 is passed through to the stability test
    st.assert_called_once_with(X, y, selector, n_permutations=5)


def test_run_full_validation_end_to_end(xy, model):
    """Unmocked run over tiny data to exercise the real wiring."""
    X, y = xy
    suite = PermutationTestSuite(random_state=42, n_jobs=1)
    selector = FakeSelector(features=["f0", "f1"])
    np.random.seed(7)

    res = suite.run_full_validation(
        model, X, y, feature_selector=selector, n_permutations=10
    )

    assert set(res) == {
        "model_performance",
        "feature_importance",
        "stability",
        "summary",
    }
    assert len(res["model_performance"]["permuted_scores"]) == 10
    assert set(res["feature_importance"]["feature_results"]) == set(X.columns)
    assert len(res["stability"]["stability_scores"]) == 1
    assert len(res["summary"]) == 3


# --------------------------------------------------------------------------- #
# module surface
# --------------------------------------------------------------------------- #


def test_module_exports_expected_symbols():
    assert hasattr(pt, "PermutationTester")
    assert hasattr(pt, "PermutationTestSuite")
    assert pt.logger.name == MODULE
