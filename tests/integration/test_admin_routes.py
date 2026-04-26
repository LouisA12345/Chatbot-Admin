"""Integration tests for admin endpoints and protected configuration flows."""

from __future__ import annotations

import io

import pytest


@pytest.mark.integration
def test_valid_api_key_works(client):
    """Protected admin endpoints should accept a valid admin API key."""
    response = client.get("/admin/sites", headers={"X-Admin-Key": "test-admin-key"})

    assert response.status_code == 200
    assert "sites" in response.get_json()


@pytest.mark.integration
def test_missing_api_key_fails(client):
    """Protected admin endpoints should reject requests without the admin key."""
    response = client.get("/admin/sites")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Unauthorized"


@pytest.mark.integration
def test_config_update_persists(client):
    """Admin config updates should persist and be readable afterward."""
    headers = {"X-Admin-Key": "test-admin-key"}

    create = client.post("/admin/sites", json={"site_id": "site123"}, headers=headers)
    update = client.post("/admin/config/site123", json={"bot_name": "Research Bot"}, headers=headers)
    fetch = client.get("/admin/config/site123", headers=headers)

    assert create.status_code == 200
    assert update.status_code == 200
    assert fetch.get_json()["bot_name"] == "Research Bot"


@pytest.mark.integration
def test_pdf_upload_triggers_processing(client, isolated_app, monkeypatch):
    """Uploading a PDF should trigger mocked processing and KB rebuild flow."""
    headers = {"X-Admin-Key": "test-admin-key"}

    def fake_process_pdf(self, _path):
        self.chunks = ["Parsed PDF knowledge chunk"]
        self._build_index()

    monkeypatch.setattr(isolated_app.admin.KnowledgeBase, "process_pdf", fake_process_pdf)
    monkeypatch.setattr(
        isolated_app.admin,
        "rebuild_kb",
        lambda _site_id: type("KB", (), {"chunks": ["Parsed PDF knowledge chunk"]})(),
    )

    response = client.post(
        "/admin/upload",
        headers=headers,
        data={"site_id": "site123", "file": (io.BytesIO(b"Mock PDF payload"), "sample.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["chunks"] == 1
