"""
Comprehensive unit tests for quality control pipeline.
"""
import numpy as np
import pandas as pd
import pytest

from app.pipelines.qc import QualityControl


class TestQualityControl:
    """Test cases for QualityControl."""

    def test_qc_initialization(self):
        """Test QualityControl initialization."""
        qc = QualityControl()
        assert qc is not None
        assert qc.config == {}

    def test_perform_qc_analysis(self, test_data_files):
        """Test performing QC analysis."""
        qc = QualityControl()

        # Load expression data
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        # Load labels
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        results = qc.perform_qc_analysis(expression_data, labels=labels)

        assert results is not None
        assert "basic_qc" in results
        assert "sample_qc" in results
        assert "gene_qc" in results
        assert "summary" in results

    def test_calculate_basic_qc_metrics(self, test_data_files):
        """Test calculating basic QC metrics."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        metrics = qc._calculate_basic_qc_metrics(expression_data)
        assert isinstance(metrics, dict)
        assert "n_genes" in metrics
        assert "n_samples" in metrics
        assert "missing_values" in metrics

    def test_calculate_sample_qc_metrics(self, test_data_files):
        """Test calculating sample QC metrics."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        sample_qc = qc._calculate_sample_qc_metrics(expression_data)
        assert isinstance(sample_qc, pd.DataFrame)
        assert len(sample_qc) == expression_data.shape[1]
        assert "library_size" in sample_qc.columns

    def test_calculate_gene_qc_metrics(self, test_data_files):
        """Test calculating gene QC metrics."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        gene_qc = qc._calculate_gene_qc_metrics(expression_data)
        assert isinstance(gene_qc, pd.DataFrame)
        assert len(gene_qc) == expression_data.shape[0]
        assert "mean_expression" in gene_qc.columns

    def test_analyze_distributions(self, test_data_files):
        """Test analyzing distributions."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        distributions = qc._analyze_distributions(expression_data)
        assert isinstance(distributions, dict)
        assert "sample_distributions" in distributions
        assert "gene_distributions" in distributions

    def test_perform_dimensionality_reduction(self, test_data_files):
        """Test performing dimensionality reduction."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        # Need at least 3 samples for PCA
        if expression_data.shape[1] >= 3:
            labels_df = pd.read_csv(test_data_files["clinical_file"])
            labels = pd.Series(
                labels_df["class_label"].values, index=labels_df["sample_id"]
            )

            dim_red = qc._perform_dimensionality_reduction(
                expression_data, labels=labels
            )
            assert isinstance(dim_red, dict)
            assert "pca" in dim_red

    def test_detect_outliers(self, test_data_files):
        """Test detecting outliers."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        sample_qc = qc._calculate_sample_qc_metrics(expression_data)
        gene_qc = qc._calculate_gene_qc_metrics(expression_data)

        outliers = qc._detect_outliers(expression_data, sample_qc, gene_qc)
        assert isinstance(outliers, dict)
        assert "samples" in outliers
        assert "genes" in outliers

    def test_filter_data(self, test_data_files):
        """Test filtering data."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)

        filtered_data, summary = qc.filter_data(
            expression_data,
            min_detection_rate=0.1,
            min_variance=0.0,
            max_missing_ratio=0.5,
        )

        assert isinstance(filtered_data, pd.DataFrame)
        assert isinstance(summary, dict)
        assert "original_shape" in summary
        assert "filtered_shape" in summary

    def test_get_qc_summary(self, test_data_files):
        """Test getting QC summary."""
        qc = QualityControl()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        qc.perform_qc_analysis(expression_data, labels=labels)
        summary = qc.get_qc_summary()

        assert isinstance(summary, dict)
        assert "status" in summary
