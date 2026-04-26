"""Additional integration coverage for admin and public endpoints."""

from __future__ import annotations

import pytest
import numpy as np

from tests.helpers.db_utils import create_product_db, seed_product


def _headers():
    return {"X-Admin-Key": "test-admin-key"}


class FakeKb:
    def __init__(self, chunks=None):
        self.chunks = list(chunks or [])
        self.index = None
        if self.chunks:
            self._build_index()

    def _build_index(self):
        self.index = type("Index", (), {"dim": 1, "vectors": np.array([[float(i)] for i in range(len(self.chunks))], dtype="float32")})()


@pytest.mark.integration
def test_create_delete_and_duplicate_site_paths(client):
    create = client.post("/admin/sites", json={"site_id": "new site"}, headers=_headers())
    duplicate = client.post("/admin/sites", json={"site_id": "new_site"}, headers=_headers())
    delete = client.delete("/admin/sites/new_site", headers=_headers())
    missing = client.delete("/admin/sites/new_site", headers=_headers())

    assert create.status_code == 200
    assert create.get_json()["site_id"] == "new_site"
    assert duplicate.status_code == 409
    assert delete.status_code == 200
    assert missing.status_code == 404


@pytest.mark.integration
def test_admin_database_endpoints_cover_success_and_errors(client, isolated_app, monkeypatch):
    monkeypatch.setattr(isolated_app.admin, "test_connection", lambda config: {"ok": bool(config.get("path")), "row_count": 2, "error": "bad"} if not config.get("path") else {"ok": True, "row_count": 2})
    monkeypatch.setattr(isolated_app.admin, "rebuild_kb", lambda _site_id: type("KB", (), {"chunks": ["A", "B"]})())
    monkeypatch.setattr(
        isolated_app.admin,
        "load_db_configs",
        lambda _site_id: [{"id": "db1", "path": "sample.db", "label": "Main", "password": "secret"}],
    )

    get_resp = client.get("/admin/db/site123", headers=_headers())
    test_resp = client.post("/admin/db/test", json={"path": "db.sqlite"}, headers=_headers())
    add_missing = client.post("/admin/db/site123/add", json={}, headers=_headers())
    add_ok = client.post("/admin/db/site123/add", json={"path": "db.sqlite", "label": "Main"}, headers=_headers())
    remove_ok = client.delete("/admin/db/site123/db1", headers=_headers())

    assert get_resp.get_json()["databases"][0]["password"] == "********"
    assert test_resp.get_json()["ok"] is True
    assert add_missing.status_code == 400
    assert add_ok.status_code == 200
    assert remove_ok.get_json()["chunks"] == 2


@pytest.mark.integration
def test_admin_database_sync_and_chunk_utility_endpoints(client, isolated_app, monkeypatch):
    kb = FakeKb(["Hello world", " hello   world ", "Unique"])
    isolated_app.admin.site_stores["site123"] = kb
    isolated_app.site_store.save_pdf_chunks("site123", ["Hello world", " hello   world "])
    monkeypatch.setattr(isolated_app.admin, "get_kb", lambda _site_id: isolated_app.admin.site_stores.get("site123"))
    monkeypatch.setattr(isolated_app.admin, "rebuild_kb", lambda _site_id: type("KB", (), {"chunks": ["One", "Two", "Three"]})())
    monkeypatch.setattr(isolated_app.admin, "load_db_configs", lambda _site_id: [{"id": "db1", "path": "a.db"}])

    sync_one_missing = client.post("/admin/db/site123/unknown/sync", headers=_headers())
    sync_one = client.post("/admin/db/site123/db1/sync", headers=_headers())
    sync_all = client.post("/admin/db/site123/sync-all", headers=_headers())
    pdf_count = client.get("/admin/pdf-chunks/site123", headers=_headers())
    duplicates = client.get("/admin/chunks/site123/duplicates", headers=_headers())
    dedupe = client.post("/admin/chunks/site123/deduplicate", headers=_headers())

    assert sync_one_missing.status_code == 404
    assert sync_one.get_json()["chunks"] == 3
    assert sync_all.get_json()["chunks"] == 3
    assert pdf_count.get_json()["count"] == 2
    assert duplicates.get_json()["count"] == 1
    assert dedupe.get_json()["removed"] == 1


@pytest.mark.integration
def test_admin_chunk_crud_and_public_config(client, isolated_app, monkeypatch):
    isolated_app.admin.site_stores["site123"] = FakeKb(["First chunk", "Second chunk"])
    isolated_app.site_store.save_pdf_chunks("site123", ["First chunk", "Second chunk"])
    monkeypatch.setattr(isolated_app.admin, "get_kb", lambda _site_id: isolated_app.admin.site_stores.get("site123"))
    monkeypatch.setattr(isolated_app.admin, "save_kb", lambda _site_id, _kb: None)

    list_resp = client.get("/admin/chunks/site123?q=first&page=1&limit=5", headers=_headers())
    add_bad = client.post("/admin/chunks/site123", json={"text": ""}, headers=_headers())
    add_ok = client.post("/admin/chunks/site123", json={"text": "Third chunk"}, headers=_headers())
    edit_bad = client.put("/admin/chunks/site123/0", json={"text": ""}, headers=_headers())
    edit_ok = client.put("/admin/chunks/site123/1", json={"text": "Updated chunk"}, headers=_headers())
    delete_missing = client.delete("/admin/chunks/site123/99", headers=_headers())
    delete_ok = client.delete("/admin/chunks/site123/0", headers=_headers())
    public_cfg = client.get("/config/site123")

    assert list_resp.get_json()["total"] == 1
    assert add_bad.status_code == 400
    assert add_ok.get_json()["total"] == 3
    assert edit_bad.status_code == 400
    assert edit_ok.status_code == 200
    assert delete_missing.status_code == 404
    assert delete_ok.status_code == 200
    assert "bot_name" in public_cfg.get_json()


@pytest.mark.integration
def test_admin_add_database_uses_real_sqlite_connection(client, isolated_app):
    product_db = create_product_db(isolated_app.data_dir.parent / "products.db")
    seed_product(product_db)

    response = client.post(
        "/admin/db/site123/add",
        json={"type": "sqlite", "path": str(product_db), "label": "Products"},
        headers=_headers(),
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["chunks"] >= 1

    db_listing = client.get("/admin/db/site123", headers=_headers()).get_json()
    assert db_listing["count"] == 1

    sites = client.get("/admin/sites", headers=_headers()).get_json()
    assert sites["sites"][0]["has_db"] is True
