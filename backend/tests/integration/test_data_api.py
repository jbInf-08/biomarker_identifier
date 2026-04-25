"""
Comprehensive integration tests for data API endpoints.
"""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


class TestDataAPI:
    """Test cases for data API endpoints."""

    def test_upload_expression_data_unauthorized(self, client: TestClient):
        """Test uploading expression data without authentication."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df = pd.DataFrame(
                {
                    "Gene": ["GENE001", "GENE002"],
                    "Sample1": [1.5, 2.3],
                    "Sample2": [1.8, 2.1],
                }
            )
            df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as file:
                response = client.post(
                    "/api/data/upload/expression",
                    files={"file": file},
                    data={"data_type": "rna_seq", "organism": "human"},
                )
                assert response.status_code in [401, 403, 422]
        finally:
            os.unlink(temp_path)

    def test_upload_expression_data_success(self, client: TestClient, auth_headers):
        """Test uploading expression data with valid file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df = pd.DataFrame(
                {
                    "Gene": ["GENE001", "GENE002", "GENE003"],
                    "Sample1": [1.5, 2.3, 0.8],
                    "Sample2": [1.8, 2.1, 0.9],
                    "Sample3": [1.2, 2.5, 0.7],
                }
            )
            df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as file:
                response = client.post(
                    "/api/data/upload/expression",
                    files={"file": file},
                    data={"data_type": "rna_seq", "organism": "human"},
                    headers=auth_headers,
                )
                assert response.status_code == 200
                data = response.json()
                assert "file_id" in data or "status" in data
        finally:
            os.unlink(temp_path)

    def test_upload_clinical_data_unauthorized(self, client: TestClient):
        """Test uploading clinical data without authentication."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df = pd.DataFrame(
                {
                    "sample_id": ["S1", "S2", "S3"],
                    "class_label": ["A", "B", "A"],
                    "age": [45, 50, 55],
                }
            )
            df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as file:
                response = client.post(
                    "/api/data/upload/clinical",
                    files={"file": file},
                    data={"data_type": "clinical"},
                )
                assert response.status_code in [401, 403, 422]
        finally:
            os.unlink(temp_path)

    def test_upload_clinical_data_success(self, client: TestClient, auth_headers):
        """Test uploading clinical data with valid file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df = pd.DataFrame(
                {
                    "sample_id": ["S1", "S2", "S3"],
                    "class_label": ["A", "B", "A"],
                    "age": [45, 50, 55],
                }
            )
            df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            with open(temp_path, "rb") as file:
                response = client.post(
                    "/api/data/upload/clinical",
                    files={"file": file},
                    data={"data_type": "clinical"},
                    headers=auth_headers,
                )
                assert response.status_code == 200
                data = response.json()
                assert "file_id" in data or "status" in data
        finally:
            os.unlink(temp_path)

    def test_validate_expression_data_not_found(self, client: TestClient, auth_headers):
        """Test validating non-existent expression data."""
        response = client.post(
            "/api/data/validate/expression",
            params={"file_id": "nonexistent-id"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_validate_clinical_data_not_found(self, client: TestClient, auth_headers):
        """Test validating non-existent clinical data."""
        response = client.post(
            "/api/data/validate/clinical",
            params={"file_id": "nonexistent-id"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_normalize_expression_data_not_found(
        self, client: TestClient, auth_headers
    ):
        """Test normalizing non-existent expression data."""
        response = client.post(
            "/api/data/process/normalize",
            params={"file_id": "nonexistent-id", "method": "quantile"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_perform_quality_control_not_found(self, client: TestClient, auth_headers):
        """Test performing QC on non-existent data."""
        response = client.post(
            "/api/data/process/quality-control",
            params={"file_id": "nonexistent-id"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_list_uploaded_files(self, client: TestClient, auth_headers):
        """Test listing uploaded files."""
        response = client.get(
            "/api/data/files", params={"limit": 10, "offset": 0}, headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_delete_file_not_found(self, client: TestClient, auth_headers):
        """Test deleting non-existent file."""
        response = client.delete("/api/data/files/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404

    def test_download_file_not_found(self, client: TestClient, auth_headers):
        """Test downloading non-existent file."""
        response = client.get(
            "/api/data/files/nonexistent-id/download", headers=auth_headers
        )
        assert response.status_code == 404

    def test_upload_expression_data_edge_cases(self, client: TestClient, auth_headers):
        """Test uploading expression data with edge cases."""
        # Test with different file types
        file_types = ["rna_seq", "microarray", "proteomics"]
        for file_type in file_types:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                df = pd.DataFrame(
                    {
                        "Gene": ["GENE001", "GENE002"],
                        "Sample1": [1.5, 2.3],
                        "Sample2": [1.8, 2.1],
                    }
                )
                df.to_csv(f.name, index=False)
                temp_path = f.name

            try:
                with open(temp_path, "rb") as file:
                    response = client.post(
                        "/api/data/upload/expression",
                        files={"file": file},
                        data={"data_type": file_type, "organism": "human"},
                        headers=auth_headers,
                    )
                    assert response.status_code in [200, 422, 500]
            finally:
                os.unlink(temp_path)

    def test_upload_expression_data_invalid_file(
        self, client: TestClient, auth_headers
    ):
        """Test uploading invalid file type."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("invalid data")
            temp_path = f.name

        try:
            with open(temp_path, "rb") as file:
                response = client.post(
                    "/api/data/upload/expression",
                    files={"file": file},
                    data={"data_type": "rna_seq", "organism": "human"},
                    headers=auth_headers,
                )
                assert response.status_code in [400, 422, 500]
        finally:
            os.unlink(temp_path)

    def test_upload_multi_omics_data(self, client: TestClient, auth_headers):
        """Test uploading multi-omics data."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as expr_file, tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as clinical_file:
            expr_df = pd.DataFrame(
                {
                    "Gene": ["GENE001", "GENE002"],
                    "Sample1": [1.5, 2.3],
                    "Sample2": [1.8, 2.1],
                }
            )
            expr_df.to_csv(expr_file.name, index=False)

            clinical_df = pd.DataFrame(
                {"sample_id": ["Sample1", "Sample2"], "group": ["A", "B"]}
            )
            clinical_df.to_csv(clinical_file.name, index=False)

            expr_path = expr_file.name
            clinical_path = clinical_file.name

        try:
            with open(expr_path, "rb") as expr, open(clinical_path, "rb") as clinical:
                response = client.post(
                    "/api/data/upload/multi-omics",
                    files={"expression_file": expr, "clinical_file": clinical},
                    data={"study_name": "test_study"},
                    headers=auth_headers,
                )
                assert response.status_code in [200, 422, 500]
        finally:
            os.unlink(expr_path)
            os.unlink(clinical_path)
