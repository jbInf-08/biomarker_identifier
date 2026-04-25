"""
Simple end-to-end workflow verification test.

This test verifies the basic workflow: health check -> API status -> tenant creation.
It's designed to run even without full Docker stack, using local services.
"""
from typing import Any, Dict

import pytest
import requests

# Use 127.0.0.1 on Windows so requests reach the Docker-published port reliably.
BASE_URL = "http://127.0.0.1:8000"
# Docker / multi-worker startup can exceed a short client timeout
REQUEST_TIMEOUT = 30


@pytest.mark.e2e
@pytest.mark.usefixtures("wait_for_backend_ready")
class TestSimpleWorkflow:
    """Simple E2E workflow tests."""

    def test_health_endpoint(self):
        """Test backend health endpoint."""
        response = requests.get(f"{BASE_URL}/health", timeout=REQUEST_TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_api_status_endpoint(self):
        """Test API status endpoint."""
        response = requests.get(f"{BASE_URL}/api/status", timeout=REQUEST_TIMEOUT)
        assert response.status_code == 200
        data = response.json()
        assert "api_status" in data

    def test_tenant_creation_workflow(self):
        """Test tenant creation via API (multi-tenant feature)."""
        # Create a test tenant
        tenant_data = {"id": "test_tenant_e2e", "name": "E2E Test Tenant"}

        response = requests.post(
            f"{BASE_URL}/api/tenants/", json=tenant_data, timeout=REQUEST_TIMEOUT
        )

        # Should succeed (201) or return conflict if exists (400)
        assert response.status_code in [201, 400]

        # Verify tenant exists
        get_response = requests.get(
            f"{BASE_URL}/api/tenants/{tenant_data['id']}", timeout=REQUEST_TIMEOUT
        )
        assert get_response.status_code == 200
        tenant = get_response.json()
        assert tenant["id"] == tenant_data["id"]

    def test_api_documentation_accessible(self):
        """Test that API documentation is accessible."""
        response = requests.get(f"{BASE_URL}/docs", timeout=REQUEST_TIMEOUT)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
