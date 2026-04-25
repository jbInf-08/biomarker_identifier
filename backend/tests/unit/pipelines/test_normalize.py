"""
Comprehensive unit tests for normalization pipeline.
"""
import os

import numpy as np
import pandas as pd
import pytest

from app.pipelines.normalize import Normalization


class TestNormalization:
    """Test cases for Normalization."""

    def test_normalization_initialization(self):
        """Test Normalization initialization."""
        norm = Normalization()
        assert norm is not None
        assert norm.config == {}

    def test_normalize_data_log2(self, test_data_files):
        """Test normalizing data with log2 transformation."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        results = norm.normalize_data(expression_data, normalization_method="log2")

        assert results is not None
        assert "original_data" in results
        assert "final_data" in results
        assert "summary" in results

    def test_normalize_data_none(self, test_data_files):
        """Test normalizing data with no transformation."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        results = norm.normalize_data(expression_data, normalization_method="none")

        assert results is not None
        assert "final_data" in results

    def test_apply_transformation_log2(self, test_data_files):
        """Test applying log2 transformation."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        transformed = norm._apply_transformation(expression_data, method="log2")
        assert isinstance(transformed, pd.DataFrame)
        assert transformed.shape == expression_data.shape

    def test_apply_final_normalization_zscore(self, test_data_files):
        """Test applying z-score normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm._apply_final_normalization(
            expression_data, final_normalization="zscore"
        )
        assert isinstance(normalized, pd.DataFrame)

    def test_apply_final_normalization_robust_zscore(self, test_data_files):
        """Test applying robust z-score normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm._apply_final_normalization(
            expression_data, final_normalization="robust_zscore"
        )
        assert isinstance(normalized, pd.DataFrame)

    def test_quantile_normalize(self, test_data_files):
        """Test quantile normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm._quantile_normalize(expression_data)
        assert isinstance(normalized, pd.DataFrame)
        assert normalized.shape == expression_data.shape

    def test_median_ratio_normalize(self, test_data_files):
        """Test median ratio normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm._median_ratio_normalize(expression_data)
        assert isinstance(normalized, pd.DataFrame)
        assert normalized.shape == expression_data.shape

    def test_generate_normalization_summary(self, test_data_files):
        """Test generating normalization summary."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        results = norm.normalize_data(expression_data, normalization_method="log2")
        summary = norm._generate_normalization_summary(results)

        assert isinstance(summary, dict)
        assert "steps_applied" in summary
        assert "data_statistics" in summary

    def test_get_normalization_summary(self, test_data_files):
        """Test getting normalization summary."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        norm.normalize_data(expression_data, normalization_method="log2")
        summary = norm.get_normalization_summary()

        assert isinstance(summary, dict)
        assert "status" in summary

    def test_save_normalized_data(self, test_data_files):
        """Test saving normalized data."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        norm.normalize_data(expression_data, normalization_method="log2")

        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "normalized.tsv")
            result = norm.save_normalized_data(output_path, format="tsv")

            assert result == output_path
            assert os.path.exists(output_path)
