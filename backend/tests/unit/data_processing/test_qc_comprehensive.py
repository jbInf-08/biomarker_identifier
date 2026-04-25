"""
Comprehensive tests for quality control covering all methods and error paths.
"""
import numpy as np
import pandas as pd
import pytest

from app.pipelines.qc import QualityControl


class TestQualityControlComprehensive:
    """Comprehensive tests for QualityControl."""

    def test_perform_qc_analysis_complete(self):
        """Test complete QC analysis with all components."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(100, 30),
            index=[f"GENE{i:03d}" for i in range(100)],
            columns=[f"SAMPLE{i:03d}" for i in range(30)],
        )
        labels = pd.Series(np.random.choice([0, 1], 30))

        results = qc.perform_qc_analysis(expression_data, labels=labels)

        assert isinstance(results, dict)
        assert "basic_qc" in results
        assert "sample_qc" in results
        assert "gene_qc" in results
        assert "distribution_qc" in results
        assert "outliers" in results
        assert "summary" in results

    def test_calculate_basic_qc_metrics(self):
        """Test calculating basic QC metrics."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(50, 20),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(20)],
        )

        metrics = qc._calculate_basic_qc_metrics(expression_data)

        assert isinstance(metrics, dict)
        assert "n_genes" in metrics
        assert "n_samples" in metrics

    def test_calculate_sample_qc_metrics(self):
        """Test calculating sample QC metrics."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(50, 20),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(20)],
        )

        metrics = qc._calculate_sample_qc_metrics(expression_data)

        assert isinstance(metrics, (dict, pd.DataFrame))

    def test_calculate_gene_qc_metrics(self):
        """Test calculating gene QC metrics."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(50, 20),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(20)],
        )

        metrics = qc._calculate_gene_qc_metrics(expression_data)

        assert isinstance(metrics, (dict, pd.DataFrame))

    def test_analyze_distributions(self):
        """Test analyzing distributions."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(50, 20),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(20)],
        )

        distributions = qc._analyze_distributions(expression_data)

        assert isinstance(distributions, dict)

    def test_perform_dimensionality_reduction(self):
        """Test performing dimensionality reduction."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(50, 20),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(20)],
        )
        labels = pd.Series(np.random.choice([0, 1], 20))

        dim_reduction = qc._perform_dimensionality_reduction(
            expression_data, labels=labels
        )

        assert isinstance(dim_reduction, dict)

    def test_detect_outliers(self):
        """Test detecting outliers."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(50, 20),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(20)],
        )

        sample_qc = qc._calculate_sample_qc_metrics(expression_data)
        gene_qc = qc._calculate_gene_qc_metrics(expression_data)

        outliers = qc._detect_outliers(expression_data, sample_qc, gene_qc)

        assert isinstance(outliers, dict)

    def test_filter_data_all_parameters(self):
        """Test filtering data with all parameter combinations."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(100, 30),
            index=[f"GENE{i:03d}" for i in range(100)],
            columns=[f"SAMPLE{i:03d}" for i in range(30)],
        )

        parameter_combinations = [
            {"min_detection_rate": 0.1},
            {"min_variance": 0.5},
            {"max_missing_ratio": 0.2},
            {"min_detection_rate": 0.1, "min_variance": 0.5},
            {"min_detection_rate": 0.2, "max_missing_ratio": 0.3},
            {"min_variance": 0.3, "max_missing_ratio": 0.4},
        ]

        for params in parameter_combinations:
            filtered, summary = qc.filter_data(expression_data, **params)
            assert isinstance(filtered, pd.DataFrame)
            assert isinstance(summary, dict)

    def test_generate_qc_plots(self):
        """Test generating QC plots."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(50, 20),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(20)],
        )
        labels = pd.Series(np.random.choice([0, 1], 20))

        results = {
            "basic_qc": {},
            "sample_qc": {},
            "gene_qc": {},
            "distribution_qc": {},
        }

        plots = qc._generate_qc_plots(
            expression_data, labels=labels, batch_info=None, qc_results=results
        )

        assert isinstance(plots, dict)

    def test_generate_qc_summary(self):
        """Test generating QC summary."""
        qc = QualityControl()

        results = {
            "basic_qc": {
                "n_genes": 100,
                "n_samples": 30,
                "missing_ratio": 0.0,
                "zero_ratio": 0.0,
                "negative_values": 0,
            },
            "sample_qc": {},
            "gene_qc": {},
            "outliers": {"samples": {}, "genes": {}},
        }

        summary = qc._generate_qc_summary(results)

        assert isinstance(summary, dict)
        assert "status" in summary

    def test_qc_analysis_with_batch_info(self):
        """Test QC analysis with batch information."""
        qc = QualityControl()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(50, 20),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(20)],
        )
        batch_info = pd.Series(np.random.choice(["BATCH1", "BATCH2"], 20))

        results = qc.perform_qc_analysis(expression_data, batch_info=batch_info)

        assert isinstance(results, dict)

    def test_qc_analysis_insufficient_samples(self):
        """Test QC analysis with insufficient samples for PCA."""
        qc = QualityControl()

        np.random.seed(42)
        # Only 2 samples - not enough for PCA
        expression_data = pd.DataFrame(
            np.random.randn(50, 2),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(2)],
        )

        results = qc.perform_qc_analysis(expression_data)

        assert isinstance(results, dict)
        # Should not have dimensionality_reduction or handle gracefully
        assert "dimensionality_reduction" not in results or isinstance(
            results.get("dimensionality_reduction"), dict
        )
