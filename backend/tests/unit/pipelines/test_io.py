"""
Comprehensive unit tests for pipeline I/O operations.
"""
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.pipelines.io import DataIO


class TestDataIO:
    """Test cases for DataIO."""

    def test_data_io_initialization(self):
        """Test DataIO initialization."""
        data_io = DataIO()
        assert data_io is not None
        assert data_io.config == {}

    def test_data_io_initialization_with_config(self):
        """Test DataIO initialization with config."""
        config = {"test": "value"}
        data_io = DataIO(config=config)
        assert data_io.config == config

    def test_load_data_success(self, test_data_files):
        """Test loading data successfully."""
        data_io = DataIO()

        result = data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        assert result is not None
        assert "expression_data" in result
        assert "labels" in result
        assert "validation_results" in result
        assert isinstance(result["expression_data"], pd.DataFrame)
        assert isinstance(result["labels"], pd.Series)

    def test_load_data_with_metadata(self, test_data_files):
        """Test loading data with metadata file."""
        data_io = DataIO()

        # Create temporary metadata file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json

            json.dump({"project": "test", "investigator": "test"}, f)
            metadata_path = f.name

        try:
            result = data_io.load_data(
                expression_file=test_data_files["expression_file"],
                labels_file=test_data_files["clinical_file"],
                metadata_file=metadata_path,
                label_column="group",
            )

            assert result is not None
            assert "metadata" in result
        finally:
            os.unlink(metadata_path)

    def test_load_expression_data_csv(self, test_data_files):
        """Test loading expression data from CSV."""
        data_io = DataIO()
        result = data_io._load_expression_data(test_data_files["expression_file"])
        assert isinstance(result, pd.DataFrame)
        assert result.shape[0] > 0
        assert result.shape[1] > 0

    def test_load_expression_data_tsv(self):
        """Test loading expression data from TSV."""
        data_io = DataIO()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False) as f:
            df = pd.DataFrame(
                {"GENE001": [1.5, 2.3, 0.8], "GENE002": [1.8, 2.1, 0.9]},
                index=["Sample1", "Sample2", "Sample3"],
            )
            df.to_csv(f.name, sep="\t")
            temp_path = f.name

        try:
            result = data_io._load_expression_data(temp_path)
            assert isinstance(result, pd.DataFrame)
        finally:
            os.unlink(temp_path)

    def test_load_labels_success(self, test_data_files):
        """Test loading labels successfully."""
        data_io = DataIO()
        result = data_io._load_labels(test_data_files["clinical_file"])
        assert isinstance(result, pd.Series)
        assert len(result) > 0

    def test_load_labels_missing_column(self):
        """Test loading labels with missing column."""
        data_io = DataIO()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df = pd.DataFrame({"sample_id": ["S1", "S2"], "wrong_column": ["A", "B"]})
            df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            with pytest.raises(ValueError):
                data_io._load_labels(temp_path, label_column="class_label")
        finally:
            os.unlink(temp_path)

    def test_load_metadata_json(self):
        """Test loading metadata from JSON."""
        data_io = DataIO()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            import json

            json.dump({"key": "value"}, f)
            temp_path = f.name

        try:
            result = data_io._load_metadata(temp_path)
            assert isinstance(result, dict)
            assert result["key"] == "value"
        finally:
            os.unlink(temp_path)

    def test_load_metadata_yaml(self):
        """Test loading metadata from YAML."""
        data_io = DataIO()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\n")
            temp_path = f.name

        try:
            result = data_io._load_metadata(temp_path)
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_validate_data_success(self, test_data_files):
        """Test validating data successfully."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        validation_results = data_io._validate_data()
        assert validation_results is not None
        assert "status" in validation_results
        assert "errors" in validation_results
        assert "warnings" in validation_results

    def test_check_data_types(self, test_data_files):
        """Test checking data types."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        validation_results = {"errors": [], "warnings": [], "checks": {}}
        data_io._check_data_types(validation_results)
        assert "data_types" in validation_results["checks"]

    def test_check_sample_intersection(self, test_data_files):
        """Test checking sample intersection."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        validation_results = {"errors": [], "warnings": [], "checks": {}}
        data_io._check_sample_intersection(validation_results)
        assert "sample_intersection" in validation_results["checks"]

    def test_check_duplicates(self, test_data_files):
        """Test checking for duplicates."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        validation_results = {"errors": [], "warnings": [], "checks": {}}
        data_io._check_duplicates(validation_results)
        assert "duplicates" in validation_results["checks"]

    def test_check_missing_values(self, test_data_files):
        """Test checking for missing values."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        validation_results = {"errors": [], "warnings": [], "checks": {}}
        data_io._check_missing_values(validation_results)
        assert "missing_values" in validation_results["checks"]

    def test_check_data_quality(self, test_data_files):
        """Test checking data quality."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        validation_results = {"errors": [], "warnings": [], "checks": {}}
        data_io._check_data_quality(validation_results)
        assert "data_quality" in validation_results["checks"]

    def test_check_label_distribution(self, test_data_files):
        """Test checking label distribution."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        validation_results = {"errors": [], "warnings": [], "checks": {}}
        data_io._check_label_distribution(validation_results)
        assert "label_distribution" in validation_results["checks"]

    def test_generate_dataset_hash(self, test_data_files):
        """Test generating dataset hash."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        hash_value = data_io._generate_dataset_hash()
        assert isinstance(hash_value, str)
        assert len(hash_value) > 0

    def test_generate_data_summary(self, test_data_files):
        """Test generating data summary."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        summary = data_io._generate_data_summary()
        assert isinstance(summary, dict)
        assert "timestamp" in summary or "dataset_hash" in summary

    def test_map_gene_ids(self, test_data_files):
        """Test mapping gene IDs."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        mapped_data = data_io.map_gene_ids(
            expression_data=data_io.expression_data,
            from_type="ensembl",
            to_type="symbol",
        )

        assert isinstance(mapped_data, pd.DataFrame)

    def test_save_processed_data_tsv(self, test_data_files):
        """Test saving processed data as TSV."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.tsv")
            result = data_io.save_processed_data(
                data=data_io.expression_data, output_path=output_path, format="tsv"
            )

            assert result == output_path
            assert os.path.exists(output_path)

    def test_save_processed_data_csv(self, test_data_files):
        """Test saving processed data as CSV."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.csv")
            result = data_io.save_processed_data(
                data=data_io.expression_data, output_path=output_path, format="csv"
            )

            assert result == output_path
            assert os.path.exists(output_path)

    def test_get_validation_summary(self, test_data_files):
        """Test getting validation summary."""
        data_io = DataIO()
        data_io.load_data(
            expression_file=test_data_files["expression_file"],
            labels_file=test_data_files["clinical_file"],
            label_column="group",
        )

        summary = data_io.get_validation_summary()
        assert isinstance(summary, dict)
        assert "status" in summary
