"""
Self-contained unit tests for ``app.pipelines.io``.

Runs with ``--noconftest``: no fixtures from tests/conftest.py are used and all
data is built inside the tests (tmp_path for every file write).
"""

import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# --------------------------------------------------------------------------
# Environment / import bootstrap
# --------------------------------------------------------------------------
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_local.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "True")

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _install_statsmodels_stub_if_missing():
    """``app.pipelines.__init__`` imports a module chain that needs statsmodels.

    Only stub it when the real package is genuinely absent so CI (which has the
    real dependency installed) still exercises the real code path.
    """
    if importlib.util.find_spec("statsmodels") is not None:
        return

    statsmodels = types.ModuleType("statsmodels")
    stats_mod = types.ModuleType("statsmodels.stats")
    multitest_mod = types.ModuleType("statsmodels.stats.multitest")

    def multipletests(pvals, alpha=0.05, method="fdr_bh", **kwargs):
        pvals = np.asarray(pvals, dtype=float)
        adjusted = np.minimum(pvals * max(len(pvals), 1), 1.0)
        reject = adjusted < alpha
        return reject, adjusted, alpha, alpha

    multitest_mod.multipletests = multipletests
    stats_mod.multitest = multitest_mod
    statsmodels.stats = stats_mod

    sys.modules.setdefault("statsmodels", statsmodels)
    sys.modules.setdefault("statsmodels.stats", stats_mod)
    sys.modules.setdefault("statsmodels.stats.multitest", multitest_mod)


_install_statsmodels_stub_if_missing()

from app.pipelines.io import DataIO  # noqa: E402

RNG = np.random.RandomState(42)

N_GENES = 30
N_SAMPLES = 20


# --------------------------------------------------------------------------
# Helpers (plain functions, not conftest fixtures)
# --------------------------------------------------------------------------
def make_expression_df(n_genes=N_GENES, n_samples=N_SAMPLES, seed=0):
    rng = np.random.RandomState(seed)
    genes = [f"GENE{i:03d}" for i in range(n_genes)]
    samples = [f"S{i:03d}" for i in range(n_samples)]
    values = rng.rand(n_genes, n_samples) * 10 + 1
    return pd.DataFrame(values, index=genes, columns=samples)


def make_labels(samples, seed=0):
    rng = np.random.RandomState(seed)
    return pd.Series(rng.randint(0, 2, size=len(samples)), index=list(samples))


def write_expression_file(tmp_path, df, name="expr.tsv"):
    path = tmp_path / name
    sep = "," if path.suffix == ".csv" else "\t"
    df.to_csv(path, sep=sep)
    return str(path)


def write_labels_file(tmp_path, labels, name="labels.tsv"):
    path = tmp_path / name
    sep = "," if path.suffix == ".csv" else "\t"
    frame = pd.DataFrame(
        {"sample_id": list(labels.index), "class_label": list(labels.values)}
    )
    frame.to_csv(path, sep=sep, index=False)
    return str(path)


def loaded_io(seed=0):
    """A DataIO instance with expression + labels populated in memory."""
    io = DataIO()
    io.expression_data = make_expression_df(seed=seed)
    io.labels = make_labels(io.expression_data.columns, seed=seed)
    return io


def blank_results():
    return {"status": "passed", "errors": [], "warnings": [], "checks": {}}


# --------------------------------------------------------------------------
# __init__
# --------------------------------------------------------------------------
class TestInit:
    def test_default_construction(self):
        io = DataIO()
        assert io.config == {}
        assert io.expression_data is None
        assert io.labels is None
        assert io.metadata is None
        assert io.validation_results == {}

    def test_construction_with_config(self):
        cfg = {"threshold": 0.5}
        io = DataIO(config=cfg)
        assert io.config is cfg


# --------------------------------------------------------------------------
# _load_expression_data
# --------------------------------------------------------------------------
class TestLoadExpressionData:
    def test_tsv_roundtrip(self, tmp_path):
        df = make_expression_df()
        path = write_expression_file(tmp_path, df, "expr.tsv")
        out = DataIO()._load_expression_data(path)
        assert out.shape == (N_GENES, N_SAMPLES)
        assert list(out.index) == list(df.index)
        assert out.iloc[0, 0] == pytest.approx(df.iloc[0, 0])

    def test_csv_separator_detected(self, tmp_path):
        df = make_expression_df()
        path = write_expression_file(tmp_path, df, "expr.csv")
        out = DataIO()._load_expression_data(path)
        assert out.shape == (N_GENES, N_SAMPLES)

    def test_unknown_extension_defaults_to_tab(self, tmp_path):
        df = make_expression_df()
        path = tmp_path / "expr.dat"
        df.to_csv(path, sep="\t")
        out = DataIO()._load_expression_data(str(path))
        assert out.shape == (N_GENES, N_SAMPLES)

    def test_txt_extension_uses_tab(self, tmp_path):
        df = make_expression_df()
        path = tmp_path / "expr.txt"
        df.to_csv(path, sep="\t")
        out = DataIO()._load_expression_data(str(path))
        assert out.shape == (N_GENES, N_SAMPLES)

    def test_pipeline_kwargs_are_filtered_out(self, tmp_path):
        """Unknown kwargs must not reach pd.read_csv; known ones must."""
        df = make_expression_df()
        path = write_expression_file(tmp_path, df, "expr.tsv")
        out = DataIO()._load_expression_data(
            path,
            sample_column="sample_id",
            label_column="class_label",
            encoding="utf-8",
        )
        assert out.shape == (N_GENES, N_SAMPLES)

    def test_non_numeric_columns_are_coerced(self, tmp_path):
        """No numeric column survives read_csv -> to_numeric(errors='coerce')."""
        path = tmp_path / "mixed.tsv"
        path.write_text(
            "gene\tS1\tS2\tS3\n"
            "g1\t1.0\t2.0\t3.0\n"
            "g2\tabc\t5.0\t6.0\n"
            "g3\t3.0\txyz\t9.0\n",
            encoding="utf-8",
        )
        out = DataIO()._load_expression_data(str(path))
        # A column with ANY non-numeric cell is dropped entirely (not coerced to
        # NaN): only S3, which is numeric in every row, survives. S1 (has "abc")
        # and S2 (has "xyz") are removed.
        assert list(out.columns) == ["S3"]
        assert pd.api.types.is_numeric_dtype(out["S3"])
        assert out.loc["g1", "S3"] == pytest.approx(3.0)

    def test_mixed_numeric_and_text_columns_keeps_numeric_only(self, tmp_path):
        """At least one column parses as numeric -> non-numeric columns dropped."""
        path = tmp_path / "partial.tsv"
        path.write_text(
            "gene\tdescription\tS1\tS2\n"
            "g1\talpha\t1.0\t2.0\n"
            "g2\tbeta\t3.0\t4.0\n"
            "g3\tgamma\t5.0\t6.0\n",
            encoding="utf-8",
        )
        out = DataIO()._load_expression_data(str(path))
        assert list(out.columns) == ["S1", "S2"]
        assert out.shape == (3, 2)

    def test_all_non_numeric_raises_value_error(self, tmp_path):
        path = tmp_path / "bad.tsv"
        path.write_text(
            "gene\tS1\tS2\n" "g1\taa\tbb\n" "g2\tcc\tdd\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="empty after loading"):
            DataIO()._load_expression_data(str(path))

    def test_wide_matrix_is_transposed(self, tmp_path):
        """shape[0] < shape[1] means samples are rows -> transposed."""
        wide = make_expression_df(n_genes=4, n_samples=12)
        path = write_expression_file(tmp_path, wide, "wide.tsv")
        out = DataIO()._load_expression_data(path)
        assert out.shape == (12, 4)
        assert list(out.index) == list(wide.columns)

    def test_all_nan_rows_and_columns_dropped(self, tmp_path):
        path = tmp_path / "sparse.tsv"
        path.write_text(
            "gene\tS1\tS2\tS3\n"
            "g1\t1.0\t\t3.0\n"
            "g2\t\t\t\n"
            "g3\t2.0\t\t4.0\n"
            "g4\t7.0\t\t8.0\n",
            encoding="utf-8",
        )
        out = DataIO()._load_expression_data(str(path))
        assert "g2" not in out.index
        assert "S2" not in out.columns
        assert out.shape == (3, 2)


# --------------------------------------------------------------------------
# _load_labels
# --------------------------------------------------------------------------
class TestLoadLabels:
    def test_tsv_labels(self, tmp_path):
        labels = make_labels([f"S{i:03d}" for i in range(N_SAMPLES)])
        path = write_labels_file(tmp_path, labels, "labels.tsv")
        out = DataIO()._load_labels(path)
        assert isinstance(out, pd.Series)
        assert len(out) == N_SAMPLES
        assert set(out.index) == set(labels.index)

    def test_csv_labels(self, tmp_path):
        labels = make_labels([f"S{i:03d}" for i in range(10)])
        path = write_labels_file(tmp_path, labels, "labels.csv")
        out = DataIO()._load_labels(path)
        assert len(out) == 10

    def test_unknown_extension_defaults_to_tab(self, tmp_path):
        labels = make_labels([f"S{i:03d}" for i in range(6)])
        path = tmp_path / "labels.lst"
        pd.DataFrame(
            {"sample_id": list(labels.index), "class_label": list(labels.values)}
        ).to_csv(path, sep="\t", index=False)
        out = DataIO()._load_labels(str(path))
        assert len(out) == 6

    def test_custom_column_names(self, tmp_path):
        path = tmp_path / "custom.csv"
        pd.DataFrame({"sid": ["a", "b", "c"], "grp": [1, 0, 1]}).to_csv(
            path, index=False
        )
        out = DataIO()._load_labels(str(path), sample_column="sid", label_column="grp")
        assert list(out.index) == ["a", "b", "c"]
        assert list(out.values) == [1, 0, 1]

    def test_missing_sample_column_raises(self, tmp_path):
        path = tmp_path / "nosample.csv"
        pd.DataFrame({"other": ["a"], "class_label": [1]}).to_csv(path, index=False)
        with pytest.raises(ValueError, match="Sample column 'sample_id' not found"):
            DataIO()._load_labels(str(path))

    def test_missing_label_column_raises(self, tmp_path):
        path = tmp_path / "nolabel.csv"
        pd.DataFrame({"sample_id": ["a"], "other": [1]}).to_csv(path, index=False)
        with pytest.raises(ValueError, match="Label column 'class_label' not found"):
            DataIO()._load_labels(str(path))

    def test_single_row_labels(self, tmp_path):
        path = tmp_path / "one.csv"
        pd.DataFrame({"sample_id": ["S000"], "class_label": [1]}).to_csv(
            path, index=False
        )
        out = DataIO()._load_labels(str(path))
        assert len(out) == 1
        assert len(out.unique()) == 1


# --------------------------------------------------------------------------
# _load_metadata
# --------------------------------------------------------------------------
class TestLoadMetadata:
    def test_yaml(self, tmp_path):
        path = tmp_path / "meta.yaml"
        path.write_text("study: demo\nplatform: rnaseq\n", encoding="utf-8")
        meta = DataIO()._load_metadata(str(path))
        assert meta == {"study": "demo", "platform": "rnaseq"}

    def test_yml_extension(self, tmp_path):
        path = tmp_path / "meta.yml"
        path.write_text("a: 1\n", encoding="utf-8")
        assert DataIO()._load_metadata(str(path)) == {"a": 1}

    def test_json(self, tmp_path):
        path = tmp_path / "meta.json"
        path.write_text(json.dumps({"study": "demo", "n": 3}), encoding="utf-8")
        meta = DataIO()._load_metadata(str(path))
        assert meta["n"] == 3

    def test_unsupported_extension_raises(self, tmp_path):
        path = tmp_path / "meta.txt"
        path.write_text("nope", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported metadata file format"):
            DataIO()._load_metadata(str(path))


# --------------------------------------------------------------------------
# load_data
# --------------------------------------------------------------------------
class TestLoadData:
    def test_happy_path_without_metadata(self, tmp_path):
        df = make_expression_df()
        labels = make_labels(df.columns)
        expr_path = write_expression_file(tmp_path, df)
        label_path = write_labels_file(tmp_path, labels)

        io = DataIO()
        result = io.load_data(expr_path, label_path)

        assert set(result) == {
            "expression_data",
            "labels",
            "metadata",
            "validation_results",
            "dataset_hash",
            "data_summary",
        }
        assert result["metadata"] is None
        assert result["expression_data"].shape == (N_GENES, N_SAMPLES)
        assert len(result["dataset_hash"].split("_")) == 2
        assert result["validation_results"]["status"] in {
            "passed",
            "warning",
            "failed",
        }
        assert result["data_summary"]["expression"]["n_genes"] == N_GENES

    def test_happy_path_with_metadata(self, tmp_path):
        df = make_expression_df()
        labels = make_labels(df.columns)
        expr_path = write_expression_file(tmp_path, df)
        label_path = write_labels_file(tmp_path, labels)
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"study": "demo"}), encoding="utf-8")

        io = DataIO()
        result = io.load_data(expr_path, label_path, str(meta_path))
        assert result["metadata"] == {"study": "demo"}
        assert result["data_summary"]["metadata"]["fields"] == ["study"]

    def test_missing_file_propagates_exception(self, tmp_path):
        with pytest.raises(Exception):
            DataIO().load_data(
                str(tmp_path / "missing.tsv"), str(tmp_path / "missing_labels.tsv")
            )


# --------------------------------------------------------------------------
# _validate_data and the individual checks
# --------------------------------------------------------------------------
class TestValidateData:
    def test_clean_data_passes_or_warns(self):
        io = loaded_io()
        results = io._validate_data()
        assert results["status"] in {"passed", "warning"}
        assert set(results["checks"]) >= {
            "data_types",
            "sample_intersection",
            "duplicates",
            "missing_values",
            "data_quality",
            "label_distribution",
        }

    def test_errors_set_failed_status(self):
        io = DataIO()
        io.expression_data = make_expression_df(n_genes=5, n_samples=4)
        # Labels that share no samples with expression data -> error branch
        io.labels = pd.Series([0, 1, 0, 1], index=["x1", "x2", "x3", "x4"])
        results = io._validate_data()
        assert results["status"] == "failed"
        assert any("No sample intersection" in e for e in results["errors"])

    def test_exception_inside_checks_is_captured(self):
        io = loaded_io()
        with patch.object(io, "_check_data_types", side_effect=RuntimeError("boom")):
            results = io._validate_data()
        assert results["status"] == "error"
        assert any("Validation failed: boom" in e for e in results["errors"])

    def test_no_data_at_all_passes_trivially(self):
        results = DataIO()._validate_data()
        assert results["status"] == "passed"
        assert results["errors"] == []


class TestCheckDataTypes:
    def test_numeric_expression_and_unique_labels(self):
        io = loaded_io()
        res = blank_results()
        io._check_data_types(res)
        checks = res["checks"]["data_types"]
        assert checks["expression_numeric"]
        assert checks["expression_shape"]
        assert checks["labels_not_empty"]
        assert checks["labels_unique_samples"]
        assert res["errors"] == []

    def test_non_numeric_expression_and_empty_shape(self):
        io = DataIO()
        io.expression_data = pd.DataFrame({"S1": pd.Series([], dtype=object)})
        res = blank_results()
        io._check_data_types(res)
        assert "Expression data contains non-numeric values" in res["errors"]
        assert "Expression data is empty" in res["errors"]

    def test_empty_labels_and_duplicate_sample_ids(self):
        io = DataIO()
        io.labels = pd.Series([], dtype=float)
        res = blank_results()
        io._check_data_types(res)
        assert "Labels are empty" in res["errors"]

        io.labels = pd.Series([0, 1, 1], index=["a", "a", "b"])
        res = blank_results()
        io._check_data_types(res)
        assert "Duplicate sample IDs in labels" in res["errors"]

    def test_no_data_records_empty_checks(self):
        res = blank_results()
        DataIO()._check_data_types(res)
        assert res["checks"]["data_types"] == {}


class TestCheckSampleIntersection:
    def test_full_intersection(self):
        io = loaded_io()
        res = blank_results()
        io._check_sample_intersection(res)
        info = res["checks"]["sample_intersection"]
        assert info["intersection_size"] == N_SAMPLES
        assert info["expression_only"] == 0
        assert info["labels_only"] == 0
        assert info["intersection_ratio"] == pytest.approx(1.0)
        assert res["warnings"] == []

    def test_no_intersection_is_error(self):
        io = DataIO()
        io.expression_data = make_expression_df(n_genes=4, n_samples=3)
        io.labels = pd.Series([0, 1, 0], index=["z1", "z2", "z3"])
        res = blank_results()
        io._check_sample_intersection(res)
        assert "No sample intersection between expression and labels" in res["errors"]
        assert res["checks"]["sample_intersection"]["intersection_ratio"] == 0

    def test_partial_intersection_warns(self):
        io = DataIO()
        io.expression_data = make_expression_df(n_genes=10, n_samples=10)
        overlap = list(io.expression_data.columns[:5])
        io.labels = pd.Series(
            [0] * 5 + [1] * 3, index=overlap + ["extra1", "extra2", "extra3"]
        )
        res = blank_results()
        io._check_sample_intersection(res)
        info = res["checks"]["sample_intersection"]
        assert info["intersection_size"] == 5
        assert info["expression_only"] == 5
        assert info["labels_only"] == 3
        joined = " ".join(res["warnings"])
        assert "Low sample intersection" in joined
        assert "samples in expression but not in labels" in joined
        assert "samples in labels but not in expression" in joined

    def test_skipped_when_labels_missing(self):
        io = DataIO()
        io.expression_data = make_expression_df(n_genes=3, n_samples=2)
        res = blank_results()
        io._check_sample_intersection(res)
        assert "sample_intersection" not in res["checks"]

    def test_empty_expression_columns_ratio_zero(self):
        io = DataIO()
        io.expression_data = pd.DataFrame(index=["g1", "g2"])
        io.labels = pd.Series([0, 1], index=["a", "b"])
        res = blank_results()
        io._check_sample_intersection(res)
        assert res["checks"]["sample_intersection"]["intersection_ratio"] == 0


class TestCheckDuplicates:
    def test_no_duplicates(self):
        io = loaded_io()
        res = blank_results()
        io._check_duplicates(res)
        assert res["checks"]["duplicates"]["duplicate_genes"] == 0
        assert res["checks"]["duplicates"]["duplicate_samples"] == 0
        assert res["warnings"] == []
        assert res["errors"] == []

    def test_duplicate_genes_warn(self):
        io = DataIO()
        io.expression_data = pd.DataFrame(
            [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
            index=["g1", "g1", "g2"],
            columns=["S1", "S2"],
        )
        res = blank_results()
        io._check_duplicates(res)
        assert res["checks"]["duplicates"]["duplicate_genes"] == 1
        assert any("duplicate gene IDs found" in w for w in res["warnings"])

    def test_duplicate_samples_error(self):
        io = DataIO()
        io.labels = pd.Series([0, 1, 1], index=["a", "a", "b"])
        res = blank_results()
        io._check_duplicates(res)
        assert res["checks"]["duplicates"]["duplicate_samples"] == 1
        assert any("duplicate sample IDs found" in e for e in res["errors"])

    def test_no_data(self):
        res = blank_results()
        DataIO()._check_duplicates(res)
        assert res["checks"]["duplicates"] == {}


class TestCheckMissingValues:
    def test_no_missing(self):
        io = loaded_io()
        res = blank_results()
        io._check_missing_values(res)
        checks = res["checks"]["missing_values"]
        assert checks["missing_expression"] == 0
        assert checks["missing_expression_ratio"] == pytest.approx(0.0)
        assert checks["missing_labels"] == 0
        assert res["warnings"] == []

    def test_high_missing_ratio_warns(self):
        io = DataIO()
        df = make_expression_df(n_genes=10, n_samples=10)
        df.iloc[:5, :] = np.nan  # 50% missing
        io.expression_data = df
        io.labels = pd.Series([0, 1] * 5, index=df.columns)
        io.labels.iloc[0] = np.nan
        res = blank_results()
        io._check_missing_values(res)
        checks = res["checks"]["missing_values"]
        assert checks["missing_expression_ratio"] == pytest.approx(0.5)
        assert checks["missing_labels"] == 1
        joined = " ".join(res["warnings"])
        assert "High missing value ratio" in joined
        assert "missing values in labels" in joined

    def test_empty_expression_skips_block(self):
        io = DataIO()
        io.expression_data = pd.DataFrame()
        res = blank_results()
        io._check_missing_values(res)
        assert "missing_expression" not in res["checks"]["missing_values"]


class TestCheckDataQuality:
    def test_clean_matrix(self):
        io = loaded_io()
        res = blank_results()
        io._check_data_quality(res)
        checks = res["checks"]["data_quality"]
        assert checks["infinite_values"] == 0
        assert checks["negative_values"] == 0
        assert checks["zero_variance_genes"] == 0
        assert res["warnings"] == []

    def test_infinite_negative_and_zero_variance(self):
        io = DataIO()
        df = make_expression_df(n_genes=6, n_samples=5)
        df.iloc[0, 0] = np.inf
        df.iloc[1, 1] = -3.0
        df.iloc[2, :] = 1.0  # zero variance gene
        io.expression_data = df
        res = blank_results()
        io._check_data_quality(res)
        checks = res["checks"]["data_quality"]
        assert checks["infinite_values"] == 1
        assert checks["negative_values"] == 1
        assert checks["zero_variance_genes"] == 1
        joined = " ".join(res["warnings"])
        assert "infinite values found" in joined
        assert "negative values found" in joined
        assert "genes with zero variance" in joined

    def test_no_expression_data_skips(self):
        res = blank_results()
        DataIO()._check_data_quality(res)
        assert "data_quality" not in res["checks"]


class TestCheckLabelDistribution:
    def test_balanced_labels(self):
        io = DataIO()
        io.labels = pd.Series([0] * 10 + [1] * 10, index=[f"S{i}" for i in range(20)])
        res = blank_results()
        io._check_label_distribution(res)
        checks = res["checks"]["label_distribution"]
        assert checks["n_classes"] == 2
        assert checks["min_class_size"] == 10
        assert checks["max_class_size"] == 10
        assert checks["class_imbalance_ratio"] == pytest.approx(1.0)
        assert res["warnings"] == []

    def test_imbalance_and_small_class_warn(self):
        io = DataIO()
        io.labels = pd.Series([0] * 15 + [1] * 3, index=[f"S{i}" for i in range(18)])
        res = blank_results()
        io._check_label_distribution(res)
        checks = res["checks"]["label_distribution"]
        assert checks["class_imbalance_ratio"] == pytest.approx(5.0)
        assert checks["min_class_size"] == 3
        joined = " ".join(res["warnings"])
        assert "Class imbalance detected" in joined
        assert "Small class size" in joined

    def test_single_class(self):
        io = DataIO()
        io.labels = pd.Series([1] * 8, index=[f"S{i}" for i in range(8)])
        res = blank_results()
        io._check_label_distribution(res)
        checks = res["checks"]["label_distribution"]
        assert checks["n_classes"] == 1
        assert checks["class_imbalance_ratio"] == pytest.approx(1.0)
        assert checks["class_counts"] == {1: 8}

    def test_no_labels_skips(self):
        res = blank_results()
        DataIO()._check_label_distribution(res)
        assert "label_distribution" not in res["checks"]


# --------------------------------------------------------------------------
# hash / summary
# --------------------------------------------------------------------------
class TestDatasetHashAndSummary:
    def test_hash_is_deterministic(self):
        h1 = loaded_io()._generate_dataset_hash()
        h2 = loaded_io()._generate_dataset_hash()
        assert h1 == h2
        assert len(h1) == 17  # 8 + "_" + 8

    def test_hash_changes_with_data(self):
        io = loaded_io()
        first = io._generate_dataset_hash()
        io.expression_data.iloc[0, 0] += 1.0
        assert io._generate_dataset_hash() != first

    def test_hash_unknown_without_data(self):
        assert DataIO()._generate_dataset_hash() == "unknown"
        io = DataIO()
        io.expression_data = make_expression_df(n_genes=2, n_samples=2)
        assert io._generate_dataset_hash() == "unknown"

    def test_summary_empty_instance(self):
        summary = DataIO()._generate_data_summary()
        assert summary["dataset_hash"] == "unknown"
        assert "timestamp" in summary
        assert "expression" not in summary
        assert "labels" not in summary
        assert "metadata" not in summary

    def test_summary_full(self):
        io = loaded_io()
        io.metadata = {"study": "demo", "platform": "rnaseq"}
        summary = io._generate_data_summary()

        expr = summary["expression"]
        assert expr["n_genes"] == N_GENES
        assert expr["n_samples"] == N_SAMPLES
        assert expr["value_range"]["min"] <= expr["value_range"]["mean"]
        assert expr["value_range"]["mean"] <= expr["value_range"]["max"]
        assert expr["value_range"]["std"] > 0

        assert summary["labels"]["n_samples"] == N_SAMPLES
        assert summary["labels"]["n_classes"] >= 1
        assert sum(summary["labels"]["class_distribution"].values()) == N_SAMPLES

        assert summary["metadata"]["n_fields"] == 2
        assert set(summary["metadata"]["fields"]) == {"study", "platform"}


# --------------------------------------------------------------------------
# gene ID mapping
# --------------------------------------------------------------------------
def write_mapping_file(tmp_path, rows, name="map.tsv"):
    path = tmp_path / name
    frame = pd.DataFrame(rows)
    if path.suffix == ".csv":
        frame.to_csv(path, index=False)
    else:
        frame.to_csv(path, sep="\t", index=False)
    return str(path)


MAPPING_ROWS = [
    {
        "from_id": "ENSG1",
        "to_id": "TP53",
        "from_type": "ensembl",
        "to_type": "symbol",
    },
    {
        "from_id": "ENSG2",
        "to_id": "BRCA1",
        "from_type": "ensembl",
        "to_type": "symbol",
    },
]


class TestLoadGeneMapping:
    def test_tsv_mapping(self, tmp_path):
        path = write_mapping_file(tmp_path, MAPPING_ROWS, "map.tsv")
        mapping = DataIO()._load_gene_mapping(path)
        assert mapping["ensembl"]["symbol"]["ENSG1"] == "TP53"
        assert mapping["ensembl"]["symbol"]["ENSG2"] == "BRCA1"

    def test_csv_mapping(self, tmp_path):
        path = write_mapping_file(tmp_path, MAPPING_ROWS, "map.csv")
        mapping = DataIO()._load_gene_mapping(path)
        assert set(mapping["ensembl"]["symbol"]) == {"ENSG1", "ENSG2"}

    def test_txt_mapping(self, tmp_path):
        path = write_mapping_file(tmp_path, MAPPING_ROWS, "map.txt")
        mapping = DataIO()._load_gene_mapping(path)
        assert "ensembl" in mapping

    def test_multiple_type_pairs(self, tmp_path):
        rows = MAPPING_ROWS + [
            {
                "from_id": "TP53",
                "to_id": "ENSG1",
                "from_type": "symbol",
                "to_type": "ensembl",
            },
            {
                "from_id": "ENSG3",
                "to_id": "111",
                "from_type": "ensembl",
                "to_type": "entrez",
            },
        ]
        mapping = DataIO()._load_gene_mapping(write_mapping_file(tmp_path, rows))
        assert set(mapping) == {"ensembl", "symbol"}
        assert set(mapping["ensembl"]) == {"symbol", "entrez"}

    def test_unsupported_format_raises(self, tmp_path):
        path = tmp_path / "map.json"
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported mapping file format"):
            DataIO()._load_gene_mapping(str(path))


class TestDefaultGeneMapping:
    def test_default_is_empty(self):
        assert DataIO()._get_default_gene_mapping() == {}


class TestMapGeneIds:
    def test_mapping_applied_and_unmapped_kept(self, tmp_path):
        path = write_mapping_file(tmp_path, MAPPING_ROWS)
        expr = pd.DataFrame(
            RNG.rand(3, 4),
            index=["ENSG1", "ENSG2", "ENSG_UNKNOWN"],
            columns=["S1", "S2", "S3", "S4"],
        )
        out = DataIO().map_gene_ids(expr, reference_file=path)
        assert list(out.index) == ["TP53", "BRCA1", "ENSG_UNKNOWN"]
        assert out.shape == expr.shape
        # original untouched
        assert list(expr.index) == ["ENSG1", "ENSG2", "ENSG_UNKNOWN"]

    def test_duplicates_aggregated_by_mean(self, tmp_path):
        rows = [
            {
                "from_id": "ENSG1",
                "to_id": "TP53",
                "from_type": "ensembl",
                "to_type": "symbol",
            },
            {
                "from_id": "ENSG2",
                "to_id": "TP53",
                "from_type": "ensembl",
                "to_type": "symbol",
            },
        ]
        path = write_mapping_file(tmp_path, rows)
        expr = pd.DataFrame(
            [[1.0, 3.0], [3.0, 5.0]],
            index=["ENSG1", "ENSG2"],
            columns=["S1", "S2"],
        )
        out = DataIO().map_gene_ids(expr, reference_file=path)
        assert list(out.index) == ["TP53"]
        assert out.loc["TP53", "S1"] == pytest.approx(2.0)
        assert out.loc["TP53", "S2"] == pytest.approx(4.0)

    def test_no_mapping_available_returns_input(self):
        expr = pd.DataFrame(
            RNG.rand(3, 3), index=["a", "b", "c"], columns=["S1", "S2", "S3"]
        )
        out = DataIO().map_gene_ids(expr)
        assert out is expr

    def test_unknown_to_type_returns_input(self, tmp_path):
        path = write_mapping_file(tmp_path, MAPPING_ROWS)
        expr = pd.DataFrame(
            RNG.rand(2, 2), index=["ENSG1", "ENSG2"], columns=["S1", "S2"]
        )
        out = DataIO().map_gene_ids(expr, to_type="entrez", reference_file=path)
        assert out is expr

    def test_unknown_from_type_returns_input(self, tmp_path):
        path = write_mapping_file(tmp_path, MAPPING_ROWS)
        expr = pd.DataFrame(
            RNG.rand(2, 2), index=["ENSG1", "ENSG2"], columns=["S1", "S2"]
        )
        out = DataIO().map_gene_ids(expr, from_type="refseq", reference_file=path)
        assert out is expr


# --------------------------------------------------------------------------
# save_processed_data
# --------------------------------------------------------------------------
class TestSaveProcessedData:
    def test_tsv(self, tmp_path):
        df = make_expression_df(n_genes=5, n_samples=4)
        out_path = str(tmp_path / "out.tsv")
        assert DataIO().save_processed_data(df, out_path) == out_path
        reread = pd.read_csv(out_path, sep="\t", index_col=0)
        assert reread.shape == df.shape

    def test_csv_and_case_insensitive_format(self, tmp_path):
        df = make_expression_df(n_genes=5, n_samples=4)
        out_path = str(tmp_path / "out.csv")
        assert DataIO().save_processed_data(df, out_path, format="CSV") == out_path
        assert pd.read_csv(out_path, index_col=0).shape == df.shape

    def test_h5_delegates_to_to_hdf(self, tmp_path):
        """to_hdf needs pytables; mock it so the branch runs in any environment."""
        df = MagicMock(spec=pd.DataFrame)
        out_path = str(tmp_path / "out.h5")
        assert DataIO().save_processed_data(df, out_path, format="h5") == out_path
        df.to_hdf.assert_called_once_with(out_path, key="data")

    def test_unsupported_format_raises(self, tmp_path):
        df = make_expression_df(n_genes=3, n_samples=2)
        with pytest.raises(ValueError, match="Unsupported format: parquet"):
            DataIO().save_processed_data(df, str(tmp_path / "o.parquet"), "parquet")

    def test_write_failure_propagates(self, tmp_path):
        df = MagicMock(spec=pd.DataFrame)
        df.to_csv.side_effect = OSError("disk full")
        with pytest.raises(OSError, match="disk full"):
            DataIO().save_processed_data(df, str(tmp_path / "o.tsv"))


# --------------------------------------------------------------------------
# get_validation_summary
# --------------------------------------------------------------------------
class TestGetValidationSummary:
    def test_without_validation(self):
        assert DataIO().get_validation_summary() == {
            "status": "No validation performed"
        }

    def test_with_populated_results(self):
        io = DataIO()
        io.validation_results = {
            "status": "warning",
            "errors": ["e1"],
            "warnings": ["w1", "w2"],
            "checks": {"data_types": {"expression_numeric": True}},
        }
        summary = io.get_validation_summary()
        assert summary["status"] == "warning"
        assert summary["n_errors"] == 1
        assert summary["n_warnings"] == 2
        assert summary["errors"] == ["e1"]
        assert summary["warnings"] == ["w1", "w2"]
        assert summary["checks"]["data_types"]["expression_numeric"] is True

    def test_with_partial_results_uses_defaults(self):
        io = DataIO()
        io.validation_results = {"something": 1}
        summary = io.get_validation_summary()
        assert summary["status"] == "unknown"
        assert summary["n_errors"] == 0
        assert summary["n_warnings"] == 0
        assert summary["checks"] == {}
