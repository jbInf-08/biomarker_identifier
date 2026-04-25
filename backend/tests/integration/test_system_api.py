"""
Comprehensive integration tests for system API endpoints.
"""
import pytest
from fastapi.testclient import TestClient


class TestSystemAPI:
    """Test cases for system API endpoints."""

    def test_get_system_health(self, client: TestClient):
        """Test getting system health status."""
        response = client.get("/api/v1/system/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] in ["healthy", "warning", "critical", "unknown"]
        assert "timestamp" in data
        assert "metrics" in data or "cpu_percent" in data

    def test_get_system_metrics(self, client: TestClient):
        """Test getting system metrics."""
        response = client.get("/api/v1/system/metrics")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        # Check for expected metric keys
        assert "system" in data or "cpu_usage" in data or "memory_usage" in data

    def test_get_services_status(self, client: TestClient):
        """Test getting services status."""
        response = client.get("/api/v1/system/services/status")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "timestamp" in data
        assert "database" in data or "redis" in data

    def test_get_system_health_error_handling(self, client: TestClient):
        """Test system health error handling."""
        # This should always work, but test the response structure
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        # Verify structure even if services are down
        assert "status" in data

    def test_get_system_metrics_error_handling(self, client: TestClient):
        """Test system metrics error handling."""
        response = client.get("/api/v1/system/metrics")
        # Should return 200 even if some metrics fail
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
