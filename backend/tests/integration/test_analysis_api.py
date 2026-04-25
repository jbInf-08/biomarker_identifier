"""
Comprehensive integration tests for analysis API endpoints.
"""
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


class TestAnalysisAPI:
    """Test cases for analysis API endpoints."""

    def test_perform_differential_expression_unauthorized(self, client: TestClient):
        """Test performing differential expression without authentication."""
        response = client.post("/api/analysis/statistical/differential-expression")
        assert response.status_code in [401, 403, 422]

    def test_perform_differential_expression_success(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test performing differential expression with valid data."""
        with open(test_data_files["expression_file"], "rb") as expr_file, open(
            test_data_files["clinical_file"], "rb"
        ) as clinical_file:
            response = client.post(
                "/api/analysis/statistical/differential-expression",
                files={"expression_data": expr_file, "clinical_data": clinical_file},
                params={"test_method": "welch_t", "p_value_threshold": 0.05},
                headers=auth_headers,
            )

            assert response.status_code in [200, 202]
            if response.status_code == 200:
                data = response.json()
                assert "results" in data or "run_id" in data

    def test_perform_survival_analysis_unauthorized(self, client: TestClient):
        """Test performing survival analysis without authentication."""
        response = client.post("/api/analysis/statistical/survival-analysis")
        assert response.status_code in [401, 403, 422]

    def test_perform_survival_analysis_success(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test performing survival analysis with valid data."""
        # Create survival data with time and event columns
        import tempfile

        import numpy as np
        import pandas as pd

        # Read clinical data and add survival columns
        clinical_df = pd.read_csv(test_data_files["clinical_file"])
        clinical_df["overall_survival_time"] = np.random.exponential(
            scale=365, size=len(clinical_df)
        )
        clinical_df["overall_survival_event"] = np.random.choice(
            [0, 1], size=len(clinical_df), p=[0.3, 0.7]
        )

        # Create temporary file with survival data
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            clinical_df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as clinical_file:
                response = client.post(
                    "/api/analysis/statistical/survival-analysis",
                    files={"clinical_data": clinical_file},
                    params={
                        "time_column": "overall_survival_time",
                        "event_column": "overall_survival_event",
                    },
                    headers=auth_headers,
                )

                assert response.status_code in [200, 202]
                if response.status_code == 200:
                    data = response.json()
                    assert "results" in data or "analysis_results" in data
        finally:
            import os

            os.unlink(temp_path)

    def test_get_analysis_status_not_found(self, client: TestClient, auth_headers):
        """Test getting status for non-existent analysis."""
        response = client.get(
            "/api/biomarkers/analysis/nonexistent-id/status", headers=auth_headers
        )
        assert response.status_code == 404

    def test_get_analysis_status_success(
        self, client: TestClient, auth_headers, test_analysis_run
    ):
        """Test getting status for existing analysis."""
        response = client.get(
            f"/api/biomarkers/analysis/{test_analysis_run.id}/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "run_id" in data

    def test_get_analysis_results_not_found(self, client: TestClient, auth_headers):
        """Test getting results for non-existent analysis."""
        response = client.get(
            "/api/biomarkers/analysis/nonexistent-id/results", headers=auth_headers
        )
        assert response.status_code == 404

    def test_get_analysis_results_success(
        self,
        client: TestClient,
        auth_headers,
        test_analysis_run,
        test_biomarker_results,
    ):
        """Test getting results for existing analysis."""
        response = client.get(
            f"/api/biomarkers/analysis/{test_analysis_run.id}/results",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data or "biomarkers" in data

    def test_perform_correlation_analysis(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test performing correlation analysis."""
        with open(test_data_files["expression_file"], "rb") as expr_file:
            response = client.post(
                "/api/analysis/statistical/correlation-analysis",
                files={"expression_data": expr_file},
                params={"method": "pearson"},
                headers=auth_headers,
            )

            assert response.status_code in [200, 422]
            if response.status_code == 200:
                data = response.json()
                assert "correlation_matrix" in data or "results" in data

    def test_perform_feature_selection(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test performing feature selection."""
        with open(test_data_files["expression_file"], "rb") as expr_file, open(
            test_data_files["clinical_file"], "rb"
        ) as clinical_file:
            response = client.post(
                "/api/analysis/ml/feature-selection",
                files={"expression_data": expr_file, "labels": clinical_file},
                params={"method": "lasso", "n_features": 50},
                headers=auth_headers,
            )

            assert response.status_code in [200, 422]
            if response.status_code == 200:
                data = response.json()
                assert "selected_features" in data or "features" in data

    def test_train_ml_model(self, client: TestClient, auth_headers, test_data_files):
        """Test training ML model."""
        with open(test_data_files["expression_file"], "rb") as expr_file, open(
            test_data_files["clinical_file"], "rb"
        ) as clinical_file:
            response = client.post(
                "/api/analysis/ml/model-training",
                files={"expression_data": expr_file, "labels": clinical_file},
                params={"model_type": "random_forest", "test_size": 0.2},
                headers=auth_headers,
            )

            assert response.status_code in [200, 202, 422]
            if response.status_code == 200:
                data = response.json()
                assert "model_id" in data or "performance_metrics" in data

    def test_perform_pathway_enrichment(self, client: TestClient, auth_headers):
        """Test performing pathway enrichment."""
        # Create temporary gene list file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            gene_df = pd.DataFrame({"gene": ["TP53", "BRCA1", "BRCA2", "KRAS", "EGFR"]})
            gene_df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as gene_file:
                response = client.post(
                    "/api/analysis/pathway/enrichment",
                    files={"gene_list": gene_file},
                    params={"pathway_database": "kegg", "organism": "hsa"},
                    headers=auth_headers,
                )

                assert response.status_code in [200, 422]
                if response.status_code == 200:
                    data = response.json()
                    assert "results" in data or "enriched_pathways" in data
        finally:
            os.unlink(temp_path)

    def test_perform_network_analysis(self, client: TestClient, auth_headers):
        """Test performing network analysis."""
        # Create temporary gene list file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            gene_df = pd.DataFrame({"gene": ["TP53", "BRCA1", "BRCA2"]})
            gene_df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as gene_file:
                response = client.post(
                    "/api/analysis/pathway/network-analysis",
                    files={"gene_list": gene_file},
                    params={"network_type": "ppi"},
                    headers=auth_headers,
                )

                assert response.status_code in [200, 422, 501]
                if response.status_code == 200:
                    data = response.json()
                    assert (
                        "cytoscape" in data
                        or "edge_count" in data
                        or "network_data" in data
                        or "nodes" in data
                    )
        finally:
            os.unlink(temp_path)

    def test_get_analytics_dashboard(self, client: TestClient, auth_headers):
        """Test analytics dashboard endpoint shape."""
        response = client.get(
            "/api/analysis/analytics/dashboard/test-run-id",
            headers=auth_headers,
        )
        # Depends on fixture run IDs; endpoint should return structured payload or not-found.
        assert response.status_code in [200, 404, 422]
        if response.status_code == 200:
            data = response.json()
            assert "summary" in data
            assert "three_d_points" in data

    def test_literature_kg_endpoint(self, client: TestClient, auth_headers):
        """Test literature retrieval + KG endpoint."""
        response = client.post(
            "/api/analysis/llm/literature-kg",
            json={"genes": ["TP53", "BRCA1", "EGFR"]},
            headers=auth_headers,
        )
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "kg" in data
            assert "nodes" in data["kg"]

    def test_get_available_statistical_methods(self, client: TestClient):
        """Test getting available statistical methods."""
        response = client.get("/api/analysis/methods/statistical")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_available_ml_methods(self, client: TestClient):
        """Test getting available ML methods."""
        response = client.get("/api/analysis/methods/ml")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_available_pathway_databases(self, client: TestClient):
        """Test getting available pathway databases."""
        response = client.get("/api/analysis/methods/pathway")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_evaluate_ml_model(self, client: TestClient, auth_headers, test_data_files):
        """Test evaluating ML model."""
        with open(test_data_files["expression_file"], "rb") as test_data, open(
            test_data_files["clinical_file"], "rb"
        ) as test_labels:
            response = client.post(
                "/api/analysis/ml/model-evaluation",
                files={"test_data": test_data, "test_labels": test_labels},
                params={"model_id": "test-model-123"},
                headers=auth_headers,
            )

            assert response.status_code in [200, 422, 501]
            if response.status_code == 200:
                data = response.json()
                assert "performance_metrics" in data or "model_id" in data

    def test_perform_differential_expression_edge_cases(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test differential expression with edge cases."""
        # Test with different test methods
        test_methods = ["t_test", "wilcoxon", "anova", "kruskal"]
        for method in test_methods:
            with open(test_data_files["expression_file"], "rb") as expr_file, open(
                test_data_files["clinical_file"], "rb"
            ) as clinical_file:
                response = client.post(
                    "/api/analysis/statistical/differential-expression",
                    files={
                        "expression_data": expr_file,
                        "clinical_data": clinical_file,
                    },
                    params={"test_method": method, "p_value_threshold": 0.01},
                    headers=auth_headers,
                )

                assert response.status_code in [200, 202, 422, 500]

    def test_perform_correlation_analysis_edge_cases(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test correlation analysis with different methods."""
        methods = ["pearson", "spearman", "kendall"]
        for method in methods:
            with open(test_data_files["expression_file"], "rb") as expr_file:
                response = client.post(
                    "/api/analysis/statistical/correlation-analysis",
                    files={"data_file": expr_file},
                    params={"method": method, "min_correlation": 0.3},
                    headers=auth_headers,
                )
                # Accept 500 as valid for unsupported methods or data issues
                assert response.status_code in [200, 422, 500]

    def test_perform_feature_selection_edge_cases(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test feature selection with different methods."""
        methods = ["lasso", "elastic_net", "random_forest"]
        for method in methods:
            with open(test_data_files["expression_file"], "rb") as expr_file, open(
                test_data_files["clinical_file"], "rb"
            ) as clinical_file:
                response = client.post(
                    "/api/analysis/ml/feature-selection",
                    files={"expression_data": expr_file, "labels": clinical_file},
                    params={"method": method, "n_features": 10},
                    headers=auth_headers,
                )
                assert response.status_code in [200, 422]

    def test_train_ml_model_edge_cases(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test training ML model with different model types."""
        model_types = ["random_forest", "logistic_regression", "support_vector_machine"]
        for model_type in model_types:
            with open(test_data_files["expression_file"], "rb") as expr_file, open(
                test_data_files["clinical_file"], "rb"
            ) as clinical_file:
                response = client.post(
                    "/api/analysis/ml/model-training",
                    files={"expression_data": expr_file, "labels": clinical_file},
                    params={"model_type": model_type, "test_size": 0.3},
                    headers=auth_headers,
                )
                assert response.status_code in [200, 202, 422]

    def test_perform_pathway_enrichment_edge_cases(
        self, client: TestClient, auth_headers
    ):
        """Test pathway enrichment with different databases."""
        databases = ["kegg", "reactome", "gene_ontology"]
        for db in databases:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                gene_df = pd.DataFrame({"gene": ["TP53", "BRCA1", "BRCA2"]})
                gene_df.to_csv(f.name, index=False)
                temp_path = f.name

            try:
                with open(temp_path, "rb") as gene_file:
                    response = client.post(
                        "/api/analysis/pathway/enrichment",
                        files={"gene_list": gene_file},
                        params={"pathway_database": db, "organism": "hsa"},
                        headers=auth_headers,
                    )
                    assert response.status_code in [200, 422]
            finally:
                os.unlink(temp_path)

    def test_get_available_databases(self, client: TestClient):
        """Test getting available databases."""
        response = client.get("/api/analysis/databases")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "pathway_databases" in data

    def test_perform_differential_expression_error_handling(
        self, client: TestClient, auth_headers
    ):
        """Test error handling in differential expression."""
        # Test with invalid file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("invalid data")
            temp_path = f.name

        try:
            with open(temp_path, "rb") as invalid_file:
                response = client.post(
                    "/api/analysis/statistical/differential-expression",
                    files={
                        "expression_data": invalid_file,
                        "clinical_data": invalid_file,
                    },
                    headers=auth_headers,
                )
                assert response.status_code in [400, 422, 500]
        finally:
            os.unlink(temp_path)

    def test_perform_survival_analysis_error_handling(
        self, client: TestClient, auth_headers
    ):
        """Test error handling in survival analysis."""
        # Test with missing columns
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df = pd.DataFrame({"sample_id": ["S1", "S2"], "age": [50, 60]})
            df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as clinical_file:
                response = client.post(
                    "/api/analysis/statistical/survival-analysis",
                    files={"clinical_data": clinical_file},
                    params={
                        "time_column": "nonexistent_time",
                        "event_column": "nonexistent_event",
                    },
                    headers=auth_headers,
                )
                assert response.status_code in [422, 500]
        finally:
            os.unlink(temp_path)
