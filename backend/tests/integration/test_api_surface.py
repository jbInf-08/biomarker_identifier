"""
Light integration smoke tests for public and authenticated API paths.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-local-pytest")
os.environ.setdefault("DEBUG", "true")

from app.main import app

client = TestClient(app)


def test_health_and_metrics():
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")


def test_federated_health():
    r = client.get("/api/federated/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_federated_capabilities_v1():
    r = client.get("/api/v1/federated/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["ring_masked_aggregation_utils"]["implemented"] is True
    assert "cryptographic_secure_aggregation" in body


def test_llm_status_public():
    r = client.get("/api/analysis/llm/status")
    assert r.status_code == 200
    assert "available" in r.json()


def test_llm_summarize_requires_auth():
    r = client.post("/api/analysis/llm/summarize", json={"text": "test abstract"})
    assert r.status_code in (401, 403)
