"""
Integration tests for biomarker API endpoints.
"""
import pytest
from fastapi.testclient import TestClient


class TestBiomarkerAPI:
    """Test cases for biomarker API endpoints."""

    def test_get_runs_unauthorized(self, client: TestClient):
        """Test getting runs without authentication."""
        response = client.get("/api/biomarkers/runs")

        assert response.status_code == 403

    def test_get_runs_success(self, client: TestClient, auth_headers):
        """Test getting runs with authentication."""
        response = client.get("/api/biomarkers/runs", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)

    def test_get_runs_with_test_data(
        self, client: TestClient, auth_headers, test_analysis_run
    ):
        """Test getting runs with test data."""
        response = client.get("/api/biomarkers/runs", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert len(data) >= 1
        run = data[0]
        assert "id" in run
        assert "project_name" in run
        assert "status" in run
        assert "created_at" in run

    def test_get_run_by_id_success(
        self, client: TestClient, auth_headers, test_analysis_run
    ):
        """Test getting a specific run by ID."""
        response = client.get(
            f"/api/biomarkers/runs/{test_analysis_run.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == test_analysis_run.id
        assert data["project_name"] == test_analysis_run.project_name
        assert data["status"] == test_analysis_run.status

    def test_get_run_by_id_not_found(self, client: TestClient, auth_headers):
        """Test getting a non-existent run."""
        response = client.get(
            "/api/biomarkers/runs/nonexistent-id", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Run not found" in response.json()["detail"]

    def test_get_run_by_id_unauthorized(self, client: TestClient, test_analysis_run):
        """Test getting a run without authentication."""
        response = client.get(f"/api/biomarkers/runs/{test_analysis_run.id}")

        assert response.status_code == 403

    def test_start_analysis_unauthorized(self, client: TestClient):
        """Test starting analysis without authentication."""
        analysis_data = {
            "project_name": "Test Project",
            "description": "Test analysis",
            "expression_file_path": "/test/expression.csv",
            "label_file_path": "/test/labels.csv",
            "parameters": {"top_n": 100},
        }

        response = client.post("/api/biomarkers/analysis/start", json=analysis_data)

        assert response.status_code == 403

    def test_start_analysis_success(
        self, client: TestClient, auth_headers, test_data_files
    ):
        """Test starting analysis with valid data."""
        analysis_data = {
            "project_name": "Test Project",
            "description": "Test analysis",
            "expression_file_path": test_data_files["expression_file"],
            "label_file_path": test_data_files["clinical_file"],
            "parameters": {
                "top_n": 100,
                "p_value_threshold": 0.05,
                "batch_correction": True,
            },
        }

        response = client.post(
            "/api/biomarkers/analysis/start", json=analysis_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "run_id" in data
        assert "status" in data
        assert data["status"] == "started"

    def test_start_analysis_invalid_data(self, client: TestClient, auth_headers):
        """Test starting analysis with invalid data."""
        analysis_data = {
            "project_name": "",  # Empty project name
            "expression_file_path": "nonexistent.csv",
            "label_file_path": "nonexistent.csv",
        }

        response = client.post(
            "/api/biomarkers/analysis/start", json=analysis_data, headers=auth_headers
        )

        assert response.status_code == 400

    def test_get_run_status_success(
        self, client: TestClient, auth_headers, test_analysis_run
    ):
        """Test getting run status."""
        response = client.get(
            f"/api/biomarkers/runs/{test_analysis_run.id}/status", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "run_id" in data
        assert "status" in data
        assert "progress" in data
        assert data["run_id"] == test_analysis_run.id
        assert data["status"] == test_analysis_run.status

    def test_get_run_status_not_found(self, client: TestClient, auth_headers):
        """Test getting status for non-existent run."""
        response = client.get(
            "/api/biomarkers/runs/nonexistent-id/status", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Run not found" in response.json()["detail"]

    def test_get_run_results_success(
        self, client: TestClient, auth_headers, test_analysis_run
    ):
        """Test getting run results."""
        response = client.get(
            f"/api/biomarkers/runs/{test_analysis_run.id}/results", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "run_id" in data
        assert "status" in data
        assert "results" in data
        assert data["run_id"] == test_analysis_run.id

    def test_get_run_results_not_found(self, client: TestClient, auth_headers):
        """Test getting results for non-existent run."""
        response = client.get(
            "/api/biomarkers/runs/nonexistent-id/results", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Run not found" in response.json()["detail"]

    def test_get_biomarkers_success(
        self,
        client: TestClient,
        auth_headers,
        test_analysis_run,
        test_biomarker_results,
    ):
        """Test getting biomarkers for a run."""
        response = client.get(
            f"/api/biomarkers/runs/{test_analysis_run.id}/biomarkers",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "run_id" in data
        assert "biomarkers" in data
        assert "total" in data
        assert data["run_id"] == test_analysis_run.id
        assert len(data["biomarkers"]) == len(test_biomarker_results)
        assert data["total"] == len(test_biomarker_results)

    def test_get_biomarkers_with_pagination(
        self,
        client: TestClient,
        auth_headers,
        test_analysis_run,
        test_biomarker_results,
    ):
        """Test getting biomarkers with pagination."""
        response = client.get(
            f"/api/biomarkers/runs/{test_analysis_run.id}/biomarkers?skip=0&limit=5",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["biomarkers"]) <= 5
        assert data["total"] == len(test_biomarker_results)

    def test_get_biomarkers_with_filtering(
        self,
        client: TestClient,
        auth_headers,
        test_analysis_run,
        test_biomarker_results,
    ):
        """Test getting biomarkers with filtering."""
        response = client.get(
            f"/api/biomarkers/runs/{test_analysis_run.id}/biomarkers?p_value_threshold=0.01",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check that all returned biomarkers have p_value <= 0.01
        for biomarker in data["biomarkers"]:
            assert biomarker["p_value"] <= 0.01

    def test_get_biomarkers_not_found(self, client: TestClient, auth_headers):
        """Test getting biomarkers for non-existent run."""
        response = client.get(
            "/api/biomarkers/runs/nonexistent-id/biomarkers", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Run not found" in response.json()["detail"]

    def test_delete_run_success(
        self, client: TestClient, auth_headers, test_analysis_run
    ):
        """Test deleting a run."""
        response = client.delete(
            f"/api/biomarkers/runs/{test_analysis_run.id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert "Run deleted successfully" in response.json()["message"]

    def test_delete_run_not_found(self, client: TestClient, auth_headers):
        """Test deleting a non-existent run."""
        response = client.delete(
            "/api/biomarkers/runs/nonexistent-id", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Run not found" in response.json()["detail"]

    def test_delete_run_unauthorized(self, client: TestClient, test_analysis_run):
        """Test deleting a run without authentication."""
        response = client.delete(f"/api/biomarkers/runs/{test_analysis_run.id}")

        assert response.status_code == 403

    def test_generate_report_success(
        self, client: TestClient, auth_headers, test_analysis_run
    ):
        """Test generating a report."""
        report_data = {
            "report_format": "html",
            "report_title": "Test Report",
            "template_name": "standard",
            "include_clinical": True,
        }

        response = client.post(
            f"/api/biomarkers/runs/{test_analysis_run.id}/report",
            json=report_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "run_id" in data
        assert "report_path" in data
        assert "report_format" in data
        assert "template_name" in data
        assert data["run_id"] == test_analysis_run.id
        assert data["report_format"] == "html"

    def test_generate_report_not_found(self, client: TestClient, auth_headers):
        """Test generating a report for non-existent run."""
        report_data = {"report_format": "html", "report_title": "Test Report"}

        response = client.post(
            "/api/biomarkers/runs/nonexistent-id/report",
            json=report_data,
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "Run not found" in response.json()["detail"]

    def test_generate_report_unauthorized(self, client: TestClient, test_analysis_run):
        """Test generating a report without authentication."""
        report_data = {"report_format": "html", "report_title": "Test Report"}

        response = client.post(
            f"/api/biomarkers/runs/{test_analysis_run.id}/report", json=report_data
        )

        assert response.status_code == 403

    def test_download_report_success(
        self, client: TestClient, auth_headers, test_analysis_run
    ):
        """Test downloading a report."""
        # First generate a report
        report_data = {"report_format": "html", "report_title": "Test Report"}

        generate_response = client.post(
            f"/api/biomarkers/runs/{test_analysis_run.id}/report",
            json=report_data,
            headers=auth_headers,
        )

        assert generate_response.status_code == 200

        # Then download it
        response = client.get(
            f"/api/biomarkers/runs/{test_analysis_run.id}/download-report?format=html",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"

    def test_download_report_not_found(self, client: TestClient, auth_headers):
        """Test downloading a report for non-existent run."""
        response = client.get(
            "/api/biomarkers/runs/nonexistent-id/download-report?format=html",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "Run not found" in response.json()["detail"]

    def test_download_report_unauthorized(self, client: TestClient, test_analysis_run):
        """Test downloading a report without authentication."""
        response = client.get(
            f"/api/biomarkers/runs/{test_analysis_run.id}/download-report?format=html"
        )

        assert response.status_code == 403
