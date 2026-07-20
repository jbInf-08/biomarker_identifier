"""
Self-contained coverage tests for app.data_processing.data_transformation.

These tests deliberately avoid every fixture from tests/conftest.py so the file
can be run with --noconftest.
"""

import importlib.util
import sys
import types

import numpy as np
import pandas as pd
import pytest


def _stub_plotly_if_missing():
    """app.data_processing.__init__ imports quality_control, which needs plotly.

    plotly is only required by sibling modules, not by data_transformation
    itself. Register a stub *only* when plotly is genuinely unavailable so a
    real installation (e.g. in CI) is never shadowed.
    """
    if importlib.util.find_spec("plotly") is not None:
        return
    plotly = types.ModuleType("plotly")
    express = types.ModuleType("plotly.express")
    graph_objects = types.ModuleType("plotly.graph_objects")
    subplots = types.ModuleType("plotly.subplots")
    subplots.make_subplots = lambda *a, **k: None
    plotly.express = express
    plotly.graph_objects = graph_objects
    plotly.subplots = subplots
    sys.modules.setdefault("plotly", plotly)
    sys.modules.setdefault("plotly.express", express)
    sys.modules.setdefault("plotly.graph_objects", graph_objects)
    sys.modules.setdefault("plotly.subplots", subplots)


_stub_plotly_if_missing()

from app.data_processing.data_transformation import DataTransformation  # noqa: E402

N_GENES = 20
N_SAMPLES = 12


def _make_expression(seed: int = 0, n_genes: int = N_GENES, n_samples: int = N_SAMPLES):
    """Strictly positive expression matrix (genes x samples)."""
    rng = np.random.default_rng(seed)
    values = rng.lognormal(mean=2.0, sigma=0.5, size=(n_genes, n_samples))
    return pd.DataFrame(
        values,
        index=[f"GENE_{i}" for i in range(n_genes)],
        columns=[f"S{j}" for j in range(n_samples)],
    )


@pytest.fixture
def expression():
    return _make_expression()


@pytest.fixture
def transformer():
    return DataTransformation()


# ---------------------------------------------------------------- constructor


def test_init_defaults():
    dt = DataTransformation()
    assert dt.config == {}
    assert dt.transformation_params == {}
    assert dt.transformed_data is None


def test_init_with_config():
    cfg = {"a": 1}
    dt = DataTransformation(config=cfg)
    assert dt.config is cfg


# ------------------------------------------------------------ simple methods


def test_log2_transform(transformer, expression):
    out = transformer.transform_data(expression, method="log2")
    assert out.shape == expression.shape
    expected = np.log2(expression.iloc[0, 0] + 1.0)
    assert out.iloc[0, 0] == pytest.approx(expected)
    assert transformer.transformation_params["log2"] == {
        "method": "log2",
        "prior_count": 1.0,
    }
    assert transformer.transformed_data is out


def test_log2_transform_custom_prior_count(transformer, expression):
    out = transformer.transform_data(expression, method="log2", prior_count=5.0)
    assert out.iloc[0, 0] == pytest.approx(np.log2(expression.iloc[0, 0] + 5.0))
    assert transformer.transformation_params["log2"]["prior_count"] == 5.0


def test_log10_transform(transformer, expression):
    out = transformer.transform_data(expression, method="log10", prior_count=2.0)
    assert out.iloc[0, 0] == pytest.approx(np.log10(expression.iloc[0, 0] + 2.0))
    assert transformer.transformation_params["log10"] == {
        "method": "log10",
        "prior_count": 2.0,
    }


def test_sqrt_transform(transformer, expression):
    out = transformer.transform_data(expression, method="sqrt")
    assert out.iloc[0, 0] == pytest.approx(np.sqrt(expression.iloc[0, 0]))
    assert transformer.transformation_params["sqrt"] == {"method": "sqrt"}


# -------------------------------------------------------------- power / rank


def test_box_cox_transform_yeo_johnson_default(transformer, expression):
    out = transformer.transform_data(expression, method="box_cox")
    assert isinstance(out, pd.DataFrame)
    assert out.shape == expression.shape
    assert list(out.index) == list(expression.index)
    assert list(out.columns) == list(expression.columns)
    params = transformer.transformation_params["box_cox"]
    assert params["transformer_method"] == "yeo-johnson"
    assert len(params["lambdas"]) == expression.shape[0]


def test_box_cox_transform_true_box_cox_branch(transformer, expression):
    out = transformer._box_cox_transform(expression, method="box-cox")
    assert out.shape == expression.shape
    assert transformer.transformation_params["box_cox"]["transformer_method"] == (
        "box-cox"
    )


def test_yeo_johnson_transform_delegates(transformer, expression):
    out = transformer.transform_data(expression, method="yeo_johnson")
    assert out.shape == expression.shape
    # _yeo_johnson_transform delegates to _box_cox_transform, so params land
    # under the "box_cox" key.
    assert "box_cox" in transformer.transformation_params


def test_quantile_transform_uniform(transformer, expression):
    out = transformer.transform_data(expression, method="quantile")
    assert out.shape == expression.shape
    assert out.values.min() >= 0.0
    assert out.values.max() <= 1.0
    params = transformer.transformation_params["quantile"]
    assert params["output_distribution"] == "uniform"
    assert params["n_quantiles"] == 1000
    assert isinstance(params["quantiles"], list)


def test_quantile_transform_normal_output(transformer, expression):
    out = transformer.transform_data(
        expression, method="quantile", output_distribution="normal", n_quantiles=5
    )
    assert out.shape == expression.shape
    assert transformer.transformation_params["quantile"]["output_distribution"] == (
        "normal"
    )
    assert transformer.transformation_params["quantile"]["n_quantiles"] == 5


def test_rank_transform_default(transformer, expression):
    out = transformer.transform_data(expression, method="rank")
    assert out.shape == expression.shape
    row = out.loc["GENE_0"].astype(float)
    assert sorted(row.tolist()) == [float(i) for i in range(1, N_SAMPLES + 1)]
    assert transformer.transformation_params["rank"]["ranking_method"] == "average"


def test_rank_transform_dense_method(transformer, expression):
    out = transformer._rank_transform(expression, method="dense")
    assert out.shape == expression.shape
    assert transformer.transformation_params["rank"]["ranking_method"] == "dense"


# ------------------------------------------------------------------ z-scores


def test_z_score_transform(transformer, expression):
    out = transformer.transform_data(expression, method="z_score")
    assert out.shape == expression.shape
    assert out.loc["GENE_0"].mean() == pytest.approx(0.0, abs=1e-9)
    assert out.loc["GENE_0"].std() == pytest.approx(1.0, abs=1e-9)
    params = transformer.transformation_params["z_score"]
    assert set(params["gene_means"]) == set(expression.index)
    assert set(params["gene_stds"]) == set(expression.index)


def test_robust_z_score_transform_raises_on_pandas_2(transformer, expression):
    """DataFrame.mad() was removed in pandas 2.0 -> this path always errors.

    Asserting the *current* behaviour rather than the intended behaviour.
    """
    with pytest.raises(AttributeError):
        transformer.transform_data(expression, method="robust_z_score")


# -------------------------------------------------------------------- custom


def test_custom_transform(transformer, expression):
    def scale(df, factor=2.0):
        return df * factor

    out = transformer.transform_data(
        expression, method="custom", transform_func=scale, factor=3.0
    )
    assert out.iloc[0, 0] == pytest.approx(expression.iloc[0, 0] * 3.0)
    params = transformer.transformation_params["custom"]
    assert params["method"] == "custom"
    assert params["kwargs"] == {"factor": 3.0}
    assert "scale" in params["transform_func"]


def test_custom_transform_missing_func_raises(transformer, expression):
    with pytest.raises(TypeError):
        transformer.transform_data(expression, method="custom")


# ------------------------------------------------------------- error handling


def test_unknown_method_raises(transformer, expression):
    with pytest.raises(ValueError, match="Unknown transformation method: bogus"):
        transformer.transform_data(expression, method="bogus")
    assert transformer.transformed_data is None


def test_transform_propagates_inner_exception(transformer, expression):
    def boom(df):
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError, match="kaboom"):
        transformer.transform_data(expression, method="custom", transform_func=boom)


# ------------------------------------------------------------- edge case data


def test_transform_single_gene(transformer):
    single = _make_expression(seed=1, n_genes=1, n_samples=8)
    out = transformer.transform_data(single, method="log2")
    assert out.shape == (1, 8)


def test_transform_empty_dataframe(transformer):
    empty = pd.DataFrame()
    out = transformer.transform_data(empty, method="log2")
    assert out.empty


def test_log2_with_nans_propagates_nan(transformer):
    data = _make_expression(seed=2)
    data.iloc[0, 0] = np.nan
    out = transformer.transform_data(data, method="log2")
    assert np.isnan(out.iloc[0, 0])


def test_sqrt_of_negative_yields_nan(transformer):
    data = _make_expression(seed=3)
    data.iloc[1, 1] = -4.0
    with np.errstate(invalid="ignore"):
        out = transformer.transform_data(data, method="sqrt")
    assert np.isnan(out.iloc[1, 1])


# --------------------------------------------------------- normality scoring


def test_calculate_normality_scores_structure(transformer, expression):
    np.random.seed(42)
    scores = transformer._calculate_normality_scores(expression)
    expected_keys = {
        "overall_score",
        "mean_skewness",
        "mean_kurtosis",
        "mean_shapiro_p",
        "skewness_score",
        "kurtosis_score",
        "shapiro_score",
    }
    assert set(scores) == expected_keys
    assert 0.0 <= scores["overall_score"] <= 1.0
    assert 0.0 <= scores["skewness_score"] <= 1.0
    assert 0.0 <= scores["kurtosis_score"] <= 1.0


def test_calculate_normality_scores_shapiro_failure_path(
    transformer, expression, monkeypatch
):
    """The bare `except:` around stats.shapiro appends 0.0 p-values."""
    import app.data_processing.data_transformation as mod

    def broken_shapiro(_data):
        raise ValueError("shapiro failed")

    monkeypatch.setattr(mod.stats, "shapiro", broken_shapiro)
    np.random.seed(7)
    scores = transformer._calculate_normality_scores(expression)
    assert scores["mean_shapiro_p"] == 0.0
    assert scores["shapiro_score"] == 0.0


def test_normality_scores_clamp_to_zero(transformer):
    """Extremely skewed / heavy-tailed data drives the max(0, ...) clamps."""
    rng = np.random.default_rng(11)
    values = rng.lognormal(mean=0.0, sigma=4.0, size=(6, 15))
    data = pd.DataFrame(
        values,
        index=[f"G{i}" for i in range(6)],
        columns=[f"S{j}" for j in range(15)],
    )
    np.random.seed(3)
    scores = transformer._calculate_normality_scores(data)
    assert scores["skewness_score"] >= 0.0
    assert scores["kurtosis_score"] >= 0.0


# ------------------------------------------------------ detect_best_transform


def test_detect_best_transformation_default_methods(transformer, expression):
    np.random.seed(0)
    result = transformer.detect_best_transformation(expression)
    assert set(result) == {"best_method", "best_score", "all_results"}
    assert set(result["all_results"]) == {
        "log2",
        "sqrt",
        "box_cox",
        "quantile",
        "rank",
    }
    assert result["best_method"] in result["all_results"]
    assert 0.0 <= result["best_score"] <= 1.0
    for entry in result["all_results"].values():
        assert set(entry) == {
            "normality_score",
            "skewness",
            "kurtosis",
            "shapiro_wilk",
        }
    # state is reset after each method
    assert transformer.transformed_data is None
    assert transformer.transformation_params == {}


def test_detect_best_transformation_explicit_methods(transformer, expression):
    np.random.seed(1)
    result = transformer.detect_best_transformation(expression, methods=["log2"])
    assert list(result["all_results"]) == ["log2"]
    assert result["best_method"] == "log2"


def test_detect_best_transformation_all_methods_fail(transformer, expression):
    result = transformer.detect_best_transformation(
        expression, methods=["nope", "robust_z_score"]
    )
    assert result["best_method"] is None
    assert result["best_score"] == 0
    assert "error" in result["all_results"]["nope"]
    assert "error" in result["all_results"]["robust_z_score"]


def test_detect_best_transformation_mixed_success_and_failure(transformer, expression):
    np.random.seed(5)
    result = transformer.detect_best_transformation(
        expression, methods=["log2", "nope"]
    )
    assert result["best_method"] == "log2"
    assert "error" in result["all_results"]["nope"]


# ------------------------------------------------------ compare_transformations


def test_compare_transformations_default_methods(transformer, expression):
    results = transformer.compare_transformations(expression)
    assert set(results) == {
        "log2",
        "sqrt",
        "box_cox",
        "quantile",
        "rank",
        "z_score",
    }
    for stats_summary in results.values():
        assert set(stats_summary) == {
            "basic_stats",
            "distribution_stats",
            "missing_stats",
        }
    assert transformer.transformed_data is None
    assert transformer.transformation_params == {}


def test_compare_transformations_records_errors(transformer, expression):
    results = transformer.compare_transformations(
        expression, methods=["log2", "robust_z_score", "unknown_method"]
    )
    assert "error" not in results["log2"]
    assert "error" in results["robust_z_score"]
    assert "error" in results["unknown_method"]


def test_calculate_transformation_stats_values(transformer):
    data = pd.DataFrame(
        [[1.0, 2.0, 3.0, 4.0], [-1.0, 0.0, np.nan, 5.0], [2.0, 2.0, 2.0, 2.0]],
        index=["a", "b", "c"],
        columns=["s1", "s2", "s3", "s4"],
    )
    out = transformer._calculate_transformation_stats(data)
    assert out["basic_stats"]["min"] == pytest.approx(-1.0)
    assert out["basic_stats"]["max"] == pytest.approx(5.0)
    assert isinstance(out["basic_stats"]["mean"], float)
    assert isinstance(out["basic_stats"]["median"], float)
    assert isinstance(out["basic_stats"]["std"], float)
    assert out["missing_stats"]["missing_values"] == 1
    assert out["missing_stats"]["infinite_values"] == 0
    assert out["missing_stats"]["negative_values"] == 1
    assert set(out["distribution_stats"]) == {
        "mean_skewness",
        "std_skewness",
        "mean_kurtosis",
        "std_kurtosis",
    }


def test_calculate_transformation_stats_counts_infinities(transformer):
    data = pd.DataFrame(
        [[1.0, np.inf, 3.0, 4.0], [1.0, 2.0, -np.inf, 4.0]],
        index=["a", "b"],
        columns=["s1", "s2", "s3", "s4"],
    )
    out = transformer._calculate_transformation_stats(data)
    assert out["missing_stats"]["infinite_values"] == 2


# --------------------------------------------------------------- summary


def test_get_transformation_summary_before_transform(transformer):
    assert transformer.get_transformation_summary() == {
        "status": "No transformation performed"
    }


def test_get_transformation_summary_after_transform(transformer, expression):
    transformer.transform_data(expression, method="log2")
    summary = transformer.get_transformation_summary()
    assert summary["method"] == "log2"
    assert summary["transformed_shape"] == (N_GENES, N_SAMPLES)
    assert set(summary["value_range"]) == {"min", "max", "mean", "std"}
    assert summary["value_range"]["min"] <= summary["value_range"]["max"]
    assert "log2" in summary["parameters"]


def test_get_transformation_summary_unknown_method(transformer, expression):
    transformer.transformed_data = expression
    transformer.transformation_params = {}
    summary = transformer.get_transformation_summary()
    assert summary["method"] == "unknown"


# ------------------------------------------------------------------- saving


def test_save_without_transform_raises(transformer, tmp_path):
    with pytest.raises(ValueError, match="No transformed data to save"):
        transformer.save_transformed_data(str(tmp_path / "out.tsv"))


def test_save_tsv(transformer, expression, tmp_path):
    transformer.transform_data(expression, method="log2")
    target = tmp_path / "out.tsv"
    returned = transformer.save_transformed_data(str(target))
    assert returned == str(target)
    assert target.exists()
    reloaded = pd.read_csv(target, sep="\t", index_col=0)
    assert reloaded.shape == expression.shape


def test_save_csv_case_insensitive_format(transformer, expression, tmp_path):
    transformer.transform_data(expression, method="log2")
    target = tmp_path / "out.csv"
    transformer.save_transformed_data(str(target), format="CSV")
    reloaded = pd.read_csv(target, index_col=0)
    assert reloaded.shape == expression.shape


def test_save_h5_branch(transformer, expression, tmp_path, monkeypatch):
    """pytables is not a project dependency, so to_hdf is stubbed out."""
    transformer.transform_data(expression, method="log2")
    calls = {}

    def fake_to_hdf(self, path_or_buf, key=None, **kwargs):
        calls["path"] = path_or_buf
        calls["key"] = key

    monkeypatch.setattr(pd.DataFrame, "to_hdf", fake_to_hdf, raising=True)
    target = tmp_path / "out.h5"
    returned = transformer.save_transformed_data(str(target), format="h5")
    assert returned == str(target)
    assert calls == {"path": str(target), "key": "transformed_data"}


def test_save_unsupported_format_raises(transformer, expression, tmp_path):
    transformer.transform_data(expression, method="log2")
    with pytest.raises(ValueError, match="Unsupported format: parquet"):
        transformer.save_transformed_data(
            str(tmp_path / "out.parquet"), format="parquet"
        )


def test_save_io_error_is_logged_and_reraised(transformer, expression, monkeypatch):
    transformer.transform_data(expression, method="log2")

    def boom(self, *args, **kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr(pd.DataFrame, "to_csv", boom, raising=True)
    with pytest.raises(OSError, match="disk on fire"):
        transformer.save_transformed_data("whatever.tsv")
