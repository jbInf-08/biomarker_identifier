"""
Comprehensive unit tests for statistical analysis.
"""
import numpy as np
import pandas as pd
import pytest

from app.data_processing.statistical_analysis import StatisticalAnalysis


class TestStatisticalAnalysis:
    """Test cases for StatisticalAnalysis."""

    def test_statistical_analysis_initialization(self):
        """Test StatisticalAnalysis initialization."""
        stats = StatisticalAnalysis()
        assert stats is not None
        assert stats.config == {}

    def test_differential_expression_analysis_t_test(self, test_data_files):
        """Test differential expression analysis with t-test."""
        stats = StatisticalAnalysis()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        results = stats.differential_expression_analysis(
            expression_data, labels, method="t_test"
        )

        assert isinstance(results, dict)
        assert "significant_features" in results or "results" in results

    def test_differential_expression_analysis_wilcoxon(self, test_data_files):
        """Test differential expression analysis with Wilcoxon."""
        stats = StatisticalAnalysis()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        results = stats.differential_expression_analysis(
            expression_data, labels, method="wilcoxon"
        )

        assert isinstance(results, dict)

    def test_differential_expression_analysis_anova(self, test_data_files):
        """Test differential expression analysis with ANOVA."""
        stats = StatisticalAnalysis()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        # Create multiclass labels
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        pattern = (["A", "B", "C"] * (len(labels_df) // 3 + 1))[: len(labels_df)]
        labels = pd.Series(pattern, index=labels_df["sample_id"].values[: len(pattern)])

        results = stats.differential_expression_analysis(
            expression_data, labels, method="anova"
        )

        assert isinstance(results, dict)

    def test_rank_features(self, test_data_files):
        """Test ranking features."""
        stats = StatisticalAnalysis()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        results = stats.differential_expression_analysis(
            expression_data, labels, method="t_test"
        )
        ranked = stats.rank_features(results)

        assert isinstance(ranked, dict) or isinstance(ranked, list)

    def test_volcano_plot_data(self, test_data_files):
        """Test generating volcano plot data."""
        stats = StatisticalAnalysis()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        results = stats.differential_expression_analysis(
            expression_data, labels, method="t_test"
        )
        volcano_data = stats.volcano_plot_data(results)

        assert isinstance(volcano_data, dict)
