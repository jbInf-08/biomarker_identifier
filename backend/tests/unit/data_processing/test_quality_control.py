"""
Comprehensive unit tests for quality control.
"""
import os

import numpy as np
import pandas as pd
import pytest

from app.data_processing.quality_control import QualityControl


class TestQualityControl:
    """Test cases for QualityControl."""

    def test_quality_control_initialization(self):
        """Test QualityControl initialization."""
        qc = QualityControl()
        assert qc is not None
        assert qc.config == {}

    def test_calculate_qc_metrics(self, test_data_files):
        """Test calculating QC metrics."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        metrics = qc.calculate_qc_metrics(expression_data)
        assert isinstance(metrics, dict)
        assert "data_summary" in metrics
        assert "sample_metrics" in metrics
        assert "gene_metrics" in metrics

    def test_filter_low_quality_samples(self, test_data_files):
        """Test filtering low quality samples."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        filtered = qc.filter_low_quality_samples(
            expression_data, min_library_size=1000, min_detected_genes=100
        )

        assert isinstance(filtered, pd.DataFrame)
        assert filtered.shape[1] <= expression_data.shape[1]

    def test_filter_low_quality_genes(self, test_data_files):
        """Test filtering low quality genes."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        filtered = qc.filter_low_quality_genes(
            expression_data, min_variance=0.1, min_detection_rate=0.1
        )

        assert isinstance(filtered, pd.DataFrame)
        assert filtered.shape[0] <= expression_data.shape[0]

    def test_generate_qc_report(self, test_data_files):
        """Test generating QC report."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        qc.calculate_qc_metrics(expression_data)

        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            result = qc.generate_qc_report(temp_dir, prefix="qc")
            expected = os.path.join(temp_dir, "qc_report.html")

            assert os.path.normpath(result) == os.path.normpath(expected)
            assert os.path.exists(expected)
