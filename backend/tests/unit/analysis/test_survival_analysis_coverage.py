"""
Self-contained coverage tests for ``app.analysis.survival_analysis``.

These tests intentionally avoid every fixture from ``tests/conftest.py`` so the
module can be exercised with ``--noconftest`` locally while still running fine
in CI. All randomness is seeded and every filesystem write goes to ``tmp_path``.
"""

from unittest.mock import MagicMock, patch

import matplotlib
import numpy as np
import pandas as pd
import pytest

from app.analysis import survival_analysis as sa_module
from app.analysis.survival_analysis import SurvivalAnalyzer, main

# Headless plotting: the module under test imports pyplot at import time, so
# force the backend afterwards to keep plot tests from opening a GUI window.
matplotlib.use("Agg", force=True)

TIME_COL = "overall_survival_time"
EVENT_COL = "overall_survival_event"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def make_survival_frame(n=40, n_genes=3, seed=7, index=None):
    """Build a small, deterministic survival DataFrame."""
    rng = np.random.default_rng(seed)
    data = {
        TIME_COL: rng.exponential(scale=500, size=n) + 1.0,
        EVENT_COL: rng.binomial(1, 0.7, size=n),
        "age": rng.normal(65, 10, size=n),
    }
    for i in range(n_genes):
        data[f"GENE_{i:03d}"] = rng.normal(0, 1, size=n)
    frame = pd.DataFrame(data)
    if index is not None:
        frame.index = index
    return frame


@pytest.fixture
def survival_frame():
    return make_survival_frame()


@pytest.fixture
def analyzer(survival_frame):
    obj = SurvivalAnalyzer()
    obj.survival_data = survival_frame
    return obj


def write_clinical_csv(tmp_path, frame, name="clinical.csv"):
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return str(path)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_defaults():
    obj = SurvivalAnalyzer()
    assert obj.config == {}
    assert obj.survival_data is None
    assert obj.cox_results == {}
    assert obj.km_results == {}


def test_init_with_config():
    obj = SurvivalAnalyzer(config={"penalizer": 0.5})
    assert obj.config == {"penalizer": 0.5}


# ---------------------------------------------------------------------------
# load_survival_data
# ---------------------------------------------------------------------------


def test_load_survival_data_happy_path(tmp_path, survival_frame):
    path = write_clinical_csv(tmp_path, survival_frame)
    obj = SurvivalAnalyzer()

    loaded = obj.load_survival_data(path)

    assert isinstance(loaded, pd.DataFrame)
    assert TIME_COL in loaded.columns and EVENT_COL in loaded.columns
    assert (loaded[TIME_COL] > 0).all()
    assert loaded[EVENT_COL].dtype.kind in "iu"
    assert obj.survival_data is loaded


def test_load_survival_data_drops_nan_and_nonpositive_times(tmp_path):
    frame = make_survival_frame(n=12)
    frame.loc[0, TIME_COL] = np.nan
    frame.loc[1, TIME_COL] = -5.0
    frame.loc[2, TIME_COL] = 0.0
    path = write_clinical_csv(tmp_path, frame)

    loaded = SurvivalAnalyzer().load_survival_data(path)

    # Three rows removed: one NaN, one negative, one zero.
    assert len(loaded) == 9


def test_load_survival_data_non_numeric_time_coerced(tmp_path):
    frame = make_survival_frame(n=10)
    frame[TIME_COL] = frame[TIME_COL].astype(object)
    frame.loc[0, TIME_COL] = "not-a-number"
    path = write_clinical_csv(tmp_path, frame)

    loaded = SurvivalAnalyzer().load_survival_data(path)

    assert len(loaded) == 9


def test_load_survival_data_missing_time_column_raises(tmp_path, survival_frame):
    path = write_clinical_csv(tmp_path, survival_frame.drop(columns=[TIME_COL]))

    with pytest.raises(ValueError, match="Time column"):
        SurvivalAnalyzer().load_survival_data(path)


def test_load_survival_data_missing_event_column_raises(tmp_path, survival_frame):
    path = write_clinical_csv(tmp_path, survival_frame.drop(columns=[EVENT_COL]))

    with pytest.raises(ValueError, match="Event column"):
        SurvivalAnalyzer().load_survival_data(path)


def test_load_survival_data_read_failure_propagates(tmp_path):
    missing = str(tmp_path / "does_not_exist.csv")

    with pytest.raises(FileNotFoundError):
        SurvivalAnalyzer().load_survival_data(missing)


def test_load_survival_data_with_expression_no_common_samples(tmp_path, survival_frame):
    clinical_path = write_clinical_csv(tmp_path, survival_frame)
    expression = pd.DataFrame(
        np.arange(6).reshape(2, 3).astype(float),
        index=["GENE_X", "GENE_Y"],
        columns=["SAMPLE_A", "SAMPLE_B", "SAMPLE_C"],
    )
    expr_path = tmp_path / "expression.csv"
    expression.to_csv(expr_path)

    obj = SurvivalAnalyzer()
    loaded = obj.load_survival_data(clinical_path, expression_file=str(expr_path))

    # Warning branch taken: expression columns are not merged in.
    assert "GENE_X" not in loaded.columns


def test_load_survival_data_with_expression_common_samples(tmp_path):
    samples = [f"S{i}" for i in range(12)]
    clinical = make_survival_frame(n=12, index=samples)
    expression = pd.DataFrame(
        np.linspace(0, 1, 24).reshape(2, 12),
        index=["EXPR_A", "EXPR_B"],
        columns=samples,
    )

    frames = [clinical, expression]

    def fake_read_csv(*args, **kwargs):
        return frames.pop(0).copy()

    obj = SurvivalAnalyzer()
    with patch.object(sa_module.pd, "read_csv", side_effect=fake_read_csv):
        loaded = obj.load_survival_data("clinical.csv", expression_file="expr.csv")

    assert "EXPR_A" in loaded.columns
    assert "EXPR_B" in loaded.columns
    assert len(loaded) == 12


# ---------------------------------------------------------------------------
# prepare_survival_data
# ---------------------------------------------------------------------------


def test_prepare_survival_data_without_data_raises():
    with pytest.raises(ValueError, match="No survival data loaded"):
        SurvivalAnalyzer().prepare_survival_data()


def test_prepare_survival_data_no_covariates(analyzer):
    prepared = analyzer.prepare_survival_data()

    assert list(prepared.columns) == [TIME_COL, EVENT_COL]
    assert len(prepared) == 40


def test_prepare_survival_data_standardizes_covariates(analyzer):
    prepared = analyzer.prepare_survival_data(covariates=["age", "GENE_000"])

    assert set(prepared.columns) == {TIME_COL, EVENT_COL, "age", "GENE_000"}
    # StandardScaler output: mean ~0, population std ~1.
    assert prepared["age"].mean() == pytest.approx(0.0, abs=1e-9)
    assert prepared["age"].std(ddof=0) == pytest.approx(1.0, abs=1e-9)


def test_prepare_survival_data_ignores_unknown_covariates(analyzer):
    prepared = analyzer.prepare_survival_data(covariates=["nope_not_here"])

    assert list(prepared.columns) == [TIME_COL, EVENT_COL]


def test_prepare_survival_data_drops_missing_rows(survival_frame):
    frame = survival_frame.copy()
    frame.loc[frame.index[0], "age"] = np.nan
    obj = SurvivalAnalyzer()
    obj.survival_data = frame

    prepared = obj.prepare_survival_data(covariates=["age"])

    assert len(prepared) == len(frame) - 1


def test_prepare_survival_data_failure_is_logged_and_reraised(analyzer):
    with patch.object(
        sa_module, "StandardScaler", side_effect=RuntimeError("scaler boom")
    ):
        with pytest.raises(RuntimeError, match="scaler boom"):
            analyzer.prepare_survival_data(covariates=["age"])


# ---------------------------------------------------------------------------
# cox_proportional_hazards
# ---------------------------------------------------------------------------


def test_cox_proportional_hazards_with_covariates(analyzer):
    results = analyzer.cox_proportional_hazards(covariates=["age", "GENE_000"])

    assert set(results["covariates"]) == {"age", "GENE_000"}
    assert results["penalizer"] == pytest.approx(0.1)
    assert results["n_samples"] == 40
    assert 0.0 <= results["concordance_index"] <= 1.0
    assert isinstance(results["summary"], pd.DataFrame)
    assert set(results["hazard_ratios"]) == {"age", "GENE_000"}
    assert isinstance(results["significant_covariates"], list)
    assert analyzer.cox_results["main"] is results


def test_cox_proportional_hazards_without_covariates_skips_hazard_ratios(analyzer):
    results = analyzer.cox_proportional_hazards()

    assert results["covariates"] == []
    assert "hazard_ratios" not in results
    assert "significant_covariates" not in results
    assert results["concordance_index"] == pytest.approx(0.5)


def test_cox_proportional_hazards_custom_penalizer(analyzer):
    results = analyzer.cox_proportional_hazards(covariates=["age"], penalizer=0.9)

    assert results["penalizer"] == pytest.approx(0.9)


def test_cox_proportional_hazards_without_data_raises():
    with pytest.raises(ValueError, match="No survival data loaded"):
        SurvivalAnalyzer().cox_proportional_hazards()


def test_cox_proportional_hazards_fit_failure_reraises(analyzer):
    failing = MagicMock()
    failing.fit.side_effect = RuntimeError("cox fit boom")
    with patch.object(sa_module, "CoxPHFitter", return_value=failing):
        with pytest.raises(RuntimeError, match="cox fit boom"):
            analyzer.cox_proportional_hazards(covariates=["age"])


# ---------------------------------------------------------------------------
# univariate_cox_analysis
# ---------------------------------------------------------------------------


def test_univariate_cox_without_data_raises():
    with pytest.raises(ValueError, match="No survival data loaded"):
        SurvivalAnalyzer().univariate_cox_analysis()


def test_univariate_cox_autodetects_gene_columns(analyzer):
    results = analyzer.univariate_cox_analysis()

    assert not results.empty
    # age + 3 genes are auto-detected as "gene" columns.
    assert set(results["gene"]) == {"age", "GENE_000", "GENE_001", "GENE_002"}
    for col in (
        "coef",
        "exp_coef",
        "se_coef",
        "p_value",
        "lower_ci",
        "upper_ci",
        "concordance_index",
        "n_samples",
        "n_events",
        "significant",
        "highly_significant",
        "hazard_interpretation",
    ):
        assert col in results.columns
    # Sorted ascending by p-value.
    assert results["p_value"].is_monotonic_increasing
    assert set(results["hazard_interpretation"]) <= {"Protective", "Risk", "Neutral"}


def test_univariate_cox_skips_clinical_prefixed_columns(survival_frame):
    frame = survival_frame.copy()
    frame["clinical_stage"] = 1.0
    obj = SurvivalAnalyzer()
    obj.survival_data = frame

    results = obj.univariate_cox_analysis()

    assert "clinical_stage" not in set(results["gene"])


def test_univariate_cox_explicit_gene_list(analyzer):
    results = analyzer.univariate_cox_analysis(gene_columns=["GENE_000"])

    assert list(results["gene"]) == ["GENE_000"]


def test_univariate_cox_unknown_gene_is_skipped(analyzer):
    results = analyzer.univariate_cox_analysis(gene_columns=["GENE_000", "MISSING"])

    assert list(results["gene"]) == ["GENE_000"]


def test_univariate_cox_empty_gene_list_returns_empty_frame(analyzer):
    results = analyzer.univariate_cox_analysis(gene_columns=[])

    assert results.empty
    assert "significant" not in results.columns


def test_univariate_cox_skips_when_too_few_samples():
    frame = make_survival_frame(n=6)
    obj = SurvivalAnalyzer()
    obj.survival_data = frame

    results = obj.univariate_cox_analysis(gene_columns=["GENE_000"])

    # Fewer than 10 usable rows -> the gene is skipped entirely.
    assert results.empty


def test_univariate_cox_per_gene_failure_is_swallowed(analyzer):
    failing = MagicMock()
    failing.fit.side_effect = RuntimeError("per-gene boom")
    with patch.object(sa_module, "CoxPHFitter", return_value=failing):
        results = analyzer.univariate_cox_analysis(gene_columns=["GENE_000"])

    assert results.empty


def test_univariate_cox_outer_failure_reraises(analyzer):
    with patch.object(
        sa_module.pd, "DataFrame", side_effect=RuntimeError("frame boom")
    ):
        with pytest.raises(RuntimeError, match="frame boom"):
            analyzer.univariate_cox_analysis(gene_columns=[])


# ---------------------------------------------------------------------------
# kaplan_meier_analysis
# ---------------------------------------------------------------------------


def test_kaplan_meier_without_data_raises():
    with pytest.raises(ValueError, match="No survival data loaded"):
        SurvivalAnalyzer().kaplan_meier_analysis()


def test_kaplan_meier_auto_median_split(analyzer):
    results = analyzer.kaplan_meier_analysis(group_column="GENE_000")

    assert {"Low", "High"} <= set(results)
    for name in ("Low", "High"):
        group = results[name]
        assert group["n_samples"] > 0
        assert 0.0 <= group["survival_at_1yr"] <= 1.0
        assert 0.0 <= group["survival_at_5yr"] <= 1.0
        assert group["n_events"] >= 0
    assert "logrank_test" in results
    assert 0.0 <= results["logrank_test"]["p_value"] <= 1.0
    assert results["logrank_test"]["degrees_of_freedom"] == 1
    assert analyzer.km_results["main"] is results


def test_kaplan_meier_missing_group_column_raises(analyzer):
    with pytest.raises(ValueError, match="Group column 'nope' not found"):
        analyzer.kaplan_meier_analysis(group_column="nope")


def test_kaplan_meier_explicit_groups(analyzer):
    ages = analyzer.survival_data["age"]
    groups = {"Young": ages <= ages.median(), "Old": ages > ages.median()}

    results = analyzer.kaplan_meier_analysis(groups=groups)

    assert {"Young", "Old", "logrank_test"} == set(results)


def test_kaplan_meier_small_group_is_skipped(analyzer):
    mask = pd.Series(False, index=analyzer.survival_data.index)
    mask.iloc[:3] = True
    groups = {"Tiny": mask, "Rest": ~mask}

    results = analyzer.kaplan_meier_analysis(groups=groups)

    assert "Tiny" not in results
    assert "Rest" in results
    # Only one surviving group -> no log-rank test.
    assert "logrank_test" not in results


def test_kaplan_meier_group_fit_failure_is_swallowed(analyzer):
    ages = analyzer.survival_data["age"]
    groups = {"Young": ages <= ages.median(), "Old": ages > ages.median()}
    failing = MagicMock()
    failing.fit.side_effect = RuntimeError("km boom")

    with patch.object(sa_module, "KaplanMeierFitter", return_value=failing):
        results = analyzer.kaplan_meier_analysis(groups=groups)

    assert results == {}


def test_kaplan_meier_logrank_failure_is_swallowed(analyzer):
    ages = analyzer.survival_data["age"]
    groups = {"Young": ages <= ages.median(), "Old": ages > ages.median()}

    with patch.object(
        sa_module,
        "multivariate_logrank_test",
        side_effect=RuntimeError("logrank boom"),
    ):
        results = analyzer.kaplan_meier_analysis(groups=groups)

    assert {"Young", "Old"} == set(results)
    assert "logrank_test" not in results


def test_kaplan_meier_outer_failure_reraises():
    obj = SurvivalAnalyzer()
    # Missing the time/event columns entirely -> the outer handler re-raises.
    obj.survival_data = pd.DataFrame({"a": [1, 2, 3]})

    with pytest.raises(KeyError):
        obj.kaplan_meier_analysis()


# ---------------------------------------------------------------------------
# create_survival_plots
# ---------------------------------------------------------------------------


def test_create_survival_plots_km_and_cox(tmp_path, analyzer):
    analyzer.kaplan_meier_analysis(group_column="GENE_000")
    analyzer.cox_proportional_hazards(covariates=["age", "GENE_000"])

    out_dir = tmp_path / "plots"
    analyzer.create_survival_plots(str(out_dir))

    assert (out_dir / "kaplan_meier_curves.png").exists()
    assert (out_dir / "cox_forest_plot.png").exists()


def test_create_survival_plots_km_without_logrank(tmp_path, analyzer):
    mask = pd.Series(False, index=analyzer.survival_data.index)
    mask.iloc[:3] = True
    analyzer.kaplan_meier_analysis(groups={"Tiny": mask, "Rest": ~mask})

    out_dir = tmp_path / "plots_no_logrank"
    analyzer.create_survival_plots(str(out_dir))

    assert (out_dir / "kaplan_meier_curves.png").exists()
    assert not (out_dir / "cox_forest_plot.png").exists()


def test_create_survival_plots_with_no_results_creates_only_dir(tmp_path):
    out_dir = tmp_path / "empty_plots"
    SurvivalAnalyzer().create_survival_plots(str(out_dir))

    assert out_dir.is_dir()
    assert list(out_dir.iterdir()) == []


def test_create_survival_plots_skips_empty_cox_summary(tmp_path, analyzer):
    analyzer.cox_results["main"] = {"summary": pd.DataFrame()}

    out_dir = tmp_path / "empty_summary"
    analyzer.create_survival_plots(str(out_dir))

    assert not (out_dir / "cox_forest_plot.png").exists()


def test_create_survival_plots_swallows_exceptions(tmp_path, analyzer):
    # A malformed km_results entry makes plotting blow up; the method must not raise.
    analyzer.km_results["main"] = {"Bad": {"kmf": object()}}

    out_dir = tmp_path / "broken_plots"
    analyzer.create_survival_plots(str(out_dir))

    assert not (out_dir / "kaplan_meier_curves.png").exists()


# ---------------------------------------------------------------------------
# survival_biomarker_discovery
# ---------------------------------------------------------------------------


def test_survival_biomarker_discovery_happy_path(analyzer):
    univariate = pd.DataFrame(
        {
            "gene": ["G1", "G2", "G3"],
            "p_value": [0.001, 0.02, 0.5],
            "concordance_index": [0.8, 0.7, 0.5],
            "exp_coef": [1.9, 0.4, 1.0],
            "significant": [True, True, False],
            "hazard_interpretation": ["Risk", "Protective", "Neutral"],
        }
    )

    with patch.object(analyzer, "univariate_cox_analysis", return_value=univariate):
        top = analyzer.survival_biomarker_discovery()

    assert list(top["gene"]) == ["G1", "G2"]
    assert list(top["biomarker_type"]) == ["Prognostic", "Prognostic"]
    assert top["effect_size"].tolist() == pytest.approx([0.9, 0.6])


def test_survival_biomarker_discovery_respects_top_n(analyzer):
    univariate = pd.DataFrame(
        {
            "gene": ["G1", "G2"],
            "p_value": [0.001, 0.002],
            "concordance_index": [0.8, 0.7],
            "exp_coef": [1.5, 1.4],
            "significant": [True, True],
            "hazard_interpretation": ["Risk", "Risk"],
        }
    )

    with patch.object(analyzer, "univariate_cox_analysis", return_value=univariate):
        top = analyzer.survival_biomarker_discovery(top_n=1)

    assert len(top) == 1


def test_survival_biomarker_discovery_no_significant_genes(analyzer):
    univariate = pd.DataFrame(
        {
            "gene": ["G1"],
            "p_value": [0.9],
            "concordance_index": [0.5],
            "exp_coef": [1.0],
            "significant": [False],
            "hazard_interpretation": ["Neutral"],
        }
    )

    with patch.object(analyzer, "univariate_cox_analysis", return_value=univariate):
        top = analyzer.survival_biomarker_discovery()

    assert top.empty


def test_survival_biomarker_discovery_empty_univariate_returns_empty(analyzer):
    top = analyzer.survival_biomarker_discovery(gene_columns=[])

    assert isinstance(top, pd.DataFrame)
    assert top.empty


def test_survival_biomarker_discovery_end_to_end(analyzer):
    top = analyzer.survival_biomarker_discovery(top_n=2)

    assert isinstance(top, pd.DataFrame)
    if not top.empty:
        assert "biomarker_type" in top.columns
        assert "effect_size" in top.columns


def test_survival_biomarker_discovery_failure_reraises():
    with pytest.raises(ValueError, match="No survival data loaded"):
        SurvivalAnalyzer().survival_biomarker_discovery()


# ---------------------------------------------------------------------------
# get_survival_summary
# ---------------------------------------------------------------------------


def test_get_survival_summary_empty_analyzer():
    summary = SurvivalAnalyzer().get_survival_summary()

    assert summary["survival_data_loaded"] is False
    assert summary["cox_analyses_performed"] == 0
    assert summary["km_analyses_performed"] == 0
    assert "analysis_timestamp" in summary
    assert "n_samples" not in summary


def test_get_survival_summary_with_data_only(analyzer):
    summary = analyzer.get_survival_summary()

    assert summary["survival_data_loaded"] is True
    assert summary["n_samples"] == 40
    assert summary["n_events"] >= 0
    assert "cox_concordance_index" not in summary


def test_get_survival_summary_with_cox_and_km(analyzer):
    analyzer.cox_proportional_hazards(covariates=["age"])
    analyzer.kaplan_meier_analysis(group_column="GENE_000")

    summary = analyzer.get_survival_summary()

    assert summary["cox_analyses_performed"] == 1
    assert summary["km_analyses_performed"] == 1
    assert summary["cox_n_samples"] == 40
    assert summary["cox_concordance_index"] is not None
    assert summary["km_groups"] == 2
    assert 0.0 <= summary["logrank_p_value"] <= 1.0


def test_get_survival_summary_km_without_logrank(analyzer):
    analyzer.km_results["main"] = {"OnlyGroup": {"n_samples": 5}}

    summary = analyzer.get_survival_summary()

    assert summary["km_groups"] == 1
    assert "logrank_p_value" not in summary


def test_get_survival_summary_failure_reraises(analyzer):
    with patch.object(sa_module, "datetime") as fake_datetime:
        fake_datetime.now.side_effect = RuntimeError("clock boom")
        with pytest.raises(RuntimeError, match="clock boom"):
            analyzer.get_survival_summary()


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_runs_end_to_end(capsys):
    main()

    out = capsys.readouterr().out
    assert "Cox analysis C-index" in out
    assert "Survival analysis test completed successfully!" in out


def test_main_failure_reraises():
    with patch.object(
        SurvivalAnalyzer,
        "cox_proportional_hazards",
        side_effect=RuntimeError("main boom"),
    ):
        with pytest.raises(RuntimeError, match="main boom"):
            main()
