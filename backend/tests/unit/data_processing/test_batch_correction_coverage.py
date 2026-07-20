"""
Coverage-focused unit tests for ``app.data_processing.batch_correction``.

Fully self-contained: no fixtures from ``tests/conftest.py`` are used so the
module can be exercised with ``pytest --noconftest``.

Important implementation detail that shapes these tests
-------------------------------------------------------
``BatchCorrection._calculate_component_batch_score`` indexes a *numpy* array
with the pandas ``Index`` of the batch samples::

    batch_mean = np.mean(component_data[batch_samples])

That only works when the sample labels are positional integers.  All tests
that exercise the PCA code paths therefore use integer column labels
(``0..n-1``); a dedicated test pins the ``IndexError`` raised for the (much
more realistic) string-labelled case.
"""

import importlib
import sys
import types

import numpy as np
import pandas as pd
import pytest

from app.data_processing.batch_correction import BatchCorrection

# ---------------------------------------------------------------------------
# statsmodels stub
# ---------------------------------------------------------------------------
# ``_anova_batch_detection`` does a function-local
# ``from statsmodels.stats.multitest import multipletests``.  statsmodels is not
# part of the pinned test environment, so provide a faithful Benjamini-Hochberg
# implementation when (and only when) the real package is unavailable.


def _bh_multipletests(pvals, alpha=0.05, method="fdr_bh", **kwargs):
    p = np.asarray(pvals, dtype=float)
    n = p.size
    if n == 0:
        empty = np.array([], dtype=float)
        return np.array([], dtype=bool), empty, alpha, alpha
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    adjusted_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted_sorted = np.clip(adjusted_sorted, 0.0, 1.0)
    adjusted = np.empty(n, dtype=float)
    adjusted[order] = adjusted_sorted
    return adjusted < alpha, adjusted, alpha, alpha


@pytest.fixture(autouse=True)
def statsmodels_available(monkeypatch):
    """Guarantee ``statsmodels.stats.multitest.multipletests`` is importable."""
    try:
        importlib.import_module("statsmodels.stats.multitest")
        yield
        return
    except ImportError:
        pass

    statsmodels = types.ModuleType("statsmodels")
    stats_pkg = types.ModuleType("statsmodels.stats")
    multitest = types.ModuleType("statsmodels.stats.multitest")
    multitest.multipletests = _bh_multipletests
    stats_pkg.multitest = multitest
    statsmodels.stats = stats_pkg

    monkeypatch.setitem(sys.modules, "statsmodels", statsmodels)
    monkeypatch.setitem(sys.modules, "statsmodels.stats", stats_pkg)
    monkeypatch.setitem(sys.modules, "statsmodels.stats.multitest", multitest)
    yield


# ---------------------------------------------------------------------------
# Data helpers / fixtures
# ---------------------------------------------------------------------------

N_GENES = 12
N_SAMPLES = 24
GENES = [f"GENE{i:02d}" for i in range(N_GENES)]


def _make_expression(n_genes=N_GENES, n_samples=N_SAMPLES, seed=0, int_columns=True):
    rng = np.random.default_rng(seed)
    values = rng.normal(loc=10.0, scale=1.0, size=(n_genes, n_samples))
    columns = (
        list(range(n_samples))
        if int_columns
        else [f"S{i:02d}" for i in range(n_samples)]
    )
    return pd.DataFrame(
        values,
        index=[f"GENE{i:02d}" for i in range(n_genes)],
        columns=columns,
    )


def _two_batch_series(n_samples=N_SAMPLES, int_columns=True):
    labels = ["B1"] * (n_samples // 2) + ["B2"] * (n_samples - n_samples // 2)
    index = (
        list(range(n_samples))
        if int_columns
        else [f"S{i:02d}" for i in range(n_samples)]
    )
    return pd.Series(labels, index=index)


@pytest.fixture
def expression():
    """Clean expression matrix with positional integer sample labels."""
    return _make_expression()


@pytest.fixture
def batch_info():
    return _two_batch_series()


@pytest.fixture
def batched_expression(expression, batch_info):
    """Expression data with a strong, deterministic additive batch shift."""
    data = expression.copy()
    b2 = batch_info[batch_info == "B2"].index
    data[b2] = data[b2] + 6.0
    return data


@pytest.fixture
def covariates(batch_info):
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        {"age": rng.normal(60, 5, size=len(batch_info))}, index=batch_info.index
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_config(self):
        bc = BatchCorrection()
        assert bc.config == {}
        assert bc.correction_params == {}
        assert bc.corrected_data is None
        assert bc.batch_effects is None

    def test_custom_config(self):
        bc = BatchCorrection({"method": "combat", "n": 3})
        assert bc.config["method"] == "combat"


# ---------------------------------------------------------------------------
# _calculate_batch_statistics
# ---------------------------------------------------------------------------


class TestBatchStatistics:
    def test_happy_path(self, expression, batch_info):
        stats = BatchCorrection()._calculate_batch_statistics(expression, batch_info)

        assert stats["n_batches"] == 2
        assert set(stats["batch_sizes"]) == {"B1", "B2"}
        assert sum(stats["batch_sizes"].values()) == N_SAMPLES
        assert set(stats["batch_means"]) == {"B1", "B2"}
        assert set(stats["batch_stds"]) == {"B1", "B2"}
        assert all(isinstance(v, float) for v in stats["batch_means"].values())
        assert isinstance(stats["mean_cv_across_batches"], float)
        assert set(stats["cv_distribution"]) == {"mean", "std", "median", "q25", "q75"}
        assert stats["cv_distribution"]["q25"] <= stats["cv_distribution"]["q75"]

    def test_single_batch(self, expression):
        single = pd.Series(["ONLY"] * N_SAMPLES, index=expression.columns)
        stats = BatchCorrection()._calculate_batch_statistics(expression, single)

        assert stats["n_batches"] == 1
        # With one batch there is no between-batch spread at all.
        assert stats["mean_cv_across_batches"] == pytest.approx(0.0, abs=1e-12)

    def test_non_positive_gene_mean_yields_zero_cv(self, expression, batch_info):
        """Covers the ``else 0`` branch of the CV computation."""
        data = expression.copy()
        data.loc["GENE00"] = 0.0
        data.loc["GENE01"] = -5.0

        stats = BatchCorrection()._calculate_batch_statistics(data, batch_info)
        assert stats["n_batches"] == 2
        assert stats["mean_cv_across_batches"] >= 0.0

    def test_single_sample_per_batch(self):
        data = _make_expression(n_genes=4, n_samples=2)
        batches = pd.Series(["B1", "B2"], index=[0, 1])
        stats = BatchCorrection()._calculate_batch_statistics(data, batches)

        assert stats["n_batches"] == 2
        # batch_stds is NOT NaN here: the std is taken across the genes within
        # each batch, not across that batch's samples, so a one-sample batch
        # still has a well-defined spread over its gene values.
        assert all(np.isfinite(v) for v in stats["batch_stds"].values())
        assert set(stats["batch_stds"]) == {"B1", "B2"}


# ---------------------------------------------------------------------------
# _calculate_component_batch_score
# ---------------------------------------------------------------------------


class TestComponentBatchScore:
    def test_single_batch_returns_zero(self):
        bc = BatchCorrection()
        component = np.arange(6, dtype=float)
        batches = pd.Series(["A"] * 6, index=range(6))
        assert bc._calculate_component_batch_score(component, batches) == 0.0

    def test_zero_variance_returns_zero(self):
        bc = BatchCorrection()
        component = np.zeros(6)
        batches = pd.Series(["A", "A", "A", "B", "B", "B"], index=range(6))
        assert bc._calculate_component_batch_score(component, batches) == 0.0

    def test_perfectly_separated_batches_scores_high(self):
        bc = BatchCorrection()
        component = np.array([-1.0, -1.0, -1.0, 1.0, 1.0, 1.0])
        batches = pd.Series(["A", "A", "A", "B", "B", "B"], index=range(6))
        score = bc._calculate_component_batch_score(component, batches)
        assert score == pytest.approx(1.0)

    def test_no_separation_scores_low(self):
        bc = BatchCorrection()
        component = np.array([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0])
        batches = pd.Series(["A", "A", "A", "B", "B", "B"], index=range(6))
        assert bc._calculate_component_batch_score(component, batches) < 0.2

    def test_string_labels_raise_index_error(self):
        """Documents the real behaviour: numpy cannot fancy-index with labels."""
        bc = BatchCorrection()
        component = np.arange(4, dtype=float)
        batches = pd.Series(["A", "A", "B", "B"], index=["s0", "s1", "s2", "s3"])
        with pytest.raises(IndexError):
            bc._calculate_component_batch_score(component, batches)


# ---------------------------------------------------------------------------
# _pca_batch_detection
# ---------------------------------------------------------------------------


class TestPcaBatchDetection:
    def test_structure_and_ranges(self, batched_expression, batch_info):
        res = BatchCorrection()._pca_batch_detection(batched_expression, batch_info)

        assert res["n_components"] == 10
        assert len(res["explained_variance_ratio"]) == min(10, N_GENES)
        assert len(res["cumulative_variance_ratio"]) == len(
            res["explained_variance_ratio"]
        )
        assert res["cumulative_variance_ratio"] == sorted(
            res["cumulative_variance_ratio"]
        )
        assert len(res["batch_scores_per_component"]) == min(10, N_GENES)
        assert 0.0 <= res["overall_batch_score"]
        assert isinstance(res["top_batch_components"], list)
        # A 6-unit additive shift must be picked up by at least one component.
        assert res["top_batch_components"]

    def test_custom_n_components(self, batched_expression, batch_info):
        res = BatchCorrection()._pca_batch_detection(
            batched_expression, batch_info, n_components=3
        )
        assert res["n_components"] == 3
        assert len(res["explained_variance_ratio"]) == 3

    def test_no_batch_effect_has_no_top_components(self, expression):
        single = pd.Series(["ONLY"] * N_SAMPLES, index=expression.columns)
        res = BatchCorrection()._pca_batch_detection(expression, single)
        assert res["top_batch_components"] == []
        assert res["overall_batch_score"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _anova_batch_detection
# ---------------------------------------------------------------------------


class TestAnovaBatchDetection:
    def test_strong_batch_effect_detected(self, batched_expression, batch_info):
        res = BatchCorrection()._anova_batch_detection(batched_expression, batch_info)

        assert res["n_significant_genes"] == N_GENES
        assert res["n_significant_genes_fdr"] == N_GENES
        assert res["proportion_significant"] == pytest.approx(1.0)
        assert res["proportion_significant_fdr"] == pytest.approx(1.0)
        assert res["mean_f_statistic"] > 0
        assert 0.0 <= res["median_p_value"] <= 1.0
        assert sorted(res["significant_genes"]) == sorted(GENES)

    def test_no_batch_effect(self, expression, batch_info):
        res = BatchCorrection()._anova_batch_detection(expression, batch_info)
        assert res["proportion_significant_fdr"] <= 0.5
        assert isinstance(res["significant_genes_fdr"], list)

    def test_custom_alpha(self, batched_expression, batch_info):
        res = BatchCorrection()._anova_batch_detection(
            batched_expression, batch_info, alpha=1e-300
        )
        assert res["n_significant_genes_fdr"] == 0

    def test_single_batch_triggers_anova_exception_handler(self, expression):
        """``f_oneway`` needs >= 2 groups; the bare ``except`` must absorb it."""
        single = pd.Series(["ONLY"] * N_SAMPLES, index=expression.columns)
        with np.errstate(invalid="ignore"):
            with pytest.warns(RuntimeWarning):
                res = BatchCorrection()._anova_batch_detection(expression, single)

        assert res["n_significant_genes"] == 0
        assert res["n_significant_genes_fdr"] == 0
        assert res["median_p_value"] == pytest.approx(1.0)
        assert np.isnan(res["mean_f_statistic"])


# ---------------------------------------------------------------------------
# _correlation_batch_analysis
# ---------------------------------------------------------------------------


class TestCorrelationBatchAnalysis:
    def test_without_covariates(self, batched_expression, batch_info):
        res = BatchCorrection()._correlation_batch_analysis(
            batched_expression, batch_info
        )

        assert set(res["correlations"]) == {"batch_B1", "batch_B2"}
        for entry in res["correlations"].values():
            assert set(entry) == {
                "mean_correlation",
                "median_correlation",
                "max_correlation",
                "n_high_correlation",
            }
            assert 0.0 <= entry["mean_correlation"] <= 1.0
            assert entry["max_correlation"] <= 1.0 + 1e-9
        assert res["overall_batch_correlation"] > 0.8

    def test_with_covariates(self, batched_expression, batch_info, covariates):
        res = BatchCorrection()._correlation_batch_analysis(
            batched_expression, batch_info, covariates
        )
        assert "age" in res["correlations"]
        assert set(res["correlations"]) == {"batch_B1", "batch_B2", "age"}

    def test_constant_gene_nan_correlation_is_skipped(self, expression, batch_info):
        """Covers the ``if not np.isnan(correlation)`` false branch."""
        data = expression.copy()
        data.loc["GENE00"] = 1.0  # zero variance -> corrcoef returns NaN
        with warnings_suppressed():
            res = BatchCorrection()._correlation_batch_analysis(data, batch_info)

        assert not np.isnan(res["overall_batch_correlation"])
        assert res["correlations"]["batch_B1"]["n_high_correlation"] >= 0


class warnings_suppressed:
    """Tiny context manager: numpy emits divide warnings for constant genes."""

    def __enter__(self):
        self._old = np.seterr(all="ignore")
        import warnings

        self._cm = warnings.catch_warnings()
        self._cm.__enter__()
        warnings.simplefilter("ignore")
        return self

    def __exit__(self, *exc):
        self._cm.__exit__(*exc)
        np.seterr(**self._old)
        return False


# ---------------------------------------------------------------------------
# _calculate_batch_effect_score
# ---------------------------------------------------------------------------


class TestBatchEffectScore:
    def test_empty_results_returns_zero(self):
        assert BatchCorrection()._calculate_batch_effect_score({}) == 0.0

    def test_all_components(self):
        results = {
            "pca_analysis": {"overall_batch_score": 0.4},
            "anova_analysis": {"proportion_significant_fdr": 0.6},
            "correlation_analysis": {"overall_batch_correlation": 0.2},
            "batch_statistics": {"mean_cv_across_batches": 0.1},
        }
        # cv score = min(1.0, 0.1 / 0.5) = 0.2
        score = BatchCorrection()._calculate_batch_effect_score(results)
        assert score == pytest.approx((0.4 + 0.6 + 0.2 + 0.2) / 4)

    def test_cv_score_is_capped_at_one(self):
        results = {"batch_statistics": {"mean_cv_across_batches": 99.0}}
        assert BatchCorrection()._calculate_batch_effect_score(results) == 1.0

    def test_partial_results(self):
        results = {"pca_analysis": {"overall_batch_score": 0.5}}
        assert BatchCorrection()._calculate_batch_effect_score(results) == 0.5


# ---------------------------------------------------------------------------
# detect_batch_effects
# ---------------------------------------------------------------------------


class TestDetectBatchEffects:
    def test_happy_path(self, batched_expression, batch_info):
        res = BatchCorrection().detect_batch_effects(batched_expression, batch_info)

        assert set(res) == {
            "batch_statistics",
            "pca_analysis",
            "anova_analysis",
            "correlation_analysis",
            "overall_batch_effect_score",
        }
        assert isinstance(res["overall_batch_effect_score"], float)
        assert res["overall_batch_effect_score"] > 0.0

    def test_with_covariates(self, batched_expression, batch_info, covariates):
        res = BatchCorrection().detect_batch_effects(
            batched_expression, batch_info, covariates
        )
        assert "age" in res["correlation_analysis"]["correlations"]

    def test_string_sample_labels_propagate_index_error(self):
        data = _make_expression(int_columns=False)
        batches = _two_batch_series(int_columns=False)
        with pytest.raises(IndexError):
            BatchCorrection().detect_batch_effects(data, batches)


# ---------------------------------------------------------------------------
# Correction methods
# ---------------------------------------------------------------------------


class TestCombatCorrection:
    def test_reduces_batch_mean_gap(self, batched_expression, batch_info):
        bc = BatchCorrection()
        corrected = bc._combat_correction(batched_expression, batch_info)

        assert corrected.shape == batched_expression.shape
        assert list(corrected.index) == list(batched_expression.index)

        b1 = batch_info[batch_info == "B1"].index
        b2 = batch_info[batch_info == "B2"].index
        before = abs(
            batched_expression[b1].mean().mean() - batched_expression[b2].mean().mean()
        )
        after = abs(corrected[b1].mean().mean() - corrected[b2].mean().mean())
        assert after < before

        params = bc.correction_params["combat"]
        assert params["method"] == "combat"
        assert set(params["batch_means"]) == {"B1", "B2"}
        assert set(params["batch_vars"]) == {"B1", "B2"}
        assert len(params["global_mean"]) == N_GENES
        assert len(params["global_var"]) == N_GENES

    def test_singleton_batch_yields_nan(self, expression):
        batches = pd.Series(
            ["B1"] * (N_SAMPLES - 1) + ["SOLO"], index=expression.columns
        )
        with warnings_suppressed():
            corrected = BatchCorrection()._combat_correction(expression, batches)
        # variance of a single sample is NaN -> that column becomes NaN
        assert corrected[N_SAMPLES - 1].isna().all()

    def test_covariates_argument_is_ignored(
        self, batched_expression, batch_info, covariates
    ):
        bc = BatchCorrection()
        a = bc._combat_correction(batched_expression, batch_info)
        b = bc._combat_correction(batched_expression, batch_info, covariates)
        pd.testing.assert_frame_equal(a, b)


class TestLimmaCorrection:
    def test_removes_batch_shift(self, batched_expression, batch_info):
        bc = BatchCorrection()
        corrected = bc._limma_correction(batched_expression, batch_info)

        assert corrected.shape == batched_expression.shape
        b1 = batch_info[batch_info == "B1"].index
        b2 = batch_info[batch_info == "B2"].index
        gap = abs(corrected[b1].mean().mean() - corrected[b2].mean().mean())
        assert gap < 1e-6

        params = bc.correction_params["limma"]
        assert params["method"] == "limma"
        assert params["design_matrix_columns"] == ["batch_B1", "batch_B2"]

    def test_with_covariates_extends_design_matrix(
        self, batched_expression, batch_info, covariates
    ):
        bc = BatchCorrection()
        bc._limma_correction(batched_expression, batch_info, covariates)
        assert bc.correction_params["limma"]["design_matrix_columns"] == [
            "batch_B1",
            "batch_B2",
            "age",
        ]


class TestPcaCorrection:
    def test_removes_batch_components(self, batched_expression, batch_info):
        bc = BatchCorrection()
        corrected = bc._pca_correction(batched_expression, batch_info)

        assert corrected.shape == batched_expression.shape
        assert list(corrected.columns) == list(batched_expression.columns)
        params = bc.correction_params["pca"]
        assert params["method"] == "pca"
        assert params["n_components"] == 10
        assert params["batch_components_removed"]
        assert len(params["explained_variance_ratio"]) == min(10, N_GENES)

    def test_no_batch_components_returns_copy(self, expression):
        """Single batch -> every component scores 0.0 -> ``else`` branch."""
        single = pd.Series(["ONLY"] * N_SAMPLES, index=expression.columns)
        bc = BatchCorrection()
        corrected = bc._pca_correction(expression, single)

        pd.testing.assert_frame_equal(corrected, expression)
        assert bc.correction_params["pca"]["batch_components_removed"] == []

    def test_custom_n_components(self, batched_expression, batch_info):
        bc = BatchCorrection()
        bc._pca_correction(batched_expression, batch_info, n_components=2)
        assert bc.correction_params["pca"]["n_components"] == 2
        assert len(bc.correction_params["pca"]["explained_variance_ratio"]) == 2


class TestLinearRegressionCorrection:
    def test_removes_batch_shift(self, batched_expression, batch_info):
        bc = BatchCorrection()
        corrected = bc._linear_regression_correction(batched_expression, batch_info)

        assert corrected.shape == batched_expression.shape
        b1 = batch_info[batch_info == "B1"].index
        b2 = batch_info[batch_info == "B2"].index
        assert abs(corrected[b1].mean().mean() - corrected[b2].mean().mean()) < 1e-6

        params = bc.correction_params["linear_regression"]
        assert params["method"] == "linear_regression"
        assert params["design_matrix_columns"] == ["batch_B1", "batch_B2"]
        assert set(params["coefficients"]) == set(GENES)

    def test_coefficients_leak_last_model(self, batched_expression, batch_info):
        """KNOWN BUG: every gene is stored with the *last* model's coefficients."""
        bc = BatchCorrection()
        bc._linear_regression_correction(batched_expression, batch_info)
        coefs = list(bc.correction_params["linear_regression"]["coefficients"].values())
        assert all(c == coefs[0] for c in coefs)

    def test_with_covariates(self, batched_expression, batch_info, covariates):
        bc = BatchCorrection()
        bc._linear_regression_correction(batched_expression, batch_info, covariates)
        assert bc.correction_params["linear_regression"]["design_matrix_columns"] == [
            "batch_B1",
            "batch_B2",
            "age",
        ]


class TestMeanCenteringCorrection:
    def test_aligns_batch_means(self, batched_expression, batch_info):
        bc = BatchCorrection()
        corrected = bc._mean_centering_correction(batched_expression, batch_info)

        assert corrected.shape == batched_expression.shape
        b1 = batch_info[batch_info == "B1"].index
        b2 = batch_info[batch_info == "B2"].index
        # After centering each batch on the global mean the two batch means agree.
        np.testing.assert_allclose(
            corrected[b1].mean(axis=1).values,
            corrected[b2].mean(axis=1).values,
            atol=1e-8,
        )

        params = bc.correction_params["mean_centering"]
        assert params["method"] == "mean_centering"
        assert set(params["batch_means"]) == {"B1", "B2"}
        assert len(params["global_mean"]) == N_GENES

    def test_single_batch_is_identity(self, expression):
        single = pd.Series(["ONLY"] * N_SAMPLES, index=expression.columns)
        corrected = BatchCorrection()._mean_centering_correction(expression, single)
        np.testing.assert_allclose(corrected.values, expression.values, atol=1e-9)


# ---------------------------------------------------------------------------
# correct_batch_effects dispatcher
# ---------------------------------------------------------------------------


class TestCorrectBatchEffects:
    @pytest.mark.parametrize(
        "method",
        ["combat", "limma", "pca", "linear_regression", "mean_centering"],
    )
    def test_each_method(self, batched_expression, batch_info, method):
        bc = BatchCorrection()
        corrected = bc.correct_batch_effects(
            batched_expression, batch_info, method=method
        )

        assert isinstance(corrected, pd.DataFrame)
        assert corrected.shape == batched_expression.shape
        assert bc.corrected_data is corrected
        assert method in bc.correction_params

    def test_default_method_is_combat(self, batched_expression, batch_info):
        bc = BatchCorrection()
        bc.correct_batch_effects(batched_expression, batch_info)
        assert "combat" in bc.correction_params

    def test_covariates_passed_through(
        self, batched_expression, batch_info, covariates
    ):
        bc = BatchCorrection()
        bc.correct_batch_effects(
            batched_expression, batch_info, method="limma", covariates=covariates
        )
        assert "age" in bc.correction_params["limma"]["design_matrix_columns"]

    def test_kwargs_forwarded(self, batched_expression, batch_info):
        bc = BatchCorrection()
        bc.correct_batch_effects(
            batched_expression, batch_info, method="pca", n_components=3
        )
        assert bc.correction_params["pca"]["n_components"] == 3

    def test_unknown_method_raises(self, batched_expression, batch_info):
        bc = BatchCorrection()
        with pytest.raises(ValueError, match="Unknown batch correction method"):
            bc.correct_batch_effects(
                batched_expression, batch_info, method="does_not_exist"
            )
        assert bc.corrected_data is None

    def test_underlying_failure_is_logged_and_reraised(self):
        bc = BatchCorrection()
        # The batch series must be indexed by the SAME labels as the frame's
        # columns, otherwise selection yields an empty frame and the PCA path
        # is never reached. With them aligned, _pca_correction indexes a numpy
        # array with string labels and raises IndexError, which
        # correct_batch_effects logs and re-raises.
        bad = _make_expression(int_columns=False)
        aligned = _two_batch_series(int_columns=False)
        with pytest.raises(IndexError):
            bc.correct_batch_effects(bad, aligned, method="pca")


# ---------------------------------------------------------------------------
# evaluate_correction
# ---------------------------------------------------------------------------


class TestEvaluateCorrection:
    def test_reports_improvement(self, batched_expression, batch_info):
        bc = BatchCorrection()
        corrected = bc.correct_batch_effects(
            batched_expression, batch_info, method="mean_centering"
        )
        res = bc.evaluate_correction(batched_expression, corrected, batch_info)

        assert set(res) == {
            "original_batch_effects",
            "corrected_batch_effects",
            "improvement",
            "correction_effective",
        }
        assert set(res["improvement"]) == {
            "pca_score_improvement",
            "anova_score_improvement",
            "correlation_score_improvement",
            "overall_score_improvement",
        }
        assert isinstance(res["correction_effective"], (bool, np.bool_))
        assert res["improvement"]["overall_score_improvement"] > 0
        assert res["correction_effective"] is True

    def test_no_improvement_when_data_unchanged(self, batched_expression, batch_info):
        bc = BatchCorrection()
        res = bc.evaluate_correction(
            batched_expression, batched_expression.copy(), batch_info
        )
        assert res["improvement"]["overall_score_improvement"] == pytest.approx(0.0)
        assert res["correction_effective"] is False

    def test_failure_is_logged_and_reraised(self):
        bad = _make_expression(int_columns=False)
        batches = _two_batch_series(int_columns=False)
        with pytest.raises(IndexError):
            BatchCorrection().evaluate_correction(bad, bad.copy(), batches)


# ---------------------------------------------------------------------------
# get_correction_summary
# ---------------------------------------------------------------------------


class TestCorrectionSummary:
    def test_before_any_correction(self):
        assert BatchCorrection().get_correction_summary() == {
            "status": "No correction performed"
        }

    def test_after_correction(self, batched_expression, batch_info):
        bc = BatchCorrection()
        bc.correct_batch_effects(
            batched_expression, batch_info, method="mean_centering"
        )
        summary = bc.get_correction_summary()

        assert summary["method"] == "mean_centering"
        assert summary["original_shape"] == (N_GENES, N_SAMPLES)
        assert set(summary["value_range"]) == {"min", "max", "mean", "std"}
        assert summary["value_range"]["min"] <= summary["value_range"]["mean"]
        assert summary["value_range"]["mean"] <= summary["value_range"]["max"]
        assert "mean_centering" in summary["parameters"]

    def test_method_unknown_when_params_empty(self, batched_expression):
        """corrected_data set without any recorded params -> 'unknown'."""
        bc = BatchCorrection()
        bc.corrected_data = batched_expression
        summary = bc.get_correction_summary()
        assert summary["method"] == "unknown"


# ---------------------------------------------------------------------------
# save_corrected_data
# ---------------------------------------------------------------------------


class TestSaveCorrectedData:
    @pytest.fixture
    def corrector(self, batched_expression, batch_info):
        bc = BatchCorrection()
        bc.correct_batch_effects(
            batched_expression, batch_info, method="mean_centering"
        )
        return bc

    def test_raises_without_corrected_data(self, tmp_path):
        with pytest.raises(ValueError, match="No corrected data to save"):
            BatchCorrection().save_corrected_data(str(tmp_path / "out.tsv"))

    def test_tsv_is_default(self, corrector, tmp_path):
        out = tmp_path / "out.tsv"
        returned = corrector.save_corrected_data(str(out))

        assert returned == str(out)
        assert out.exists()
        reloaded = pd.read_csv(out, sep="\t", index_col=0)
        assert reloaded.shape == (N_GENES, N_SAMPLES)

    def test_csv_format_is_case_insensitive(self, corrector, tmp_path):
        out = tmp_path / "out.csv"
        corrector.save_corrected_data(str(out), format="CSV")
        assert out.exists()
        assert pd.read_csv(out, index_col=0).shape == (N_GENES, N_SAMPLES)

    def test_h5_format(self, corrector, tmp_path, monkeypatch):
        calls = {}

        def fake_to_hdf(self, path, key=None, **kwargs):
            calls["path"] = path
            calls["key"] = key

        monkeypatch.setattr(pd.DataFrame, "to_hdf", fake_to_hdf, raising=True)
        out = tmp_path / "out.h5"
        assert corrector.save_corrected_data(str(out), format="h5") == str(out)
        assert calls == {"path": str(out), "key": "corrected_data"}

    def test_unsupported_format_raises(self, corrector, tmp_path):
        with pytest.raises(ValueError, match="Unsupported format"):
            corrector.save_corrected_data(str(tmp_path / "out.parquet"), format="xyz")

    def test_write_failure_is_logged_and_reraised(
        self, corrector, tmp_path, monkeypatch
    ):
        def boom(self, *args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(pd.DataFrame, "to_csv", boom, raising=True)
        with pytest.raises(OSError, match="disk full"):
            corrector.save_corrected_data(str(tmp_path / "out.tsv"))
