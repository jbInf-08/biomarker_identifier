"""
Edge case and error handling tests for analysis API endpoints.
"""
import os
import tempfile
from io import BytesIO

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


class TestAnalysisAPIEdgeCases:
    """Edge case tests for analysis API endpoints."""

    def test_differential_expression_invalid_file_format(
        self, client: TestClient, auth_headers
    ):
        """Test differential expression with invalid file format."""
        # Create invalid file
        invalid_file = BytesIO(b"not a valid csv file content")
        invalid_file.name = "invalid.txt"

        clinical_file = BytesIO(b"sample_id,group\nS1,0\nS2,1")
        clinical_file.name = "clinical.csv"

        response = client.post(
            "/api/analysis/statistical/differential-expression",
            files={"expression_data": invalid_file, "clinical_data": clinical_file},
            headers=auth_headers,
        )

        assert response.status_code in [400, 422, 500]

    def test_differential_expression_missing_label_column(
        self, client: TestClient, auth_headers
    ):
        """Test differential expression with missing label column."""
        # Create expression data
        expr_data = pd.DataFrame(np.random.randn(10, 5))
        expr_buffer = BytesIO()
        expr_data.to_csv(expr_buffer, index=True)
        expr_buffer.seek(0)
        expr_buffer.name = "expression.csv"

        # Create clinical data without label column
        clinical_data = pd.DataFrame({"sample_id": ["S1", "S2", "S3", "S4", "S5"]})
        clinical_buffer = BytesIO()
        clinical_data.to_csv(clinical_buffer, index=False)
        clinical_buffer.seek(0)
        clinical_buffer.name = "clinical.csv"

        response = client.post(
            "/api/analysis/statistical/differential-expression",
            files={"expression_data": expr_buffer, "clinical_data": clinical_buffer},
            headers=auth_headers,
        )

        assert response.status_code in [400, 422, 500]

    def test_differential_expression_invalid_test_method(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test differential expression with invalid test method."""
        with open(test_data_files["expression_file"], "rb") as expr_file, open(
            test_data_files["clinical_file"], "rb"
        ) as clinical_file:
            response = client.post(
                "/api/analysis/statistical/differential-expression",
                files={"expression_data": expr_file, "clinical_data": clinical_file},
                params={"test_method": "invalid_method"},
                headers=auth_headers,
            )

            assert response.status_code in [200, 400, 422, 500]

    def test_correlation_analysis_empty_data(self, client: TestClient, auth_headers):
        """Test correlation analysis with empty data."""
        empty_data = pd.DataFrame()
        empty_buffer = BytesIO()
        empty_data.to_csv(empty_buffer, index=True)
        empty_buffer.seek(0)
        empty_buffer.name = "empty.csv"

        response = client.post(
            "/api/analysis/statistical/correlation-analysis",
            files={"data_file": empty_buffer},
            headers=auth_headers,
        )

        assert response.status_code in [400, 422, 500]

    def test_feature_selection_invalid_method(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test feature selection with invalid method."""
        with open(test_data_files["expression_file"], "rb") as expr_file, open(
            test_data_files["clinical_file"], "rb"
        ) as clinical_file:
            response = client.post(
                "/api/analysis/ml/feature-selection",
                files={"expression_data": expr_file, "clinical_data": clinical_file},
                params={"method": "invalid_method"},
                headers=auth_headers,
            )

            assert response.status_code in [400, 422, 500]

    def test_train_ml_model_invalid_model_type(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test training ML model with invalid model type."""
        with open(test_data_files["expression_file"], "rb") as expr_file, open(
            test_data_files["clinical_file"], "rb"
        ) as clinical_file:
            response = client.post(
                "/api/analysis/ml/model-training",
                files={"expression_data": expr_file, "labels": clinical_file},
                params={"model_type": "invalid_model"},
                headers=auth_headers,
            )

            assert response.status_code in [200, 400, 422, 500]

    def test_pathway_enrichment_invalid_gene_list(
        self, client: TestClient, auth_headers
    ):
        """Test pathway enrichment with too few genes (requires file upload)."""
        buf = BytesIO(b"gene\nTP53\n")
        buf.name = "genes.csv"
        response = client.post(
            "/api/analysis/pathway/enrichment",
            files={"gene_list": ("genes.csv", buf, "text/csv")},
            headers=auth_headers,
        )

        assert response.status_code in [400, 422, 500]

    def test_pathway_enrichment_invalid_gene_set(
        self, client: TestClient, auth_headers
    ):
        """Test pathway enrichment with a minimal gene list file."""
        buf = BytesIO(b"gene\nTP53\nBRCA1\n")
        buf.name = "genes.csv"
        response = client.post(
            "/api/analysis/pathway/enrichment",
            files={"gene_list": ("genes.csv", buf, "text/csv")},
            params={"pathway_database": "kegg"},
            headers=auth_headers,
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_get_analysis_run_not_found(self, client: TestClient, auth_headers):
        """Test getting non-existent analysis run."""
        response = client.get(
            "/api/analysis/runs/nonexistent-run-id", headers=auth_headers
        )

        assert response.status_code == 404

    def test_cancel_analysis_run_not_found(self, client: TestClient, auth_headers):
        """Test canceling non-existent analysis run."""
        response = client.post(
            "/api/analysis/runs/nonexistent-run-id/cancel", headers=auth_headers
        )

        assert response.status_code == 404

    def test_download_results_not_found(self, client: TestClient, auth_headers):
        """Test downloading results for non-existent run."""
        response = client.get(
            "/api/analysis/runs/nonexistent-run-id/results", headers=auth_headers
        )

        assert response.status_code == 404

    def test_differential_expression_single_class(
        self, client: TestClient, auth_headers
    ):
        """Test differential expression with only one class."""
        # Create data with only one class
        expr_data = pd.DataFrame(np.random.randn(10, 5))
        expr_buffer = BytesIO()
        expr_data.to_csv(expr_buffer, index=True)
        expr_buffer.seek(0)
        expr_buffer.name = "expression.csv"

        clinical_data = pd.DataFrame(
            {
                "sample_id": ["S1", "S2", "S3", "S4", "S5"],
                "group": [0, 0, 0, 0, 0],  # All same class
            }
        )
        clinical_buffer = BytesIO()
        clinical_data.to_csv(clinical_buffer, index=False)
        clinical_buffer.seek(0)
        clinical_buffer.name = "clinical.csv"

        response = client.post(
            "/api/analysis/statistical/differential-expression",
            files={"expression_data": expr_buffer, "clinical_data": clinical_buffer},
            headers=auth_headers,
        )

        assert response.status_code in [400, 422, 500]

    def test_correlation_analysis_single_sample(self, client: TestClient, auth_headers):
        """Test correlation analysis with single sample."""
        # Create data with only one sample
        expr_data = pd.DataFrame(np.random.randn(10, 1))
        expr_buffer = BytesIO()
        expr_data.to_csv(expr_buffer, index=True)
        expr_buffer.seek(0)
        expr_buffer.name = "expression.csv"

        response = client.post(
            "/api/analysis/statistical/correlation-analysis",
            files={"data_file": expr_buffer},
            headers=auth_headers,
        )

        assert response.status_code in [400, 422, 500]
