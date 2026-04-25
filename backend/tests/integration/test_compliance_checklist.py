"""Compliance checklist API: evidence rules and role gates."""

from fastapi.testclient import TestClient


def _create_item(client: TestClient, admin_headers: dict) -> str:
    r = client.post(
        "/api/v1/admin/compliance/checklist-items",
        json={
            "framework": "hipaa",
            "control_code": "TEST-CTRL-1",
            "title": "Test checklist control",
        },
        headers=admin_headers,
    )
    assert r.status_code == 200
    return r.json()["id"]


def test_complete_requires_evidence_link(client: TestClient, admin_headers: dict):
    item_id = _create_item(client, admin_headers)
    bad = client.patch(
        f"/api/v1/admin/compliance/checklist-items/{item_id}",
        json={"status": "complete"},
        headers=admin_headers,
    )
    assert bad.status_code == 400
    assert "evidence_link" in bad.json().get("detail", "").lower()

    ok = client.patch(
        f"/api/v1/admin/compliance/checklist-items/{item_id}",
        json={"status": "complete", "evidence_link": "https://example.org/evidence/TEST-CTRL-1"},
        headers=admin_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "complete"


def test_waived_requires_substantive_notes(client: TestClient, admin_headers: dict):
    item_id = _create_item(client, admin_headers)
    short = client.patch(
        f"/api/v1/admin/compliance/checklist-items/{item_id}",
        json={"status": "waived", "notes": "too short"},
        headers=admin_headers,
    )
    assert short.status_code == 400
    assert "waived" in short.json().get("detail", "").lower()

    rationale = (
        "Waiver approved by security committee on 2026-04-20; applies only to de-identified "
        "demo data in staging."
    )
    ok = client.patch(
        f"/api/v1/admin/compliance/checklist-items/{item_id}",
        json={"status": "waived", "notes": rationale},
        headers=admin_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "waived"


def test_researcher_cannot_change_status(client: TestClient, admin_headers: dict, auth_headers: dict):
    item_id = _create_item(client, admin_headers)
    denied = client.patch(
        f"/api/v1/admin/compliance/checklist-items/{item_id}",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert denied.status_code == 403


def test_list_includes_notes_field(client: TestClient, admin_headers: dict):
    item_id = _create_item(client, admin_headers)
    client.patch(
        f"/api/v1/admin/compliance/checklist-items/{item_id}",
        json={"notes": "initial note body for list response"},
        headers=admin_headers,
    )
    r = client.get("/api/v1/admin/compliance/checklist-items", headers=admin_headers)
    assert r.status_code == 200
    items = r.json().get("items") or []
    match = next((i for i in items if i["id"] == item_id), None)
    assert match is not None
    assert "notes" in match
