"""
Comprehensive unit tests for ML selection pipeline.
"""
import numpy as np
import pandas as pd
import pytest

from app.pipelines.ml_select import MLSelectionPipeline


class TestMLSelectionPipeline:
    """Test cases for MLSelectionPipeline."""

    def test_ml_selection_initialization(self):
        """Test MLSelectionPipeline initialization."""
        pipeline = MLSelectionPipeline()
        assert pipeline is not None
        assert pipeline.config == {}

    def test_consensus_includes_flat_stability_and_ensemble_buckets(self):
        """Stability/ensemble attach a single result dict; consensus must still aggregate."""
        pipeline = MLSelectionPipeline()
        stub = {
            "method_results": {
                "filter": {
                    "f_test": {
                        "method": "f_test",
                        "selected_features": ["ENSG1", "ENSG2"],
                    },
                },
                "stability": {
                    "method": "stability_selection",
                    "selected_features": ["ENSG1", "ENSG3"],
                },
                "ensemble": {
                    "method": "ensemble",
                    "selected_features": ["ENSG1"],
                },
            }
        }
        consensus = pipeline._generate_consensus_features(stub)
        assert consensus["consensus_scores"]
        assert "stability" in consensus["method_features"]
        assert "ensemble" in consensus["method_features"]
        assert "filter_f_test" in consensus["method_features"]

    def test_run_ml_selection(self, test_data_files):
        """Test running ML selection."""
        pipeline = MLSelectionPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        results = pipeline.run_ml_selection(
            expression_data,
            labels,
            selection_methods=["f_test", "mutual_info"],
            n_features=50,
        )

        assert results is not None
        assert "method_results" in results
        assert "consensus_features" in results

    def test_get_selected_features(self, test_data_files):
        """Test getting selected features."""
        pipeline = MLSelectionPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        pipeline.run_ml_selection(expression_data, labels, n_features=50)
        features = pipeline.get_selected_features(top_n=20)

        assert isinstance(features, list) or isinstance(features, dict)

    def test_get_selection_summary(self, test_data_files):
        """Test getting selection summary."""
        pipeline = MLSelectionPipeline()
        expression_data = pd.read_csv(test_data_files["expression_file"], index_col=0)
        labels_df = pd.read_csv(test_data_files["clinical_file"])
        labels = pd.Series(
            labels_df["class_label"].values, index=labels_df["sample_id"]
        )

        pipeline.run_ml_selection(expression_data, labels, n_features=50)
        summary = pipeline.get_selection_summary()

        assert isinstance(summary, dict)
