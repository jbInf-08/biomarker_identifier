"""
Comprehensive unit tests for statistical pipeline.
"""
import os

import numpy as np
import pandas as pd
import pytest

from app.pipelines.stats import StatisticalPipeline


class TestStatisticalPipeline:
    """Test cases for StatisticalPipeline."""

    def test_statistical_pipeline_initialization(self):
        """Test StatisticalPipeline initialization."""
        pipeline = StatisticalPipeline()
        assert pipeline is not None
        assert pipeline.config == {}

    def test_run_statistical_analysis_binary(self, test_data_files):
        """Test running statistical analysis for binary classification."""
        pipeline = StatisticalPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        results = pipeline.run_statistical_analysis(
            expression_data, labels, analysis_methods=["t_test", "wilcoxon"]
        )

        assert results is not None
        assert "method_results" in results
        assert "summary" in results

    def test_run_statistical_analysis_multiclass(self, test_data_files):
        """Test running statistical analysis for multiclass."""
        pipeline = StatisticalPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        # Create multiclass labels
        pattern = (["A", "B", "C"] * (len(labels_df) // 3 + 1))[: len(labels_df)]
        labels = pd.Series(pattern, index=labels_df["sample_id"].values[: len(pattern)])

        results = pipeline.run_statistical_analysis(
            expression_data, labels, analysis_methods=["anova", "kruskal"]
        )

        assert results is not None
        assert "method_results" in results

    def test_generate_analysis_summary(self, test_data_files):
        """Test generating analysis summary."""
        pipeline = StatisticalPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        results = pipeline.run_statistical_analysis(expression_data, labels)
        summary = pipeline._generate_analysis_summary(results)

        assert isinstance(summary, dict)
        assert "n_genes" in summary
        assert "n_samples" in summary

    def test_get_significant_features(self, test_data_files):
        """Test getting significant features."""
        pipeline = StatisticalPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        pipeline.run_statistical_analysis(expression_data, labels)
        features = pipeline.get_significant_features(top_n=10)

        assert isinstance(features, dict)

    def test_get_top_features(self, test_data_files):
        """Test getting top features."""
        pipeline = StatisticalPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        pipeline.run_statistical_analysis(expression_data, labels)
        top_features = pipeline.get_top_features(top_n=10)

        assert isinstance(top_features, dict)

    def test_welch_ttest(self, test_data_files):
        """Test Welch t-test."""
        pipeline = StatisticalPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        # Ensure binary labels
        unique_labels = labels.unique()
        if len(unique_labels) == 2:
            result = pipeline.welch_ttest(expression_data, labels)
            assert isinstance(result, pd.DataFrame)
            assert "pvalue" in result.columns
            assert "log2fc" in result.columns

    def test_save_analysis_results_json(self, test_data_files):
        """Test saving analysis results as JSON."""
        pipeline = StatisticalPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        pipeline.run_statistical_analysis(expression_data, labels)

        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "results.json")
            result = pipeline.save_analysis_results(output_path, format="json")

            assert result == output_path
            assert os.path.exists(output_path)

    def test_save_analysis_results_csv(self, test_data_files):
        """Test saving analysis results as CSV."""
        pipeline = StatisticalPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        pipeline.run_statistical_analysis(expression_data, labels)

        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "results.csv")
            result = pipeline.save_analysis_results(output_path, format="csv")

            assert result == output_path
            assert os.path.exists(output_path)

    def test_get_analysis_summary(self, test_data_files):
        """Test getting analysis summary."""
        pipeline = StatisticalPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        pipeline.run_statistical_analysis(expression_data, labels)
        summary = pipeline.get_analysis_summary()

        assert isinstance(summary, dict)
        assert "status" in summary
