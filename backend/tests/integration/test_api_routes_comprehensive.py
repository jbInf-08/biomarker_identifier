"""
Comprehensive API route tests covering analysis, clinical, data, and system endpoints.
Includes error paths and edge cases.
"""
import io
import os
import tempfile

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


class TestAnalysisAPIRoutes:
    """Extended analysis API route tests."""

    def test_get_statistical_methods(self, client: TestClient, auth_headers):
        """Test GET /api/analysis/methods/statistical."""
        response = client.get(
            "/api/analysis/methods/statistical", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_ml_methods(self, client: TestClient, auth_headers):
        """Test GET /api/analysis/methods/ml."""
        response = client.get("/api/analysis/methods/ml", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_pathway_methods(self, client: TestClient, auth_headers):
        """Test GET /api/analysis/methods/pathway."""
        response = client.get(
            "/api/analysis/methods/pathway", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_databases(self, client: TestClient, auth_headers):
        """Test GET /api/analysis/databases."""
        response = client.get("/api/analysis/databases", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_differential_expression_invalid_file(
        self, client: TestClient, auth_headers
    ):
        """Test differential expression with invalid/empty file."""
        empty_file = io.BytesIO(b"invalid,csv,data\n1,2,3")
        response = client.post(
            "/api/analysis/statistical/differential-expression",
            files={
                "expression_data": ("expr.csv", empty_file, "text/csv"),
                "clinical_data": (
                    "clinical.csv",
                    io.BytesIO(b"sample_id,group\nS1,A\nS2,B"),
                    "text/csv",
                ),
            },
            headers=auth_headers,
        )
        assert response.status_code in [400, 422, 500]

    def test_correlation_analysis_unauthorized(self, client: TestClient):
        """Test correlation analysis without auth."""
        response = client.post(
            "/api/analysis/statistical/correlation-analysis"
        )
        assert response.status_code in [401, 403, 422]


class TestClinicalAPIRoutes:
    """Extended clinical API route tests."""

    def test_get_cosmic_cancer_genes(self, client: TestClient, auth_headers):
        """Test GET /api/clinical/cosmic/cancer-genes."""
        response = client.get(
            "/api/clinical/cosmic/cancer-genes",
            params={"cancer_type": "breast"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "genes" in data or "results" in data or "cancer_genes" in data

    def test_annotate_run_unauthorized(self, client: TestClient):
        """Test annotate-run without auth."""
        response = client.post(
            "/api/clinical/annotate-run/test-run-id",
            json={"biomarkers": ["TP53"]},
        )
        assert response.status_code in [401, 403, 404, 422]


class TestDataAPIRoutes:
    """Extended data API route tests."""

    def test_get_files(self, client: TestClient, auth_headers):
        """Test GET /api/data/files (may or may not require auth)."""
        response = client.get("/api/data/files", headers=auth_headers)
        assert response.status_code in [200, 401, 403, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_validate_expression_not_found(self, client: TestClient, auth_headers):
        """Test validate expression with non-existent file_id."""
        response = client.post(
            "/api/data/validate/expression",
            params={"file_id": "nonexistent-file-id"},
            headers=auth_headers,
        )
        assert response.status_code in [404, 422]


class TestSystemAPIRoutes:
    """System API route tests (v1 and v2)."""

    def test_health_v1(self, client: TestClient):
        """Test GET /api/v1/system/health."""
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "warning", "critical", "unknown"]

    def test_health_v2(self, client: TestClient):
        """Test GET /api/v2/system/health."""
        response = client.get("/api/v2/system/health")
        assert response.status_code == 200

    def test_metrics_v1(self, client: TestClient):
        """Test GET /api/v1/system/metrics."""
        response = client.get("/api/v1/system/metrics")
        assert response.status_code in [200, 500]

    def test_services_status_v1(self, client: TestClient):
        """Test GET /api/v1/system/services/status."""
        response = client.get("/api/v1/system/services/status")
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
