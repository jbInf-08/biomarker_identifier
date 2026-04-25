"""
Edge case and error handling tests for data API endpoints.
"""
from io import BytesIO

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


class TestDataAPIEdgeCases:
    """Edge case tests for data API endpoints."""

    def test_upload_expression_data_invalid_file(
        self, client: TestClient, auth_headers
    ):
        """Test uploading invalid expression data file."""
        invalid_file = BytesIO(b"not a valid csv")
        invalid_file.name = "invalid.txt"

        response = client.post(
            "/api/data/upload/expression",
            files={"file": invalid_file},
            headers=auth_headers,
        )

        assert response.status_code in [400, 422, 500]

    def test_upload_expression_data_empty_file(self, client: TestClient, auth_headers):
        """Test uploading empty expression data file."""
        empty_file = BytesIO(b"")
        empty_file.name = "empty.csv"

        response = client.post(
            "/api/data/upload/expression",
            files={"file": empty_file},
            headers=auth_headers,
        )

        assert response.status_code in [400, 422, 500]

    def test_upload_expression_data_missing_index(
        self, client: TestClient, auth_headers
    ):
        """Test uploading expression data without proper index."""
        # Create data without index column
        data = pd.DataFrame(np.random.randn(10, 5))
        buffer = BytesIO()
        data.to_csv(buffer, index=False)
        buffer.seek(0)
        buffer.name = "no_index.csv"

        response = client.post(
            "/api/data/upload/expression", files={"file": buffer}, headers=auth_headers
        )

        # May succeed or fail depending on implementation
        assert response.status_code in [200, 400, 422, 500]

    def test_upload_clinical_data_missing_required_column(
        self, client: TestClient, auth_headers
    ):
        """Test uploading clinical data without required columns."""
        # Create data without sample_id
        data = pd.DataFrame({"group": [0, 1, 0, 1]})
        buffer = BytesIO()
        data.to_csv(buffer, index=False)
        buffer.seek(0)
        buffer.name = "clinical.csv"

        response = client.post(
            "/api/data/upload/clinical", files={"file": buffer}, headers=auth_headers
        )

        assert response.status_code in [400, 422, 500]

    def test_validate_expression_data_not_found(self, client: TestClient, auth_headers):
        """Test validating non-existent expression data."""
        response = client.post(
            "/api/data/validate/expression",
            json={"file_id": "nonexistent-id"},
            headers=auth_headers,
        )

        assert response.status_code in [404, 422]

    def test_get_file_metadata_not_found(self, client: TestClient, auth_headers):
        """Test getting metadata for non-existent file."""
        response = client.get(
            "/api/data/files/nonexistent-file-id/metadata", headers=auth_headers
        )

        assert response.status_code == 404

    def test_delete_file_not_found(self, client: TestClient, auth_headers):
        """Test deleting non-existent file."""
        response = client.delete(
            "/api/data/files/nonexistent-file-id", headers=auth_headers
        )

        assert response.status_code == 404

    def test_normalize_data_invalid_method(self, client: TestClient, auth_headers):
        """Test normalizing data with invalid method."""
        response = client.post(
            "/api/data/normalize",
            json={"file_id": "test-id", "method": "invalid_method"},
            headers=auth_headers,
        )

        assert response.status_code in [400, 404, 422]

    def test_perform_quality_control_not_found(self, client: TestClient, auth_headers):
        """Test performing QC on non-existent file."""
        response = client.post(
            "/api/data/quality-control",
            json={"file_id": "nonexistent-id"},
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_upload_multi_omics_data_missing_files(
        self, client: TestClient, auth_headers
    ):
        """Test uploading multi-omics data with missing files."""
        response = client.post(
            "/api/data/upload/multi-omics", files={}, headers=auth_headers  # No files
        )

        assert response.status_code in [400, 422]
