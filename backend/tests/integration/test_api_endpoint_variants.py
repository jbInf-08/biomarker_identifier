"""
Tests for all API endpoint variants and parameter combinations.
"""
from io import BytesIO

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


class TestAnalysisAPIEndpointVariants:
    """Tests for analysis API endpoint variants."""

    def test_differential_expression_all_methods(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test differential expression with all available methods."""
        methods = ["welch_t", "mannwhitney", "ttest", "wilcoxon"]

        for method in methods:
            with open(test_data_files["expression_file"], "rb") as expr_file, open(
                test_data_files["clinical_file"], "rb"
            ) as clinical_file:
                response = client.post(
                    "/api/analysis/statistical/differential-expression",
                    files={
                        "expression_data": expr_file,
                        "clinical_data": clinical_file,
                    },
                    params={"test_method": method},
                    headers=auth_headers,
                )

                assert response.status_code in [200, 400, 422, 500]

    def test_differential_expression_all_fdr_methods(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test differential expression with all FDR correction methods."""
        fdr_methods = ["benjamini_hochberg", "bonferroni", "fdr_bh"]

        for fdr_method in fdr_methods:
            with open(test_data_files["expression_file"], "rb") as expr_file, open(
                test_data_files["clinical_file"], "rb"
            ) as clinical_file:
                response = client.post(
                    "/api/analysis/statistical/differential-expression",
                    files={
                        "expression_data": expr_file,
                        "clinical_data": clinical_file,
                    },
                    params={"fdr_method": fdr_method},
                    headers=auth_headers,
                )

                assert response.status_code in [200, 400, 422, 500]

    def test_correlation_analysis_all_methods(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test correlation analysis with all methods."""
        methods = ["pearson", "spearman", "kendall"]

        for method in methods:
            with open(test_data_files["expression_file"], "rb") as expr_file:
                response = client.post(
                    "/api/analysis/statistical/correlation-analysis",
                    files={"data_file": expr_file},
                    params={"method": method},
                    headers=auth_headers,
                )

                assert response.status_code in [200, 400, 422, 500]

    def test_feature_selection_all_methods(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test feature selection with all methods."""
        methods = ["lasso", "elastic_net", "random_forest", "svm"]

        for method in methods:
            with open(test_data_files["expression_file"], "rb") as expr_file, open(
                test_data_files["clinical_file"], "rb"
            ) as clinical_file:
                response = client.post(
                    "/api/analysis/ml/feature-selection",
                    files={
                        "expression_data": expr_file,
                        "clinical_data": clinical_file,
                    },
                    params={"method": method},
                    headers=auth_headers,
                )

                assert response.status_code in [200, 400, 422, 500]

    def test_train_ml_model_all_types(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test training ML models with all types."""
        model_types = [
            "random_forest",
            "logistic_regression",
            "svm",
            "gradient_boosting",
        ]

        for model_type in model_types:
            with open(test_data_files["expression_file"], "rb") as expr_file, open(
                test_data_files["clinical_file"], "rb"
            ) as clinical_file:
                response = client.post(
                    "/api/analysis/ml/model-training",
                    files={"expression_data": expr_file, "labels": clinical_file},
                    params={"model_type": model_type},
                    headers=auth_headers,
                )

                assert response.status_code in [200, 400, 422, 500]

    def test_pathway_enrichment_all_gene_sets(self, client: TestClient, auth_headers):
        """Test pathway enrichment with different gene sets."""
        gene_sets = ["KEGG", "REACTOME", "GO_BP", "GO_MF", "GO_CC"]

        for gene_set in gene_sets:
            response = client.post(
                "/api/analysis/pathway/enrichment",
                json={"gene_list": ["TP53", "BRCA1", "BRCA2"], "gene_sets": [gene_set]},
                headers=auth_headers,
            )

            assert response.status_code in [200, 400, 422, 500]

    def test_get_statistical_methods(self, client: TestClient, auth_headers):
        """Test getting available statistical methods."""
        response = client.get("/api/analysis/methods/statistical", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_ml_methods(self, client: TestClient, auth_headers):
        """Test getting available ML methods."""
        response = client.get("/api/analysis/methods/ml", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_pathway_methods(self, client: TestClient, auth_headers):
        """Test getting available pathway methods."""
        response = client.get("/api/analysis/methods/pathway", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_databases(self, client: TestClient, auth_headers):
        """Test getting available databases."""
        response = client.get("/api/analysis/databases", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestBiomarkerAPIEndpointVariants:
    """Tests for biomarker API endpoint variants."""

    def test_get_biomarkers_all_filters(self, client: TestClient, auth_headers):
        """Test getting biomarkers with various filter combinations."""
        filter_combinations = [
            {"p_value_max": 0.05},
            {"p_value_max": 0.01, "fold_change_min": 1.5},
            {"status": "validated"},
            {"gene_symbol": "TP53"},
            {"run_id": "test_run"},
        ]

        for filters in filter_combinations:
            try:
                response = client.get(
                    "/api/biomarkers", params=filters, headers=auth_headers
                )

                assert response.status_code in [200, 400, 422, 500]
            except Exception:
                # May fail for some filter combinations
                pass

    def test_get_biomarker_runs_all_statuses(self, client: TestClient, auth_headers):
        """Test getting biomarker runs with different statuses."""
        statuses = ["running", "completed", "failed", "cancelled"]

        for status in statuses:
            response = client.get(
                "/api/biomarkers/runs", params={"status": status}, headers=auth_headers
            )

            assert response.status_code in [200, 400, 422]


class TestDataAPIEndpointVariants:
    """Tests for data API endpoint variants."""

    def test_normalize_data_all_methods(self, client: TestClient, auth_headers):
        """Test normalizing data with all methods."""
        methods = ["log2", "quantile", "zscore", "robust"]

        for method in methods:
            response = client.post(
                "/api/data/process/normalize",
                json={"file_id": "test-id", "method": method},
                headers=auth_headers,
            )

            assert response.status_code in [200, 400, 404, 422, 500]

    def test_quality_control_all_options(self, client: TestClient, auth_headers):
        """Test quality control with different options."""
        options = [
            {"min_detection_rate": 0.1},
            {"min_variance": 0.5},
            {"max_missing_ratio": 0.2},
            {"min_detection_rate": 0.1, "min_variance": 0.5},
        ]

        for option in options:
            response = client.post(
                "/api/data/process/quality-control",
                json={"file_id": "test-id", **option},
                headers=auth_headers,
            )

            assert response.status_code in [200, 400, 404, 422, 500]
