"""
Unit tests for survival analysis module.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.analysis.survival_analysis import SurvivalAnalyzer


@pytest.fixture
def sample_survival_data():
    """Create sample survival data for testing."""
    np.random.seed(42)
    n_samples = 100

    data = pd.DataFrame(
        {
            "overall_survival_time": np.random.exponential(scale=1000, size=n_samples),
            "overall_survival_event": np.random.binomial(1, 0.7, size=n_samples),
            "age": np.random.normal(65, 15, size=n_samples),
            "GENE_001": np.random.normal(0, 1, size=n_samples),
            "GENE_002": np.random.normal(0, 1, size=n_samples),
            "GENE_003": np.random.normal(0, 1, size=n_samples),
        }
    )

    # Ensure positive survival times
    data["overall_survival_time"] = np.abs(data["overall_survival_time"]) + 1

    return data


class TestSurvivalAnalyzer:
    """Test SurvivalAnalyzer class."""

    def test_init(self):
        """Test SurvivalAnalyzer initialization."""
        analyzer = SurvivalAnalyzer()
        assert analyzer.config == {}
        assert analyzer.survival_data is None
        assert analyzer.cox_results == {}
        assert analyzer.km_results == {}

    def test_load_survival_data(self, sample_survival_data, tmp_path):
        """Test loading survival data."""
        analyzer = SurvivalAnalyzer()

        # Save to temporary file
        filepath = tmp_path / "clinical.csv"
        sample_survival_data.to_csv(filepath, index=False)

        data = analyzer.load_survival_data(
            str(filepath),
            time_column="overall_survival_time",
            event_column="overall_survival_event",
        )

        assert isinstance(data, pd.DataFrame)
        assert len(data) > 0
        assert analyzer.survival_data is not None

    def test_prepare_survival_data(self, sample_survival_data):
        """Test preparing survival data."""
        analyzer = SurvivalAnalyzer()
        analyzer.survival_data = sample_survival_data

        prepared = analyzer.prepare_survival_data(
            time_column="overall_survival_time",
            event_column="overall_survival_event",
            covariates=["age"],
        )

        assert isinstance(prepared, pd.DataFrame)
        assert "overall_survival_time" in prepared.columns
        assert "overall_survival_event" in prepared.columns

    def test_cox_proportional_hazards(self, sample_survival_data):
        """Test Cox proportional hazards analysis."""
        analyzer = SurvivalAnalyzer()
        analyzer.survival_data = sample_survival_data

        results = analyzer.cox_proportional_hazards(
            time_column="overall_survival_time",
            event_column="overall_survival_event",
            covariates=["age", "GENE_001"],
        )

        assert "model" in results
        assert "summary" in results
        assert "concordance_index" in results
        assert "n_events" in results
        assert "n_samples" in results

    def test_univariate_cox_analysis(self, sample_survival_data):
        """Test univariate Cox analysis."""
        analyzer = SurvivalAnalyzer()
        analyzer.survival_data = sample_survival_data

        results = analyzer.univariate_cox_analysis(
            time_column="overall_survival_time",
            event_column="overall_survival_event",
            gene_columns=["GENE_001", "GENE_002", "GENE_003"],
        )

        assert isinstance(results, pd.DataFrame)
        if len(results) > 0:
            assert "gene" in results.columns
            assert "p_value" in results.columns
            assert "coef" in results.columns

    def test_kaplan_meier_analysis(self, sample_survival_data):
        """Test Kaplan-Meier analysis."""
        analyzer = SurvivalAnalyzer()
        analyzer.survival_data = sample_survival_data

        # Create groups based on median
        median_value = sample_survival_data["GENE_001"].median()
        groups = {
            "Low": sample_survival_data["GENE_001"] <= median_value,
            "High": sample_survival_data["GENE_001"] > median_value,
        }

        results = analyzer.kaplan_meier_analysis(
            time_column="overall_survival_time",
            event_column="overall_survival_event",
            group_column="GENE_001",
            groups=groups,
        )

        assert "Low" in results or "High" in results

    def test_survival_biomarker_discovery(self, sample_survival_data):
        """Test survival biomarker discovery."""
        analyzer = SurvivalAnalyzer()
        analyzer.survival_data = sample_survival_data

        biomarkers = analyzer.survival_biomarker_discovery(
            time_column="overall_survival_time",
            event_column="overall_survival_event",
            gene_columns=["GENE_001", "GENE_002", "GENE_003"],
            top_n=10,
        )

        assert isinstance(biomarkers, pd.DataFrame)

    def test_get_survival_summary(self, sample_survival_data):
        """Test getting survival summary."""
        analyzer = SurvivalAnalyzer()
        analyzer.survival_data = sample_survival_data

        summary = analyzer.get_survival_summary()

        assert "survival_data_loaded" in summary
        assert "cox_analyses_performed" in summary
        assert "km_analyses_performed" in summary
        assert "analysis_timestamp" in summary
