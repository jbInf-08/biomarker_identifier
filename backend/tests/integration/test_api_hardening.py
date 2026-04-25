"""
Integration checks: federated routes, admin API keys, LLM status, SlowAPI test mode.
"""

import pytest
from fastapi.testclient import TestClient


def test_federated_health_ok(client: TestClient):
    r = client.get("/api/federated/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_admin_federated_api_key_lifecycle(client: TestClient, admin_headers: dict):
    r = client.post(
        "/api/v1/admin/federated-api-keys",
        json={"name": "integration-test-key"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "api_key" in body and body["api_key"].startswith("sk_")

    r2 = client.get("/api/v1/admin/federated-api-keys", headers=admin_headers)
    assert r2.status_code == 200
    keys = r2.json().get("keys", [])
    assert any(k.get("name") == "integration-test-key" for k in keys)

    kid = body.get("id")
    if kid:
        r3 = client.delete(
            f"/api/v1/admin/federated-api-keys/{kid}", headers=admin_headers
        )
        assert r3.status_code == 200


def test_llm_status_endpoint(client: TestClient):
    r = client.get("/api/analysis/llm/status")
    assert r.status_code == 200
    data = r.json()
    assert "available" in data


def test_slowapi_disabled_during_pytest():
    from app.middleware.rate_limit import limiter

    assert limiter.enabled is False
