"""
Self-contained unit tests for app.data_processing.data_loader.

Runs with --noconftest: no shared fixtures are used, all data is built inline.
"""

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import yaml

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_local.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "True")

from app.data_processing.data_loader import DataLoader  # noqa: E402

RNG = np.random.default_rng(20240720)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def make_expression(n_genes: int = 20, n_samples: int = 8) -> pd.DataFrame:
    """Small deterministic expression matrix: genes x samples."""
    data = RNG.gamma(shape=2.0, scale=3.0, size=(n_genes, n_samples))
    return pd.DataFrame(
        np.round(data, 4),
        index=[f"GENE{i:03d}" for i in range(n_genes)],
        columns=[f"S{i:02d}" for i in range(n_samples)],
    )


def make_labels(n_samples: int = 8, batch: bool = False) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "sample_id": [f"S{i:02d}" for i in range(n_samples)],
            "class_label": ["tumor" if i % 2 else "normal" for i in range(n_samples)],
            "age": [40 + i for i in range(n_samples)],
        }
    )
    if batch:
        df["batch"] = ["B1" if i < n_samples // 2 else "B2" for i in range(n_samples)]
    return df


def write_csv(path, df, sep=","):
    df.to_csv(path, sep=sep)
    return str(path)


def loaded_loader(config=None, batch=False):
    """DataLoader with expression + labels populated directly (no file IO)."""
    loader = DataLoader(config)
    loader.expression_data = make_expression()
    labels = make_labels(batch=batch).set_index("sample_id")
    loader.labels = labels
    return loader


# --------------------------------------------------------------------------
# __init__
# --------------------------------------------------------------------------
class TestInit:
    def test_default_config_is_empty_dict(self):
        loader = DataLoader()
        assert loader.config == {}
        assert loader.expression_data is None
        assert loader.labels is None
        assert loader.metadata is None
        assert loader.validation_results == {}

    def test_explicit_config_retained(self):
        cfg = {"label_column": "outcome"}
        assert DataLoader(cfg).config is cfg

    def test_falsy_config_replaced_by_empty_dict(self):
        assert DataLoader({}).config == {}


# --------------------------------------------------------------------------
# load_expression_data
# --------------------------------------------------------------------------
class TestLoadExpressionData:
    def test_load_csv_happy_path(self, tmp_path):
        expr = make_expression()
        path = write_csv(tmp_path / "expr.csv", expr)
        loader = DataLoader()
        out = loader.load_expression_data(path)
        assert out.shape == (20, 8)
        assert list(out.columns) == list(expr.columns)
        assert loader.expression_data is out
        np.testing.assert_allclose(out.values, expr.values, rtol=1e-6)

    def test_load_tsv_by_suffix(self, tmp_path):
        expr = make_expression()
        path = write_csv(tmp_path / "expr.tsv", expr, sep="\t")
        out = DataLoader().load_expression_data(path)
        assert out.shape == (20, 8)

    def test_txt_with_tab_delimiter_detected(self, tmp_path):
        expr = make_expression()
        path = write_csv(tmp_path / "expr.txt", expr, sep="\t")
        out = DataLoader().load_expression_data(path)
        assert out.shape == (20, 8)

    def test_txt_with_comma_delimiter(self, tmp_path):
        expr = make_expression()
        path = write_csv(tmp_path / "expr.txt", expr, sep=",")
        out = DataLoader().load_expression_data(path)
        assert out.shape == (20, 8)

    def test_kwargs_forwarded_to_pandas(self, tmp_path):
        expr = make_expression()
        path = write_csv(tmp_path / "expr.csv", expr)
        out = DataLoader().load_expression_data(path, nrows=15)
        assert out.shape[0] <= 15

    def test_excel_branch(self, tmp_path):
        expr = make_expression()
        path = tmp_path / "expr.xlsx"
        path.write_bytes(b"fake-xlsx")
        with patch("pandas.read_excel", return_value=expr) as mocked:
            out = DataLoader().load_expression_data(str(path))
        assert mocked.call_count == 1
        assert out.shape == (20, 8)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Expression file not found"):
            DataLoader().load_expression_data(str(tmp_path / "nope.csv"))

    def test_unsupported_extension_raises(self, tmp_path):
        path = tmp_path / "expr.json"
        path.write_text("{}")
        with pytest.raises(ValueError, match="Unsupported file format"):
            DataLoader().load_expression_data(str(path))

    def test_empty_dataframe_raises(self, tmp_path):
        path = tmp_path / "expr.csv"
        path.write_text("gene,S1,S2\n")
        with pytest.raises(ValueError, match="Expression data is empty"):
            DataLoader().load_expression_data(str(path))

    def test_too_few_genes_raises(self, tmp_path):
        expr = make_expression(n_genes=4, n_samples=8)
        path = write_csv(tmp_path / "expr.csv", expr)
        with pytest.raises(ValueError, match="too few genes"):
            DataLoader().load_expression_data(path)

    def test_too_few_samples_raises(self, tmp_path):
        expr = make_expression(n_genes=20, n_samples=3)
        path = write_csv(tmp_path / "expr.csv", expr)
        with pytest.raises(ValueError, match="too few samples"):
            DataLoader().load_expression_data(path)

    def test_non_numeric_columns_dropped(self, tmp_path):
        expr = make_expression(n_genes=20, n_samples=8)
        expr["annotation"] = "chr1"
        path = write_csv(tmp_path / "expr.csv", expr)
        out = DataLoader().load_expression_data(path)
        assert "annotation" not in out.columns
        assert out.shape[1] == 8

    def test_all_zero_genes_removed(self, tmp_path):
        expr = make_expression(n_genes=20, n_samples=8)
        expr.iloc[0] = 0.0
        expr.iloc[1] = 0.0
        path = write_csv(tmp_path / "expr.csv", expr)
        out = DataLoader().load_expression_data(path)
        assert out.shape[0] == 18
        assert "GENE000" not in out.index

    def test_all_nan_gene_removed(self, tmp_path):
        expr = make_expression(n_genes=20, n_samples=8)
        expr.iloc[3] = np.nan
        path = write_csv(tmp_path / "expr.csv", expr)
        out = DataLoader().load_expression_data(path)
        assert "GENE003" not in out.index
        assert out.shape[0] == 19

    def test_partial_nans_kept(self, tmp_path):
        expr = make_expression(n_genes=20, n_samples=8)
        expr.iloc[5, 0] = np.nan
        path = write_csv(tmp_path / "expr.csv", expr)
        out = DataLoader().load_expression_data(path)
        assert out.shape[0] == 20
        assert bool(out.isna().any().any())


# --------------------------------------------------------------------------
# load_labels
# --------------------------------------------------------------------------
class TestLoadLabels:
    def test_load_csv_happy_path(self, tmp_path):
        labels = make_labels()
        path = tmp_path / "labels.csv"
        labels.to_csv(path, index=False)
        loader = DataLoader()
        out = loader.load_labels(str(path))
        assert out.index.name == "sample_id"
        assert list(out.columns) == ["class_label", "age"]
        assert len(out) == 8
        assert loader.labels is out

    def test_load_tsv_suffix(self, tmp_path):
        labels = make_labels()
        path = tmp_path / "labels.tsv"
        labels.to_csv(path, sep="\t", index=False)
        out = DataLoader().load_labels(str(path))
        assert len(out) == 8

    def test_txt_tab_detection(self, tmp_path):
        labels = make_labels()
        path = tmp_path / "labels.txt"
        labels.to_csv(path, sep="\t", index=False)
        out = DataLoader().load_labels(str(path))
        assert len(out) == 8

    def test_custom_column_names(self, tmp_path):
        labels = make_labels().rename(
            columns={"sample_id": "sid", "class_label": "outcome"}
        )
        path = tmp_path / "labels.csv"
        labels.to_csv(path, index=False)
        out = DataLoader().load_labels(
            str(path), sample_id_col="sid", label_col="outcome"
        )
        assert out.index.name == "sid"
        assert "outcome" in out.columns

    def test_excel_branch(self, tmp_path):
        labels = make_labels()
        path = tmp_path / "labels.xls"
        path.write_bytes(b"fake")
        with patch("pandas.read_excel", return_value=labels) as mocked:
            out = DataLoader().load_labels(str(path))
        assert mocked.call_count == 1
        assert len(out) == 8

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Labels file not found"):
            DataLoader().load_labels(str(tmp_path / "nope.csv"))

    def test_unsupported_format_raises(self, tmp_path):
        path = tmp_path / "labels.parquet"
        path.write_text("x")
        with pytest.raises(ValueError, match="Unsupported file format"):
            DataLoader().load_labels(str(path))

    def test_missing_sample_id_column_raises(self, tmp_path):
        labels = make_labels().drop(columns=["sample_id"])
        path = tmp_path / "labels.csv"
        labels.to_csv(path, index=False)
        with pytest.raises(ValueError, match="Sample ID column"):
            DataLoader().load_labels(str(path))

    def test_missing_label_column_raises(self, tmp_path):
        labels = make_labels().drop(columns=["class_label"])
        path = tmp_path / "labels.csv"
        labels.to_csv(path, index=False)
        with pytest.raises(ValueError, match="Label column"):
            DataLoader().load_labels(str(path))

    def test_all_labels_missing_raises(self, tmp_path):
        labels = make_labels()
        labels["class_label"] = np.nan
        path = tmp_path / "labels.csv"
        labels.to_csv(path, index=False)
        with pytest.raises(ValueError, match="All labels are missing"):
            DataLoader().load_labels(str(path))

    def test_duplicate_sample_ids_raise(self, tmp_path):
        labels = make_labels()
        labels.loc[1, "sample_id"] = labels.loc[0, "sample_id"]
        path = tmp_path / "labels.csv"
        labels.to_csv(path, index=False)
        with pytest.raises(ValueError, match="Duplicate sample IDs"):
            DataLoader().load_labels(str(path))

    def test_single_row_labels(self, tmp_path):
        labels = make_labels(n_samples=1)
        path = tmp_path / "labels.csv"
        labels.to_csv(path, index=False)
        out = DataLoader().load_labels(str(path))
        assert len(out) == 1


# --------------------------------------------------------------------------
# load_metadata
# --------------------------------------------------------------------------
class TestLoadMetadata:
    def test_happy_path(self, tmp_path):
        path = tmp_path / "meta.yaml"
        path.write_text("project: demo\nversion: 2\n")
        loader = DataLoader()
        meta = loader.load_metadata(str(path))
        assert meta == {"project": "demo", "version": 2}
        assert loader.metadata == meta

    def test_missing_file_returns_empty_dict(self, tmp_path):
        loader = DataLoader()
        assert loader.load_metadata(str(tmp_path / "nope.yaml")) == {}
        assert loader.metadata is None

    def test_invalid_yaml_swallowed_returns_empty_dict(self, tmp_path):
        path = tmp_path / "meta.yaml"
        path.write_text("project: [unclosed\n  bad: :\n")
        loader = DataLoader()
        assert loader.load_metadata(str(path)) == {}
        assert loader.metadata is None

    def test_empty_yaml_returns_none_payload(self, tmp_path):
        path = tmp_path / "meta.yaml"
        path.write_text("")
        loader = DataLoader()
        # yaml.safe_load("") -> None; the loader stores and returns it as-is.
        assert loader.load_metadata(str(path)) is None
        assert loader.metadata is None


# --------------------------------------------------------------------------
# validate_data_integrity
# --------------------------------------------------------------------------
class TestValidateDataIntegrity:
    def test_expression_not_loaded(self):
        res = DataLoader().validate_data_integrity()
        assert res["status"] == "error"
        assert "Expression data not loaded" in res["issues"]

    def test_labels_not_loaded(self):
        loader = DataLoader()
        loader.expression_data = make_expression()
        res = loader.validate_data_integrity()
        assert res["status"] == "error"
        assert "Labels data not loaded" in res["issues"]

    def test_valid_dataset(self):
        loader = loaded_loader()
        res = loader.validate_data_integrity()
        assert res["status"] == "valid"
        assert res["issues"] == []
        summary = res["summary"]
        assert summary["sample_intersection"]["common_samples"] == 8
        assert summary["missing_values"]["expression_missing"] == 0
        assert summary["zero_inflation"]["expression_zero_pct"] == pytest.approx(0.0)
        assert summary["class_balance"]["class_ratio"] == pytest.approx(1.0)
        assert loader.validation_results is res

    def test_no_common_samples(self):
        loader = loaded_loader()
        loader.labels.index = [f"X{i}" for i in range(len(loader.labels))]
        res = loader.validate_data_integrity()
        assert res["status"] == "error"
        assert "No common samples between expression and labels" in res["issues"]

    def test_too_few_common_samples(self):
        loader = loaded_loader()
        loader.labels = loader.labels.iloc[:3]
        res = loader.validate_data_integrity()
        assert res["status"] == "error"
        assert "Too few common samples (< 5)" in res["issues"]

    def test_partial_overlap_produces_warnings(self):
        loader = loaded_loader()
        extra = loader.labels.iloc[:3].copy()
        extra.index = ["Z1", "Z2", "Z3"]
        loader.labels = pd.concat([loader.labels, extra])
        loader.expression_data["EXTRA1"] = 1.0
        res = loader.validate_data_integrity()
        assert res["status"] == "valid"
        assert any("expression data only" in w for w in res["warnings"])
        assert any("labels only" in w for w in res["warnings"])

    def test_high_missing_values_error(self):
        loader = loaded_loader()
        expr = loader.expression_data
        expr.iloc[:, :6] = np.nan  # 6/8 columns NaN -> 75%
        res = loader.validate_data_integrity()
        assert res["status"] == "error"
        assert any("Too many missing values" in i for i in res["issues"])
        assert res["summary"]["missing_values"][
            "expression_missing_pct"
        ] == pytest.approx(75.0)

    def test_moderate_missing_values_warning(self):
        loader = loaded_loader()
        loader.expression_data.iloc[:, :3] = np.nan  # 37.5%
        res = loader.validate_data_integrity()
        assert res["status"] == "valid"
        assert any("High percentage of missing" in w for w in res["warnings"])

    def test_zero_inflation_warning(self):
        loader = loaded_loader()
        loader.expression_data.iloc[:, :7] = 0.0  # 87.5% zeros
        res = loader.validate_data_integrity()
        assert any("zero-inflation" in w for w in res["warnings"])
        assert res["summary"]["zero_inflation"]["expression_zero_pct"] > 80

    def test_severe_class_imbalance(self):
        expr = make_expression(n_genes=20, n_samples=21)
        labels = pd.DataFrame(
            {"class_label": ["tumor"] * 20 + ["normal"]}, index=list(expr.columns)
        )
        loader = DataLoader()
        loader.expression_data = expr
        loader.labels = labels
        res = loader.validate_data_integrity()
        assert res["summary"]["class_balance"]["class_ratio"] == pytest.approx(1 / 20)
        assert any("Severe class imbalance" in w for w in res["warnings"])

    def test_moderate_class_imbalance(self):
        expr = make_expression(n_genes=20, n_samples=10)
        labels = pd.DataFrame(
            {"class_label": ["tumor"] * 8 + ["normal"] * 2}, index=list(expr.columns)
        )
        loader = DataLoader()
        loader.expression_data = expr
        loader.labels = labels
        res = loader.validate_data_integrity()
        assert res["summary"]["class_balance"]["class_ratio"] == pytest.approx(0.25)
        assert any("Moderate class imbalance" in w for w in res["warnings"])

    def test_one_class_labels(self):
        expr = make_expression(n_genes=20, n_samples=8)
        labels = pd.DataFrame({"class_label": ["tumor"] * 8}, index=list(expr.columns))
        loader = DataLoader()
        loader.expression_data = expr
        loader.labels = labels
        res = loader.validate_data_integrity()
        assert res["summary"]["class_balance"]["class_counts"] == {"tumor": 8}
        assert res["summary"]["class_balance"]["class_ratio"] == pytest.approx(1.0)

    def test_custom_label_column_from_config(self):
        loader = loaded_loader(config={"label_column": "age"})
        res = loader.validate_data_integrity()
        assert "class_balance" in res["summary"]
        assert len(res["summary"]["class_balance"]["class_counts"]) == 8

    def test_label_column_absent_skips_class_balance(self):
        loader = loaded_loader(config={"label_column": "does_not_exist"})
        res = loader.validate_data_integrity()
        assert "class_balance" not in res["summary"]

    def test_batch_column_multiple_batches(self):
        loader = loaded_loader(config={"batch_column": "batch"}, batch=True)
        res = loader.validate_data_integrity()
        assert res["summary"]["batch_info"]["n_batches"] == 2
        assert any("Multiple batches" in w for w in res["warnings"])

    def test_batch_column_single_batch_no_warning(self):
        loader = loaded_loader(config={"batch_column": "batch"}, batch=True)
        loader.labels["batch"] = "B1"
        res = loader.validate_data_integrity()
        assert res["summary"]["batch_info"]["n_batches"] == 1
        assert not any("Multiple batches" in w for w in res["warnings"])

    def test_batch_column_configured_but_absent(self):
        loader = loaded_loader(config={"batch_column": "batch"}, batch=False)
        res = loader.validate_data_integrity()
        assert "batch_info" not in res["summary"]

    def test_unexpected_exception_captured(self):
        loader = DataLoader()
        loader.expression_data = MagicMock()
        loader.expression_data.columns = 12345  # not iterable -> TypeError in set()
        loader.labels = MagicMock()
        loader.labels.index = [1, 2, 3]
        res = loader.validate_data_integrity()
        assert res["status"] == "error"
        assert any(i.startswith("Validation error:") for i in res["issues"])


# --------------------------------------------------------------------------
# align_data
# --------------------------------------------------------------------------
class TestAlignData:
    def test_requires_both_datasets(self):
        with pytest.raises(ValueError, match="must be loaded"):
            DataLoader().align_data()

        loader = DataLoader()
        loader.expression_data = make_expression()
        with pytest.raises(ValueError, match="must be loaded"):
            loader.align_data()

    def test_align_full_overlap(self):
        loader = loaded_loader()
        expr, labels = loader.align_data()
        assert expr.shape == (20, 8)
        assert labels.shape[0] == 8
        assert set(expr.columns) == set(labels.index)
        assert list(expr.columns) == list(labels.index)

    def test_align_partial_overlap(self):
        loader = loaded_loader()
        loader.labels = loader.labels.iloc[:5]
        expr, labels = loader.align_data()
        assert expr.shape[1] == 5
        assert len(labels) == 5
        assert set(expr.columns) == set(loader.labels.index)

    def test_align_no_overlap_raises(self):
        loader = loaded_loader()
        loader.labels.index = [f"Q{i}" for i in range(len(loader.labels))]
        with pytest.raises(ValueError, match="No common samples"):
            loader.align_data()


# --------------------------------------------------------------------------
# get_data_summary
# --------------------------------------------------------------------------
class TestGetDataSummary:
    def test_empty_loader(self):
        summary = DataLoader().get_data_summary()
        assert summary["expression_data"] is None
        assert summary["labels"] is None
        assert summary["metadata"] == {}
        assert summary["validation"] == {}

    def test_expression_only(self):
        loader = DataLoader()
        loader.expression_data = make_expression()
        summary = loader.get_data_summary()
        expr = summary["expression_data"]
        assert expr["shape"] == (20, 8)
        assert expr["missing_values"] == 0
        assert expr["missing_percentage"] == pytest.approx(0.0)
        assert expr["zero_values"] == 0
        assert expr["zero_percentage"] == pytest.approx(0.0)
        assert expr["value_range"]["min"] <= expr["value_range"]["mean"]
        assert expr["value_range"]["mean"] <= expr["value_range"]["max"]
        assert isinstance(expr["value_range"]["std"], float)
        assert summary["labels"] is None

    def test_expression_with_nans_and_zeros(self):
        loader = DataLoader()
        expr = make_expression()
        expr.iloc[0, 0] = np.nan
        expr.iloc[1, 1] = 0.0
        loader.expression_data = expr
        summary = loader.get_data_summary()["expression_data"]
        assert summary["missing_values"] == 1
        assert summary["zero_values"] == 1
        assert summary["missing_percentage"] == pytest.approx(100 / 160)

    def test_labels_summary_with_class_distribution(self):
        loader = loaded_loader()
        summary = loader.get_data_summary()["labels"]
        assert summary["shape"] == (8, 2)
        assert summary["columns"] == ["class_label", "age"]
        assert summary["categorical_columns"] == ["class_label"]
        assert summary["numeric_columns"] == ["age"]
        assert summary["class_distribution"] == {"tumor": 4, "normal": 4}

    def test_labels_summary_without_class_column(self):
        loader = loaded_loader(config={"label_column": "missing_col"})
        summary = loader.get_data_summary()["labels"]
        assert "class_distribution" not in summary

    def test_metadata_and_validation_passed_through(self):
        loader = loaded_loader()
        loader.metadata = {"project": "demo"}
        loader.validation_results = {"status": "valid"}
        summary = loader.get_data_summary()
        assert summary["metadata"] == {"project": "demo"}
        assert summary["validation"] == {"status": "valid"}

    def test_single_sample_single_gene(self):
        loader = DataLoader()
        loader.expression_data = pd.DataFrame({"S00": [1.0]}, index=["GENE0"])
        summary = loader.get_data_summary()["expression_data"]
        assert summary["shape"] == (1, 1)
        assert summary["value_range"]["min"] == pytest.approx(1.0)
        # std of a single observation is NaN
        assert np.isnan(summary["value_range"]["std"])


# --------------------------------------------------------------------------
# save_processed_data
# --------------------------------------------------------------------------
class TestSaveProcessedData:
    def test_creates_directory_and_saves_nothing_when_empty(self, tmp_path):
        out_dir = tmp_path / "nested" / "out"
        saved = DataLoader().save_processed_data(str(out_dir))
        assert saved == {}
        assert out_dir.is_dir()

    def test_saves_expression_and_labels(self, tmp_path):
        loader = loaded_loader()
        saved = loader.save_processed_data(str(tmp_path))
        assert set(saved) == {"expression", "labels"}
        expr_back = pd.read_csv(saved["expression"], sep="\t", index_col=0)
        assert expr_back.shape == (20, 8)
        labels_back = pd.read_csv(saved["labels"], sep="\t", index_col=0)
        assert len(labels_back) == 8

    def test_custom_prefix(self, tmp_path):
        loader = loaded_loader()
        saved = loader.save_processed_data(str(tmp_path), prefix="run42")
        assert saved["expression"].endswith("run42_expression.tsv")
        assert saved["labels"].endswith("run42_labels.tsv")

    def test_saves_metadata_and_validation(self, tmp_path):
        loader = loaded_loader()
        loader.metadata = {"project": "demo", "tags": ["a", "b"]}
        loader.validation_results = {"status": "valid", "issues": [], "warnings": []}
        saved = loader.save_processed_data(str(tmp_path))
        assert set(saved) == {"expression", "labels", "metadata", "validation"}
        with open(saved["metadata"]) as f:
            assert yaml.safe_load(f) == loader.metadata
        with open(saved["validation"]) as f:
            assert yaml.safe_load(f)["status"] == "valid"

    def test_empty_metadata_and_validation_skipped(self, tmp_path):
        loader = loaded_loader()
        loader.metadata = {}
        loader.validation_results = {}
        saved = loader.save_processed_data(str(tmp_path))
        assert "metadata" not in saved
        assert "validation" not in saved

    def test_write_failure_propagates(self, tmp_path):
        loader = DataLoader()
        loader.expression_data = MagicMock()
        loader.expression_data.to_csv.side_effect = OSError("disk full")
        with pytest.raises(OSError, match="disk full"):
            loader.save_processed_data(str(tmp_path))

    # Note: a test asserting yaml.dump raises RepresenterError on numpy-typed
    # validation results was removed -- whether PyYAML raises or silently
    # serializes numpy scalars is version dependent, so it is not a stable
    # assertion. The save path is already covered by the happy-path tests above.


# --------------------------------------------------------------------------
# end-to-end
# --------------------------------------------------------------------------
def test_full_round_trip(tmp_path):
    expr = make_expression(n_genes=25, n_samples=10)
    expr_path = write_csv(tmp_path / "expr.tsv", expr, sep="\t")

    labels = make_labels(n_samples=10, batch=True)
    labels_path = tmp_path / "labels.csv"
    labels.to_csv(labels_path, index=False)

    meta_path = tmp_path / "meta.yaml"
    meta_path.write_text("project: e2e\n")

    loader = DataLoader({"label_column": "class_label", "batch_column": "batch"})
    loader.load_expression_data(expr_path)
    loader.load_labels(str(labels_path))
    loader.load_metadata(str(meta_path))

    validation = loader.validate_data_integrity()
    assert validation["status"] == "valid"

    aligned_expr, aligned_labels = loader.align_data()
    assert aligned_expr.shape == (25, 10)
    assert aligned_labels.shape[0] == 10

    summary = loader.get_data_summary()
    assert summary["expression_data"]["shape"] == (25, 10)
    assert summary["metadata"] == {"project": "e2e"}

    loader.validation_results = {"status": "valid"}
    saved = loader.save_processed_data(str(tmp_path / "out"), prefix="e2e")
    assert set(saved) == {"expression", "labels", "metadata", "validation"}
