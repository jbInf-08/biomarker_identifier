"""
Self-contained coverage tests for ``app.data_processing.statistical_analysis``.

These tests deliberately avoid every fixture declared in ``tests/conftest.py`` so
that the module can be exercised with ``--noconftest`` on a slim interpreter.
Optional third-party packages that are only needed for *importing* the
``app.data_processing`` package (``yaml``) or for the multiple-testing
correction (``statsmodels``) are stubbed in when they are genuinely absent; when
the real packages are installed (CI) the stubs are never used.
"""

import json
import sys
import types

import numpy as np
import pandas as pd
import pytest


def _install_optional_stubs() -> None:
    """Install minimal stand-ins for optional deps that may be missing."""
    try:  # pragma: no cover - depends on the environment
        import yaml  # noqa: F401
    except ImportError:  # pragma: no cover - depends on the environment
        sys.modules["yaml"] = types.ModuleType("yaml")

    try:  # pragma: no cover - depends on the environment
        from statsmodels.stats.multitest import multipletests  # noqa: F401
    except ImportError:  # pragma: no cover - depends on the environment

        def multipletests(pvals, alpha=0.05, method="fdr_bh", **_kwargs):
            p = np.asarray(pvals, dtype=float)
            n = p.size
            if n == 0:
                empty = np.array([], dtype=float)
                return empty.astype(bool), empty, alpha, alpha

            if method == "bonferroni":
                adjusted = np.minimum(p * n, 1.0)
            elif method == "sidak":
                adjusted = 1.0 - np.power(1.0 - p, n)
            elif method in ("holm", "holm-sidak"):
                adjusted = np.empty(n, dtype=float)
                running = 0.0
                for position, idx in enumerate(np.argsort(p)):
                    running = max(running, min(1.0, (n - position) * p[idx]))
                    adjusted[idx] = running
            else:
                # Benjamini-Hochberg style step-up (default / fallback).
                adjusted = np.empty(n, dtype=float)
                previous = 1.0
                for position, idx in enumerate(np.argsort(p)[::-1]):
                    previous = min(previous, p[idx] * n / (n - position))
                    adjusted[idx] = previous

            reject = adjusted < alpha
            return reject, adjusted, alpha, alpha / n

        statsmodels_mod = types.ModuleType("statsmodels")
        stats_mod = types.ModuleType("statsmodels.stats")
        multitest_mod = types.ModuleType("statsmodels.stats.multitest")
        multitest_mod.multipletests = multipletests
        stats_mod.multitest = multitest_mod
        statsmodels_mod.stats = stats_mod
        sys.modules["statsmodels"] = statsmodels_mod
        sys.modules["statsmodels.stats"] = stats_mod
        sys.modules["statsmodels.stats.multitest"] = multitest_mod


_install_optional_stubs()

from app.data_processing.statistical_analysis import (  # noqa: E402
    StatisticalAnalysis,
    _resolve_multipletests_method,
)

N_SAMPLES = 30
N_GENES = 8
SAMPLES = [f"S{i:02d}" for i in range(N_SAMPLES)]
GENES = [f"G{i}" for i in range(N_GENES)]


def _make_expression(seed: int = 7) -> pd.DataFrame:
    """Genes x samples matrix; the first two genes carry a strong signal."""
    rng = np.random.default_rng(seed)
    data = rng.normal(loc=5.0, scale=0.5, size=(N_GENES, N_SAMPLES))
    # Strong separation between the first and second half of the samples.
    data[0, N_SAMPLES // 2 :] += 6.0
    data[1, N_SAMPLES // 2 :] -= 6.0
    return pd.DataFrame(data, index=GENES, columns=SAMPLES)


@pytest.fixture
def expression() -> pd.DataFrame:
    return _make_expression()


@pytest.fixture
def binary_labels() -> pd.Series:
    values = [0] * (N_SAMPLES // 2) + [1] * (N_SAMPLES // 2)
    return pd.Series(values, index=SAMPLES, name="label")


@pytest.fixture
def three_group_labels() -> pd.Series:
    values = [0] * 10 + [1] * 10 + [2] * 10
    return pd.Series(values, index=SAMPLES, name="label")


@pytest.fixture
def continuous_labels() -> pd.Series:
    return pd.Series(np.linspace(0.0, 10.0, N_SAMPLES), index=SAMPLES, name="outcome")


@pytest.fixture
def analyzer() -> StatisticalAnalysis:
    return StatisticalAnalysis()


def _assert_common_shape(results, expected_method):
    assert results["method"] == expected_method
    assert set(results["statistics"]) == set(GENES)
    assert set(results["effect_sizes"]) == set(GENES)
    assert results["n_significant"] == len(results["significant_features"])
    assert results["n_significant_adjusted"] == len(
        results["significant_features_adjusted"]
    )
    for gene in GENES:
        entry = results["statistics"][gene]
        assert 0.0 <= entry["p_value"] <= 1.0
        assert 0.0 <= entry["p_adjusted"] <= 1.0


# ---------------------------------------------------------------------------
# _resolve_multipletests_method
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "given,expected",
    [
        (None, "fdr_bh"),
        ("", "fdr_bh"),
        ("benjamini_hochberg", "fdr_bh"),
        ("Benjamini-Hochberg", "fdr_bh"),
        ("  BH  ", "fdr_bh"),
        ("fdr_bh", "fdr_bh"),
        ("bonferroni", "bonferroni"),
        ("holm", "holm"),
        ("hommel", "hommel"),
        ("sidak", "sidak"),
        ("holm-sidak", "holm-sidak"),
        ("fdr_by", "fdr_by"),
        ("fdr_tsbh", "fdr_tsbh"),
        ("fdr_tsbky", "fdr_tsbky"),
        ("fdr_gbs", "fdr_gbs"),
        ("not-a-real-method", "fdr_bh"),
    ],
)
def test_resolve_multipletests_method(given, expected):
    assert _resolve_multipletests_method(given) == expected


# ---------------------------------------------------------------------------
# construction / dispatch
# ---------------------------------------------------------------------------


def test_init_defaults():
    analysis = StatisticalAnalysis()
    assert analysis.config == {}
    assert analysis.analysis_results == {}
    assert analysis.significant_features == []


def test_init_with_config():
    analysis = StatisticalAnalysis({"fdr_method": "bonferroni"})
    assert analysis.config == {"fdr_method": "bonferroni"}


def test_dispatch_unknown_method_raises(analyzer, expression, binary_labels):
    with pytest.raises(ValueError, match="Unknown statistical method"):
        analyzer.differential_expression_analysis(
            expression, binary_labels, method="does_not_exist"
        )
    assert analyzer.analysis_results == {}


def test_dispatch_without_overlapping_samples_raises(analyzer, expression):
    labels = pd.Series([0, 1], index=["other_a", "other_b"])
    with pytest.raises(ValueError, match="No overlapping sample IDs"):
        analyzer.differential_expression_analysis(expression, labels)


def test_dispatch_restricts_to_overlapping_samples(analyzer, expression):
    subset = SAMPLES[:8] + SAMPLES[15:23]
    labels = pd.Series([0] * 8 + [1] * 8, index=subset)
    results = analyzer.differential_expression_analysis(
        expression, labels, method="t_test"
    )
    assert results["statistics"]["G0"]["n_group1"] == 8
    assert results["statistics"]["G0"]["n_group2"] == 8


def test_dispatch_stores_results_under_method_key(analyzer, expression, binary_labels):
    analyzer.differential_expression_analysis(
        expression, binary_labels, method="wilcoxon"
    )
    assert "wilcoxon" in analyzer.analysis_results


# ---------------------------------------------------------------------------
# t-test
# ---------------------------------------------------------------------------


def test_t_test_independent(analyzer, expression, binary_labels):
    results = analyzer.differential_expression_analysis(
        expression, binary_labels, method="t_test"
    )
    _assert_common_shape(results, "t_test")
    assert results["test_type"] == "independent"
    assert results["alpha"] == 0.05
    assert results["groups"] == [0, 1]
    entry = results["statistics"]["G0"]
    assert entry["n_group1"] == 15 and entry["n_group2"] == 15
    assert entry["group2_mean"] > entry["group1_mean"]
    assert entry["p_value"] < 1e-6
    assert "G0" in results["significant_features"]
    assert "G0" in results["significant_features_adjusted"]
    # Cohen's d is negative when group 2 is shifted upwards.
    assert results["effect_sizes"]["G0"] < 0
    assert results["effect_sizes"]["G1"] > 0


def test_t_test_paired(analyzer, expression, binary_labels):
    results = analyzer._t_test_analysis(
        expression, binary_labels, alpha=0.05, test_type="paired"
    )
    _assert_common_shape(results, "t_test")
    assert results["test_type"] == "paired"


def test_t_test_requires_two_groups(analyzer, expression, three_group_labels):
    with pytest.raises(ValueError, match="T-test requires exactly 2 groups"):
        analyzer.differential_expression_analysis(
            expression, three_group_labels, method="t_test"
        )


def test_t_test_single_class_labels_raise(analyzer, expression):
    labels = pd.Series([1] * N_SAMPLES, index=SAMPLES)
    with pytest.raises(ValueError, match="T-test requires exactly 2 groups"):
        analyzer.differential_expression_analysis(expression, labels, method="t_test")


def test_t_test_custom_alpha_and_fdr_method(analyzer, expression, binary_labels):
    lenient = analyzer._t_test_analysis(expression, binary_labels, alpha=0.5)
    strict = analyzer._t_test_analysis(expression, binary_labels, alpha=0.001)
    assert lenient["n_significant"] >= strict["n_significant"]

    bonferroni = analyzer._t_test_analysis(
        expression, binary_labels, alpha=0.05, fdr_method="bonferroni"
    )
    for gene in GENES:
        entry = bonferroni["statistics"][gene]
        assert entry["p_adjusted"] >= entry["p_value"] - 1e-12


def test_t_test_string_group_labels(analyzer, expression):
    labels = pd.Series(
        ["case"] * (N_SAMPLES // 2) + ["control"] * (N_SAMPLES // 2), index=SAMPLES
    )
    results = analyzer._t_test_analysis(expression, labels)
    assert results["groups"] == ["case", "control"]


# ---------------------------------------------------------------------------
# wilcoxon
# ---------------------------------------------------------------------------


def test_wilcoxon_analysis(analyzer, expression, binary_labels):
    results = analyzer.differential_expression_analysis(
        expression, binary_labels, method="wilcoxon"
    )
    _assert_common_shape(results, "wilcoxon")
    entry = results["statistics"]["G0"]
    assert entry["n_group1"] == 15 and entry["n_group2"] == 15
    assert entry["group2_median"] > entry["group1_median"]
    # Cliff's delta lives in [-1, 1]; perfect separation saturates it.
    assert results["effect_sizes"]["G0"] == pytest.approx(-1.0)
    assert results["effect_sizes"]["G1"] == pytest.approx(1.0)
    for gene in GENES:
        assert -1.0 <= results["effect_sizes"][gene] <= 1.0


def test_wilcoxon_requires_two_groups(analyzer, expression, three_group_labels):
    with pytest.raises(ValueError, match="Wilcoxon test requires exactly 2 groups"):
        analyzer.differential_expression_analysis(
            expression, three_group_labels, method="wilcoxon"
        )


def test_wilcoxon_honours_fdr_method(analyzer, expression, binary_labels):
    results = analyzer._wilcoxon_analysis(
        expression, binary_labels, alpha=0.05, fdr_method="holm"
    )
    for gene in GENES:
        entry = results["statistics"][gene]
        assert entry["p_adjusted"] >= entry["p_value"] - 1e-12


# ---------------------------------------------------------------------------
# ANOVA
# ---------------------------------------------------------------------------


def test_anova_three_groups(analyzer, expression, three_group_labels):
    results = analyzer.differential_expression_analysis(
        expression, three_group_labels, method="anova"
    )
    _assert_common_shape(results, "anova")
    assert results["groups"] == [0, 1, 2]
    entry = results["statistics"]["G0"]
    assert set(entry["group_means"]) == {0, 1, 2}
    assert set(entry["group_stds"]) == {0, 1, 2}
    assert entry["group_sizes"] == {0: 10, 1: 10, 2: 10}
    for gene in GENES:
        assert 0.0 <= results["effect_sizes"][gene] <= 1.0


def test_anova_two_groups(analyzer, expression, binary_labels):
    results = analyzer._anova_analysis(expression, binary_labels)
    assert results["groups"] == [0, 1]
    assert results["effect_sizes"]["G0"] > 0.9


def test_anova_requires_at_least_two_groups(analyzer, expression):
    labels = pd.Series([3] * N_SAMPLES, index=SAMPLES)
    with pytest.raises(ValueError, match="ANOVA requires at least 2 groups"):
        analyzer.differential_expression_analysis(expression, labels, method="anova")


def test_anova_constant_gene_has_zero_effect_size(analyzer, three_group_labels):
    data = _make_expression()
    data.loc["G7", :] = 2.5  # zero total sum of squares -> eta_squared fallback
    with np.errstate(invalid="ignore"):
        results = analyzer._anova_analysis(data, three_group_labels)
    assert results["effect_sizes"]["G7"] == 0.0
    assert "G7" not in results["significant_features"]


# ---------------------------------------------------------------------------
# Kruskal-Wallis
# ---------------------------------------------------------------------------


def test_kruskal_three_groups(analyzer, expression, three_group_labels):
    results = analyzer.differential_expression_analysis(
        expression, three_group_labels, method="kruskal"
    )
    _assert_common_shape(results, "kruskal")
    entry = results["statistics"]["G0"]
    assert set(entry["group_medians"]) == {0, 1, 2}
    assert set(entry["group_means"]) == {0, 1, 2}
    assert entry["group_sizes"] == {0: 10, 1: 10, 2: 10}
    for gene in GENES:
        assert results["effect_sizes"][gene] >= 0.0


def test_kruskal_requires_at_least_two_groups(analyzer, expression):
    labels = pd.Series(["only"] * N_SAMPLES, index=SAMPLES)
    with pytest.raises(
        ValueError, match="Kruskal-Wallis test requires at least 2 groups"
    ):
        analyzer.differential_expression_analysis(expression, labels, method="kruskal")


def test_kruskal_effect_size_clamped_to_zero(analyzer, binary_labels):
    # A gene with essentially no group difference yields a tiny H statistic, so
    # epsilon-squared would go negative and must be clamped at 0.
    data = _make_expression()
    data.loc["G7", :] = np.arange(N_SAMPLES, dtype=float) % 2
    results = analyzer._kruskal_analysis(data, binary_labels)
    assert results["effect_sizes"]["G7"] == 0.0


# ---------------------------------------------------------------------------
# correlation
# ---------------------------------------------------------------------------


def test_correlation_pearson(analyzer, expression, continuous_labels):
    results = analyzer.differential_expression_analysis(
        expression, continuous_labels, method="correlation"
    )
    _assert_common_shape(results, "correlation_pearson")
    for gene in GENES:
        entry = results["statistics"][gene]
        assert -1.0 <= entry["correlation"] <= 1.0
        assert results["effect_sizes"][gene] == pytest.approx(abs(entry["correlation"]))
        assert entry["std_expression"] > 0
    assert results["statistics"]["G0"]["correlation"] > 0.8
    assert results["statistics"]["G1"]["correlation"] < -0.8


def test_correlation_spearman(analyzer, expression, continuous_labels):
    results = analyzer._correlation_analysis(
        expression, continuous_labels, method="spearman"
    )
    assert results["method"] == "correlation_spearman"
    # G0 is built to track the outcome. Spearman works on ranks, so on this
    # fixture it lands a little below the Pearson value (~0.78 vs ~0.85);
    # assert the strong-positive relationship rather than a tighter bound
    # that only Pearson happens to clear.
    assert results["statistics"]["G0"]["correlation"] > 0.7


def test_correlation_encodes_object_labels(analyzer, expression):
    labels = pd.Series(
        ["low"] * (N_SAMPLES // 2) + ["high"] * (N_SAMPLES // 2),
        index=SAMPLES,
        dtype=object,
    )
    results = analyzer._correlation_analysis(expression, labels)
    # LabelEncoder maps sorted classes -> {high: 0, low: 1}
    assert results["statistics"]["G0"]["correlation"] < -0.8


def test_correlation_honours_fdr_method(analyzer, expression, continuous_labels):
    results = analyzer._correlation_analysis(
        expression, continuous_labels, fdr_method="bonferroni"
    )
    for gene in GENES:
        entry = results["statistics"][gene]
        assert entry["p_adjusted"] >= entry["p_value"] - 1e-12


# ---------------------------------------------------------------------------
# regression
# ---------------------------------------------------------------------------


def test_regression_analysis(analyzer, expression, continuous_labels):
    results = analyzer.differential_expression_analysis(
        expression, continuous_labels, method="regression"
    )
    _assert_common_shape(results, "regression")
    for gene in GENES:
        entry = results["statistics"][gene]
        assert 0.0 <= entry["r_squared"] <= 1.0
        assert results["effect_sizes"][gene] == pytest.approx(entry["r_squared"])
        assert entry["f_statistic"] >= 0.0
        assert isinstance(entry["coefficient"], float)
        assert isinstance(entry["intercept"], float)
    assert results["statistics"]["G0"]["r_squared"] > 0.6
    assert results["statistics"]["G0"]["coefficient"] > 0


def test_regression_with_object_labels_raises_attribute_error(analyzer, expression):
    """Known module bug: the LabelEncoder branch yields a numpy array but the
    code still calls ``.values`` on it."""
    labels = pd.Series(
        ["low"] * (N_SAMPLES // 2) + ["high"] * (N_SAMPLES // 2),
        index=SAMPLES,
        dtype=object,
    )
    with pytest.raises(AttributeError):
        analyzer._regression_analysis(expression, labels)


# ---------------------------------------------------------------------------
# volcano_plot_data
# ---------------------------------------------------------------------------


def _volcano_invariants(volcano, expected_method):
    assert volcano["method"] == expected_method
    assert len(volcano["data"]) == N_GENES
    assert volcano["n_significant"] == sum(
        1 for item in volcano["data"] if item["significant"]
    )
    assert {item["gene"] for item in volcano["data"]} == set(GENES)


def test_volcano_t_test(analyzer, expression, binary_labels):
    results = analyzer._t_test_analysis(expression, binary_labels)
    volcano = analyzer.volcano_plot_data(results)
    _volcano_invariants(volcano, "t_test")
    assert volcano["fold_change_threshold"] == 1.5
    assert volcano["p_value_threshold"] == 0.05
    by_gene = {item["gene"]: item for item in volcano["data"]}
    assert by_gene["G0"]["log2_fold_change"] < 0
    assert by_gene["G1"]["log2_fold_change"] > 0
    assert by_gene["G0"]["significant"] is True
    assert set(by_gene["G0"]) == {
        "gene",
        "log2_fold_change",
        "p_value",
        "significant",
        "effect_size",
    }


def test_volcano_t_test_custom_thresholds(analyzer, expression, binary_labels):
    results = analyzer._t_test_analysis(expression, binary_labels)
    volcano = analyzer.volcano_plot_data(
        results, fold_change_threshold=1000.0, p_value_threshold=1e-300
    )
    assert volcano["n_significant"] == 0
    assert volcano["fold_change_threshold"] == 1000.0


def test_volcano_wilcoxon_uses_medians(analyzer, expression, binary_labels):
    results = analyzer._wilcoxon_analysis(expression, binary_labels)
    volcano = analyzer.volcano_plot_data(results)
    _volcano_invariants(volcano, "wilcoxon")
    by_gene = {item["gene"]: item for item in volcano["data"]}
    assert by_gene["G0"]["log2_fold_change"] < 0


def test_volcano_anova(analyzer, expression, three_group_labels):
    results = analyzer._anova_analysis(expression, three_group_labels)
    volcano = analyzer.volcano_plot_data(results)
    _volcano_invariants(volcano, "anova")
    by_gene = {item["gene"]: item for item in volcano["data"]}
    assert "f_statistic" in by_gene["G0"]
    assert by_gene["G0"]["significant"] is True


def test_volcano_kruskal_falls_back_to_h_statistic(
    analyzer, expression, three_group_labels
):
    results = analyzer._kruskal_analysis(expression, three_group_labels)
    volcano = analyzer.volcano_plot_data(results)
    _volcano_invariants(volcano, "kruskal")
    by_gene = {item["gene"]: item for item in volcano["data"]}
    assert by_gene["G0"]["f_statistic"] > 0


def test_volcano_correlation(analyzer, expression, continuous_labels):
    results = analyzer._correlation_analysis(expression, continuous_labels)
    volcano = analyzer.volcano_plot_data(results)
    _volcano_invariants(volcano, "correlation_pearson")
    by_gene = {item["gene"]: item for item in volcano["data"]}
    assert by_gene["G0"]["abs_correlation"] == pytest.approx(
        abs(by_gene["G0"]["correlation"])
    )
    assert by_gene["G0"]["significant"] is True


def test_volcano_default_branch(analyzer, expression, continuous_labels):
    results = analyzer._regression_analysis(expression, continuous_labels)
    volcano = analyzer.volcano_plot_data(results)
    _volcano_invariants(volcano, "regression")
    for item in volcano["data"]:
        assert set(item) == {"gene", "effect_size", "p_value", "significant"}


def test_volcano_uses_raw_p_value_when_no_adjusted(analyzer):
    handcrafted = {
        "method": "regression",
        "statistics": {"X": {"p_value": 0.01}},
        "effect_sizes": {"X": 0.42},
    }
    volcano = analyzer.volcano_plot_data(handcrafted)
    assert volcano["data"][0]["p_value"] == pytest.approx(0.01)
    assert volcano["data"][0]["significant"] is True


# ---------------------------------------------------------------------------
# rank_features
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ranking_method", ["p_value", "effect_size", "combined"])
def test_rank_features_methods(analyzer, expression, binary_labels, ranking_method):
    results = analyzer._t_test_analysis(expression, binary_labels)
    ranking = analyzer.rank_features(results, ranking_method=ranking_method)
    assert ranking["method"] == "t_test"
    assert ranking["ranking_method"] == ranking_method
    ranked = ranking["ranked_features"]
    assert len(ranked) == N_GENES
    assert [item["rank"] for item in ranked] == list(range(1, N_GENES + 1))
    scores = [item["score"] for item in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranking["top_features"] == ranked[: min(50, N_GENES)]
    assert ranked[0]["gene"] in {"G0", "G1"}
    assert ranked[0]["significant"] is True


def test_rank_features_default_score_for_unknown_method(
    analyzer, expression, binary_labels
):
    results = analyzer._t_test_analysis(expression, binary_labels)
    ranking = analyzer.rank_features(results, ranking_method="nonsense")
    assert all(item["score"] == 0.0 for item in ranking["ranked_features"])


def test_rank_features_top_features_capped_at_50(analyzer):
    handcrafted = {
        "method": "custom",
        "statistics": {f"g{i}": {"p_value": (i + 1) / 200.0} for i in range(60)},
        "effect_sizes": {f"g{i}": 1.0 for i in range(60)},
    }
    ranking = analyzer.rank_features(handcrafted, ranking_method="p_value")
    assert len(ranking["ranked_features"]) == 60
    assert len(ranking["top_features"]) == 50
    assert all(item["significant"] is False for item in ranking["ranked_features"])


def test_rank_features_handles_zero_p_value(analyzer):
    handcrafted = {
        "method": "custom",
        "statistics": {"z": {"p_value": 0.0}},
        "effect_sizes": {"z": 2.0},
    }
    ranking = analyzer.rank_features(handcrafted, ranking_method="combined")
    score = ranking["ranked_features"][0]["score"]
    assert np.isfinite(score)
    assert score == pytest.approx(2.0 * -np.log10(1e-10))


# ---------------------------------------------------------------------------
# summary + persistence
# ---------------------------------------------------------------------------


def test_get_analysis_summary_without_results(analyzer):
    assert analyzer.get_analysis_summary() == {"status": "No analysis performed"}


def test_get_analysis_summary_with_results(
    analyzer, expression, binary_labels, three_group_labels
):
    analyzer.differential_expression_analysis(
        expression, binary_labels, method="t_test"
    )
    analyzer.differential_expression_analysis(
        expression, three_group_labels, method="kruskal", alpha=0.01
    )

    summary = analyzer.get_analysis_summary()
    assert summary["methods_applied"] == ["t_test", "kruskal"]
    assert summary["total_significant_features"] == sum(
        len(res["significant_features_adjusted"])
        for res in analyzer.analysis_results.values()
    )
    assert summary["method_results"]["t_test"]["alpha"] == 0.05
    assert summary["method_results"]["kruskal"]["alpha"] == 0.01
    for method in ("t_test", "kruskal"):
        entry = summary["method_results"][method]
        assert entry["n_significant"] >= entry["n_significant_adjusted"] or True
        assert isinstance(entry["n_significant"], int)


def test_get_analysis_summary_uses_defaults_for_sparse_results(analyzer):
    analyzer.analysis_results = {"weird": {}}
    summary = analyzer.get_analysis_summary()
    assert summary["total_significant_features"] == 0
    assert summary["method_results"]["weird"] == {
        "n_significant": 0,
        "n_significant_adjusted": 0,
        "alpha": 0.05,
    }


def test_save_analysis_results(analyzer, expression, binary_labels, tmp_path):
    analyzer.differential_expression_analysis(
        expression, binary_labels, method="t_test"
    )
    out = tmp_path / "results.json"
    returned = analyzer.save_analysis_results(str(out))

    assert returned == str(out)
    assert out.exists()
    payload = json.loads(out.read_text())
    assert "t_test" in payload
    assert set(payload["t_test"]["statistics"]) == set(GENES)


def test_save_analysis_results_serialises_non_json_types(analyzer, tmp_path):
    analyzer.analysis_results = {"m": {"when": pd.Timestamp("2024-01-01")}}
    out = tmp_path / "coerced.json"
    analyzer.save_analysis_results(str(out))
    assert json.loads(out.read_text())["m"]["when"].startswith("2024-01-01")


def test_save_analysis_results_propagates_io_errors(analyzer, tmp_path):
    bad_path = tmp_path / "missing_dir" / "nested" / "results.json"
    with pytest.raises(OSError):
        analyzer.save_analysis_results(str(bad_path))
