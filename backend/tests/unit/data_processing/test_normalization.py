"""
Comprehensive unit tests for normalization.
"""
import numpy as np
import pandas as pd
import pytest

from app.data_processing.normalization import Normalization


class TestNormalization:
    """Test cases for Normalization."""

    def test_normalization_initialization(self):
        """Test Normalization initialization."""
        norm = Normalization()
        assert norm is not None
        assert norm.config == {}

    def test_normalize_data_log_cpm(self, test_data_files):
        """Test log CPM normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm.normalize_data(expression_data, method="log_cpm")
        assert isinstance(normalized, pd.DataFrame)
        assert normalized.shape == expression_data.shape

    def test_normalize_data_quantile(self, test_data_files):
        """Test quantile normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm.normalize_data(expression_data, method="quantile")
        assert isinstance(normalized, pd.DataFrame)

    def test_normalize_data_z_score(self, test_data_files):
        """Test z-score normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm.normalize_data(expression_data, method="z_score")
        assert isinstance(normalized, pd.DataFrame)

    def test_normalize_data_robust_z_score(self, test_data_files):
        """Test robust z-score normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm.normalize_data(expression_data, method="robust_z_score")
        assert isinstance(normalized, pd.DataFrame)

    def test_normalize_data_min_max(self, test_data_files):
        """Test min-max normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm.normalize_data(expression_data, method="min_max")
        assert isinstance(normalized, pd.DataFrame)

    def test_normalize_data_median_ratio(self, test_data_files):
        """Test median ratio normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm.normalize_data(expression_data, method="median_ratio")
        assert isinstance(normalized, pd.DataFrame)

    def test_normalize_data_tmm(self, test_data_files):
        """Test TMM normalization."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        normalized = norm.normalize_data(expression_data, method="tmm")
        assert isinstance(normalized, pd.DataFrame)

    def test_normalize_data_unknown_method(self, test_data_files):
        """Test normalization with unknown method."""
        norm = Normalization()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        with pytest.raises(ValueError):
            norm.normalize_data(expression_data, method="unknown_method")
