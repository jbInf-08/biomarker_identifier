"""
API error-path tests: invalid inputs, 404, 500, malformed requests.
"""
import io

import pytest
from fastapi.testclient import TestClient


class TestAnalysisErrorPaths:
    """Error paths for analysis endpoints."""

    def test_differential_expression_missing_files(
        self, client: TestClient, auth_headers
    ):
        """Post with no files returns 422."""
        response = client.post(
            "/api/analysis/statistical/differential-expression",
            files={},
            headers=auth_headers,
        )
        assert response.status_code in [400, 422]

    def test_correlation_analysis_missing_files(
        self, client: TestClient, auth_headers
    ):
        """Post correlation with no files."""
        response = client.post(
            "/api/analysis/statistical/correlation-analysis",
            files={},
            headers=auth_headers,
        )
        assert response.status_code in [400, 422]

    def test_feature_selection_invalid_method(
        self, client: TestClient, auth_headers
    ):
        """Feature selection with invalid method."""
        csv_content = b"gene,S1,S2,S3,S4,S5\nG1,1,2,3,4,5\nG2,2,3,4,5,6"
        response = client.post(
            "/api/analysis/ml/feature-selection",
            files={"file": ("expr.csv", io.BytesIO(csv_content), "text/csv")},
            data={"method": "invalid_method"},
            headers=auth_headers,
        )
        assert response.status_code in [400, 422, 500]

    def test_pathway_enrichment_invalid_json(
        self, client: TestClient, auth_headers
    ):
        """Pathway enrichment with invalid body."""
        response = client.post(
            "/api/analysis/pathway/enrichment",
            content="not valid json",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert response.status_code in [400, 422]


class TestDataErrorPaths:
    """Error paths for data endpoints."""

    def test_upload_expression_empty_file(
        self, client: TestClient, auth_headers
    ):
        """Upload empty file."""
        response = client.post(
            "/api/data/upload/expression",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
            data={"data_type": "rna_seq", "organism": "human"},
            headers=auth_headers,
        )
        assert response.status_code in [400, 422, 500]

    def test_validate_expression_nonexistent_file(
        self, client: TestClient, auth_headers
    ):
        """Validate non-existent file_id."""
        response = client.post(
            "/api/data/validate/expression",
            params={"file_id": "nonexistent-id-12345"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_delete_file_nonexistent(self, client: TestClient, auth_headers):
        """Delete non-existent file."""
        response = client.delete(
            "/api/data/files/nonexistent-file-999",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_download_file_nonexistent(self, client: TestClient, auth_headers):
        """Download non-existent file."""
        response = client.get(
            "/api/data/files/nonexistent-file-999/download",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestBiomarkerErrorPaths:
    """Error paths for biomarker/run endpoints."""

    def test_get_run_not_found(self, client: TestClient, auth_headers):
        """Get non-existent run."""
        response = client.get(
            "/api/biomarkers/runs/nonexistent-run-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_get_run_status_not_found(self, client: TestClient, auth_headers):
        """Get status of non-existent run."""
        response = client.get(
            "/api/biomarkers/runs/nonexistent-run-id/status",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_get_run_results_not_found(self, client: TestClient, auth_headers):
        """Get results of non-existent run."""
        response = client.get(
            "/api/biomarkers/runs/nonexistent-run-id/results",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestAuthErrorPaths:
    """Error paths for auth endpoints."""

    def test_login_missing_body(self, client: TestClient):
        """Login with missing body."""
        response = client.post(
            "/api/auth/login",
            json={},
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in [400, 422]

    def test_login_invalid_content_type(self, client: TestClient):
        """Login with wrong content type."""
        response = client.post(
            "/api/auth/login",
            data="email=test@test.com&password=secret",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code in [400, 415, 422]
