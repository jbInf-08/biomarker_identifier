"""Self-contained coverage tests for app.data_processing.multi_omics.

These tests deliberately avoid every fixture in tests/conftest.py so the file can
run with ``--noconftest``.  All data is generated in-process with fixed seeds and
all filesystem writes go to ``tmp_path``.
"""

import importlib.util
import os
import sys
import types

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_local.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("MPLBACKEND", "Agg")

# isort: split
import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")


def _stub_plotly_if_absent():
    """``app.data_processing.__init__`` imports plotly transitively.

    plotly is not part of the pinned test dependencies, so register a minimal
    stub when (and only when) it is genuinely unavailable.  With plotly
    installed this is a no-op.
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


_stub_plotly_if_absent()

# isort: split
from app.data_processing.multi_omics import MultiOmicsProcessor, main

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

N_FEATURES = 12
N_SAMPLES = 8


def _samples(n=N_SAMPLES, prefix="SAMPLE"):
    return [f"{prefix}_{i:03d}" for i in range(n)]


def _frame(n_rows=N_FEATURES, n_cols=N_SAMPLES, prefix="FEAT", seed=0, kind="normal"):
    rng = np.random.default_rng(seed)
    if kind == "normal":
        values = rng.normal(0.0, 1.0, size=(n_rows, n_cols))
    elif kind == "positive":
        values = rng.lognormal(mean=3.0, sigma=0.5, size=(n_rows, n_cols))
    elif kind == "beta":
        values = rng.beta(2, 2, size=(n_rows, n_cols))
    elif kind == "big":
        values = rng.uniform(1e5, 1e7, size=(n_rows, n_cols))
    else:  # pragma: no cover - defensive
        raise AssertionError(kind)
    return pd.DataFrame(
        values,
        index=[f"{prefix}_{i:03d}" for i in range(n_rows)],
        columns=_samples(n_cols),
    )


def _write(df, path, sep=","):
    df.to_csv(path, sep=sep)
    return str(path)


@pytest.fixture
def processor():
    return MultiOmicsProcessor()


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    import matplotlib.pyplot as plt

    plt.close("all")


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_defaults():
    p = MultiOmicsProcessor()
    assert p.config == {}
    assert p.processed_data == {}
    assert p.integration_results == {}


def test_init_with_config():
    cfg = {"a": 1}
    p = MultiOmicsProcessor(config=cfg)
    assert p.config is cfg


# ---------------------------------------------------------------------------
# load_expression_data
# ---------------------------------------------------------------------------


def test_load_expression_csv(processor, tmp_path):
    df = _frame(kind="positive", seed=1)
    path = _write(df, tmp_path / "expr.csv")

    out = processor.load_expression_data(path)

    assert out.shape == df.shape
    assert list(out.columns) == list(df.columns)
    assert processor.processed_data["expression"] is out


def test_load_expression_tsv_txt(processor, tmp_path):
    df = _frame(kind="positive", seed=2)
    path = _write(df, tmp_path / "expr.txt", sep="\t")

    out = processor.load_expression_data(path)

    assert out.shape == df.shape
    assert np.allclose(out.values, df.values)


def test_load_expression_drops_all_zero_rows(processor, tmp_path):
    df = _frame(kind="positive", seed=3)
    df.iloc[0, :] = 0.0
    path = _write(df, tmp_path / "expr.csv")

    out = processor.load_expression_data(path)

    assert out.shape[0] == df.shape[0] - 1
    assert df.index[0] not in out.index


def test_load_expression_unsupported_suffix(processor, tmp_path):
    bad = tmp_path / "expr.xlsx"
    bad.write_bytes(b"nope")

    with pytest.raises(ValueError, match="Unsupported file format"):
        processor.load_expression_data(str(bad))


def test_load_expression_missing_file(processor, tmp_path):
    with pytest.raises(OSError):
        processor.load_expression_data(str(tmp_path / "nope.csv"))


# ---------------------------------------------------------------------------
# load_methylation_data
# ---------------------------------------------------------------------------


def test_load_methylation_filters_low_variance(processor, tmp_path):
    df = _frame(n_rows=6, kind="beta", prefix="PROBE", seed=4)
    # give one probe a huge variance so it survives the > 0.3 variance filter
    df.iloc[0, :] = np.linspace(-10, 10, df.shape[1])
    path = _write(df, tmp_path / "meth.csv")

    out = processor.load_methylation_data(path)

    assert list(out.index) == [df.index[0]]
    assert processor.processed_data["methylation"] is out


def test_load_methylation_custom_threshold_keeps_all(processor, tmp_path):
    df = _frame(n_rows=5, kind="beta", prefix="PROBE", seed=5)
    path = _write(df, tmp_path / "meth.txt", sep="\t")

    out = processor.load_methylation_data(path, beta_threshold=-1.0)

    assert out.shape == df.shape


def test_load_methylation_drops_nan_rows(processor, tmp_path):
    df = _frame(n_rows=4, kind="beta", prefix="PROBE", seed=6)
    df.iloc[0, :] = np.linspace(-10, 10, df.shape[1])
    df.iloc[1, :] = np.linspace(-10, 10, df.shape[1])
    df.iloc[1, 0] = np.nan
    path = _write(df, tmp_path / "meth.csv")

    out = processor.load_methylation_data(path)

    assert list(out.index) == [df.index[0]]


def test_load_methylation_unsupported_suffix(processor, tmp_path):
    bad = tmp_path / "meth.parquet"
    bad.write_bytes(b"nope")
    with pytest.raises(ValueError, match="Unsupported file format"):
        processor.load_methylation_data(str(bad))


def test_load_methylation_missing_file(processor, tmp_path):
    with pytest.raises(OSError):
        processor.load_methylation_data(str(tmp_path / "missing.csv"))


# ---------------------------------------------------------------------------
# load_copy_number_data
# ---------------------------------------------------------------------------


def test_load_copy_number_filters_low_variance(processor, tmp_path):
    df = _frame(n_rows=6, prefix="SEG", seed=7) * 0.01
    df.iloc[0, :] = np.linspace(-5, 5, df.shape[1])
    path = _write(df, tmp_path / "cnv.csv")

    out = processor.load_copy_number_data(path)

    assert list(out.index) == [df.index[0]]
    assert processor.processed_data["copy_number"] is out


def test_load_copy_number_tab_separated(processor, tmp_path):
    df = _frame(n_rows=5, prefix="SEG", seed=8)
    path = _write(df, tmp_path / "cnv.txt", sep="\t")

    out = processor.load_copy_number_data(path, cnv_threshold=-1.0)

    assert out.shape == df.shape


def test_load_copy_number_unsupported_suffix(processor, tmp_path):
    bad = tmp_path / "cnv.h5"
    bad.write_bytes(b"nope")
    with pytest.raises(ValueError, match="Unsupported file format"):
        processor.load_copy_number_data(str(bad))


def test_load_copy_number_missing_file(processor, tmp_path):
    with pytest.raises(OSError):
        processor.load_copy_number_data(str(tmp_path / "missing.csv"))


# ---------------------------------------------------------------------------
# load_proteomics_data
# ---------------------------------------------------------------------------


def test_load_proteomics_filters_and_log2(processor, tmp_path):
    df = _frame(n_rows=4, prefix="PROT", kind="big", seed=9)
    df.iloc[0, :] = 10.0  # below the 1e5 intensity threshold -> dropped
    path = _write(df, tmp_path / "prot.csv")

    out = processor.load_proteomics_data(path)

    assert df.index[0] not in out.index
    assert out.shape[0] == 3
    # values are log2(x + 1) of the originals
    expected = np.log2(df.loc[out.index].values + 1)
    assert np.allclose(out.values, expected)
    assert processor.processed_data["proteomics"] is out


def test_load_proteomics_custom_threshold_tab(processor, tmp_path):
    df = _frame(n_rows=4, prefix="PROT", kind="positive", seed=10)
    path = _write(df, tmp_path / "prot.txt", sep="\t")

    out = processor.load_proteomics_data(path, intensity_threshold=0.0)

    assert out.shape == df.shape


def test_load_proteomics_unsupported_suffix(processor, tmp_path):
    bad = tmp_path / "prot.xls"
    bad.write_bytes(b"nope")
    with pytest.raises(ValueError, match="Unsupported file format"):
        processor.load_proteomics_data(str(bad))


def test_load_proteomics_missing_file(processor, tmp_path):
    with pytest.raises(OSError):
        processor.load_proteomics_data(str(tmp_path / "missing.csv"))


# ---------------------------------------------------------------------------
# normalize_omics_data
# ---------------------------------------------------------------------------


def test_normalize_missing_data_type(processor):
    with pytest.raises(ValueError, match="No expression data loaded"):
        processor.normalize_omics_data("expression")


def test_normalize_quantile(processor):
    # quantile path needs n_cols <= n_rows so percentiles stay within [0, 100]
    processor.processed_data["expression"] = _frame(
        n_rows=10, n_cols=5, kind="positive", seed=11
    )

    out = processor.normalize_omics_data("expression", method="quantile")

    assert out.shape == (10, 5)
    assert processor.processed_data["expression_normalized"] is out
    assert np.isfinite(out.values).all()


def test_normalize_zscore(processor):
    processor.processed_data["expression"] = _frame(seed=12)

    out = processor.normalize_omics_data("expression", method="zscore")

    assert out.shape == (N_FEATURES, N_SAMPLES)
    # StandardScaler works column-wise -> each column has ~zero mean
    assert out.mean(axis=0).abs().max() == pytest.approx(0.0, abs=1e-9)


def test_normalize_robust(processor):
    processor.processed_data["methylation"] = _frame(kind="beta", seed=13)

    out = processor.normalize_omics_data("methylation", method="robust")

    assert out.shape == (N_FEATURES, N_SAMPLES)
    assert list(out.index) == list(processor.processed_data["methylation"].index)
    assert "methylation_normalized" in processor.processed_data


def test_normalize_log2(processor):
    data = _frame(kind="positive", seed=14)
    processor.processed_data["expression"] = data

    out = processor.normalize_omics_data("expression", method="log2")

    assert np.allclose(out.values, np.log2(data.values + 1))


def test_normalize_unknown_method(processor):
    processor.processed_data["expression"] = _frame(seed=15)
    with pytest.raises(ValueError, match="Unknown normalization method"):
        processor.normalize_omics_data("expression", method="bogus")


def test_normalize_single_row(processor):
    processor.processed_data["expression"] = _frame(n_rows=1, n_cols=1, seed=16)

    out = processor.normalize_omics_data("expression", method="zscore")

    assert out.shape == (1, 1)
    assert out.iloc[0, 0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# align_omics_data
# ---------------------------------------------------------------------------


def test_align_missing_reference(processor):
    with pytest.raises(ValueError, match="No expression data available"):
        processor.align_omics_data()


def test_align_common_samples(processor):
    expr = _frame(n_rows=6, n_cols=6, prefix="GENE", seed=17)
    meth = _frame(n_rows=6, n_cols=8, prefix="PROBE", kind="beta", seed=18)
    processor.processed_data["expression"] = expr
    processor.processed_data["methylation"] = meth

    aligned = processor.align_omics_data()

    assert set(aligned) == {"expression", "methylation"}
    assert aligned["expression"] is expr
    assert set(aligned["methylation"].columns) == set(expr.columns)
    assert processor.processed_data["aligned"] is aligned


def test_align_no_common_samples_is_skipped(processor):
    expr = _frame(n_rows=4, n_cols=4, prefix="GENE", seed=19)
    other = _frame(n_rows=4, n_cols=4, prefix="PROBE", seed=20)
    other.columns = [f"OTHER_{i}" for i in range(4)]
    processor.processed_data["expression"] = expr
    processor.processed_data["methylation"] = other

    aligned = processor.align_omics_data()

    assert set(aligned) == {"expression"}


def test_align_custom_reference(processor):
    meth = _frame(n_rows=4, n_cols=4, prefix="PROBE", seed=21)
    processor.processed_data["methylation"] = meth

    aligned = processor.align_omics_data(reference_data_type="methylation")

    assert set(aligned) == {"methylation"}


def test_align_twice_raises_because_aligned_dict_is_stored(processor):
    """Known module bug: align_omics_data stores a dict under 'aligned', so a
    second call iterates over it and blows up on ``dict.columns``."""
    processor.processed_data["expression"] = _frame(n_rows=4, n_cols=4, seed=22)
    processor.align_omics_data()

    with pytest.raises(AttributeError):
        processor.align_omics_data()


# ---------------------------------------------------------------------------
# integrate_omics_data
# ---------------------------------------------------------------------------


def _two_omics(processor, seed=30, n_rows=8, n_cols=6):
    processor.processed_data["expression"] = _frame(
        n_rows=n_rows, n_cols=n_cols, prefix="GENE", seed=seed
    )
    processor.processed_data["methylation"] = _frame(
        n_rows=n_rows, n_cols=n_cols, prefix="PROBE", kind="beta", seed=seed + 1
    )
    return processor


def test_integrate_concatenation_autoaligns(processor):
    _two_omics(processor)

    out = processor.integrate_omics_data(feature_selection=False)

    assert out.shape[0] == 16
    assert processor.integration_results["integration_method"] == "concatenation"
    assert processor.integration_results["integrated_data"] is out


def test_integrate_with_feature_selection(processor):
    _two_omics(processor, seed=32)

    out = processor.integrate_omics_data(feature_selection=True, n_features=5)

    assert out.shape[0] == 5


def test_integrate_feature_selection_more_than_available(processor):
    _two_omics(processor, seed=33)

    out = processor.integrate_omics_data(feature_selection=True, n_features=10_000)

    assert out.shape[0] == 16


def test_integrate_pca(processor):
    _two_omics(processor, seed=34, n_rows=10, n_cols=6)

    out = processor.integrate_omics_data(
        integration_method="pca", feature_selection=False
    )

    # transposed PCA components x samples
    assert out.shape[1] == 6
    assert all("_PC" in str(idx) for idx in out.index)


def test_integrate_mofa(processor):
    _two_omics(processor, seed=35)

    out = processor.integrate_omics_data(
        integration_method="mofa", feature_selection=False
    )

    assert out.shape == (16, 6)
    assert any(str(i).startswith("expression_") for i in out.index)
    assert any(str(i).startswith("methylation_") for i in out.index)


def test_integrate_unknown_method(processor):
    _two_omics(processor, seed=36)

    with pytest.raises(ValueError, match="Unknown integration method"):
        processor.integrate_omics_data(integration_method="nope")


def test_integrate_reuses_existing_aligned(processor):
    _two_omics(processor, seed=37)
    aligned = processor.align_omics_data()

    out = processor.integrate_omics_data(feature_selection=False)

    assert out.shape[0] == sum(d.shape[0] for d in aligned.values())


def test_integrate_propagates_alignment_error(processor):
    with pytest.raises(ValueError, match="No expression data available"):
        processor.integrate_omics_data()


# ---------------------------------------------------------------------------
# private helpers, exercised directly for their error branches
# ---------------------------------------------------------------------------


def test_pca_integration_direct(processor):
    aligned = {"expression": _frame(n_rows=9, n_cols=5, prefix="GENE", seed=40)}

    out = processor._pca_integration(aligned)

    assert out.shape[1] == 5
    assert out.shape[0] == min(50, 9, 5)


def test_pca_integration_error(processor):
    with pytest.raises(Exception):
        processor._pca_integration({"expression": "not-a-dataframe"})


def test_mofa_integration_error(processor):
    with pytest.raises(Exception):
        processor._mofa_integration({"expression": "not-a-dataframe"})


def test_select_integrated_features_error(processor):
    with pytest.raises(Exception):
        processor._select_integrated_features("not-a-dataframe", 3)


def test_select_integrated_features_orders_by_variance(processor):
    data = pd.DataFrame(
        [[0.0, 0.0, 0.0], [0.0, 5.0, 10.0], [0.0, 1.0, 2.0]],
        index=["flat", "wide", "mid"],
        columns=["a", "b", "c"],
    )

    out = processor._select_integrated_features(data, 2)

    assert list(out.index) == ["wide", "mid"]


# ---------------------------------------------------------------------------
# calculate_omics_correlations
# ---------------------------------------------------------------------------


def test_correlations_pair(processor):
    _two_omics(processor, seed=50)

    out = processor.calculate_omics_correlations(["expression", "methylation"])

    assert list(out.columns) == ["Data Types", "Correlation"]
    assert out.shape[0] == 1
    assert out.loc[0, "Data Types"] == "expression_methylation"
    assert -1.0 <= out.loc[0, "Correlation"] <= 1.0


def test_correlations_skips_unknown_types(processor):
    _two_omics(processor, seed=51)

    out = processor.calculate_omics_correlations(["expression", "not_loaded"])

    assert out.empty


def test_correlations_single_type_returns_empty(processor):
    processor.processed_data["expression"] = _frame(n_rows=5, n_cols=5, seed=52)

    out = processor.calculate_omics_correlations(["expression"])

    assert out.empty


def test_correlations_triggers_alignment(processor):
    _two_omics(processor, seed=53)
    assert "aligned" not in processor.processed_data

    processor.calculate_omics_correlations(["expression", "methylation"])

    assert "aligned" in processor.processed_data


def test_correlations_mismatched_shapes_raise(processor):
    processor.processed_data["expression"] = _frame(
        n_rows=8, n_cols=6, prefix="GENE", seed=54
    )
    processor.processed_data["methylation"] = _frame(
        n_rows=4, n_cols=6, prefix="PROBE", seed=55
    )

    with pytest.raises(Exception):
        processor.calculate_omics_correlations(["expression", "methylation"])


# ---------------------------------------------------------------------------
# visualize_omics_integration
# ---------------------------------------------------------------------------


def test_visualize_without_aligned_data_returns_early(processor, tmp_path):
    out_dir = tmp_path / "viz_empty"

    processor.visualize_omics_integration(str(out_dir))

    assert out_dir.exists()
    assert list(out_dir.glob("*.png")) == []


def test_visualize_single_data_type_saves_plot(processor, tmp_path):
    processor.processed_data["expression"] = _frame(n_rows=6, n_cols=5, seed=60)
    processor.align_omics_data()
    out_dir = tmp_path / "viz_one"

    processor.visualize_omics_integration(str(out_dir))

    assert (out_dir / "multi_omics_integration_overview.png").exists()


def test_visualize_with_integrated_data(processor, tmp_path):
    processor.processed_data["expression"] = _frame(n_rows=6, n_cols=5, seed=61)
    processor.align_omics_data()
    processor.integration_results["integrated_data"] = processor.processed_data[
        "expression"
    ]
    out_dir = tmp_path / "viz_int"

    processor.visualize_omics_integration(str(out_dir))

    assert (out_dir / "multi_omics_integration_overview.png").exists()


def test_visualize_multiple_data_types_is_exception_safe(processor, tmp_path):
    """The >1 data-type branch reaches the correlation heatmap; whatever pandas
    does with a pivot_table whose index and columns are the same label, the
    method must never propagate an exception."""
    _two_omics(processor, seed=62, n_rows=6, n_cols=5)
    processor.align_omics_data()
    out_dir = tmp_path / "viz_multi"

    processor.visualize_omics_integration(str(out_dir))

    assert out_dir.exists()


def test_visualize_handles_bad_aligned_payload(processor, tmp_path):
    processor.processed_data["aligned"] = {"expression": "not-a-dataframe"}
    out_dir = tmp_path / "viz_bad"

    # exception is swallowed and logged, not raised
    processor.visualize_omics_integration(str(out_dir))

    assert list(out_dir.glob("*.png")) == []


# ---------------------------------------------------------------------------
# get_integration_summary
# ---------------------------------------------------------------------------


def test_summary_empty(processor):
    summary = processor.get_integration_summary()

    assert summary["data_types_loaded"] == []
    assert summary["integration_timestamp"] is None
    assert summary["integration_method"] is None
    assert summary["integrated_data_shape"] is None
    assert summary["aligned_samples"] is None
    assert "data_types_aligned" not in summary


def test_summary_after_alignment(processor):
    _two_omics(processor, seed=70, n_rows=5, n_cols=4)
    processor.align_omics_data()

    summary = processor.get_integration_summary()

    assert summary["aligned_samples"] == 4
    assert set(summary["data_types_aligned"]) == {"expression", "methylation"}
    assert summary["integrated_data_shape"] is None


def test_summary_after_integration(processor):
    _two_omics(processor, seed=71, n_rows=5, n_cols=4)
    processor.integrate_omics_data(feature_selection=False)

    summary = processor.get_integration_summary()

    assert summary["integration_method"] == "concatenation"
    assert summary["integrated_data_shape"] == (10, 4)
    assert isinstance(summary["integration_timestamp"], str)


def test_summary_error_path(processor):
    processor.processed_data["aligned"] = {}

    with pytest.raises(Exception):
        processor.get_integration_summary()


# ---------------------------------------------------------------------------
# module-level main()
# ---------------------------------------------------------------------------


def test_main_runs(capsys):
    main()

    out = capsys.readouterr().out
    assert "Aligned data: 3 datasets" in out
    assert "Multi-omics processing test completed successfully!" in out
