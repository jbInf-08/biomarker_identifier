"""
Edge case and error handling tests for biomarker API endpoints.
"""
import pytest
from fastapi.testclient import TestClient


class TestBiomarkerAPIEdgeCases:
    """Edge case tests for biomarker API endpoints."""

    def test_get_biomarker_not_found(self, client: TestClient, auth_headers):
        """Test getting non-existent biomarker."""
        response = client.get(
            "/api/biomarkers/nonexistent-biomarker-id", headers=auth_headers
        )

        assert response.status_code == 404

    def test_update_biomarker_not_found(self, client: TestClient, auth_headers):
        """Test updating non-existent biomarker."""
        response = client.put(
            "/api/biomarkers/nonexistent-biomarker-id",
            json={"status": "validated"},
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_delete_biomarker_not_found(self, client: TestClient, auth_headers):
        """Test deleting non-existent biomarker."""
        response = client.delete(
            "/api/biomarkers/nonexistent-biomarker-id", headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_biomarkers_invalid_filters(self, client: TestClient, auth_headers):
        """Test getting biomarkers with invalid filters."""
        response = client.get(
            "/api/biomarkers",
            params={"p_value_max": -1},  # Invalid negative value
            headers=auth_headers,
        )

        assert response.status_code in [400, 404, 422]

    def test_create_biomarker_invalid_data(self, client: TestClient, auth_headers):
        """Test creating biomarker with invalid data."""
        response = client.post(
            "/api/biomarkers", json={}, headers=auth_headers  # Missing required fields
        )

        assert response.status_code in [400, 404, 422]

    def test_annotate_biomarker_not_found(self, client: TestClient, auth_headers):
        """Test annotating non-existent biomarker."""
        response = client.post(
            "/api/biomarkers/nonexistent-biomarker-id/annotate",
            json={"databases": ["COSMIC"]},
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_validate_biomarker_not_found(self, client: TestClient, auth_headers):
        """Test validating non-existent biomarker."""
        response = client.post(
            "/api/biomarkers/nonexistent-biomarker-id/validate", headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_biomarker_statistics_invalid_date_range(
        self, client: TestClient, auth_headers
    ):
        """Test getting biomarker statistics with invalid date range."""
        response = client.get(
            "/api/biomarkers/statistics",
            params={
                "start_date": "2024-12-31",
                "end_date": "2024-01-01",  # End before start
            },
            headers=auth_headers,
        )

        assert response.status_code in [400, 404, 422]

    def test_export_biomarkers_invalid_format(self, client: TestClient, auth_headers):
        """Test exporting biomarkers with invalid format."""
        response = client.get(
            "/api/biomarkers/export",
            params={"format": "invalid_format"},
            headers=auth_headers,
        )

        assert response.status_code in [400, 404, 422]

    def test_bulk_update_biomarkers_empty_list(self, client: TestClient, auth_headers):
        """Test bulk updating biomarkers with empty list."""
        response = client.put(
            "/api/biomarkers/bulk", json={"biomarker_ids": []}, headers=auth_headers
        )

        assert response.status_code in [400, 404, 422]
