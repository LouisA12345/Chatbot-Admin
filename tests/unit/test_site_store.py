"""Unit tests for per-site storage and cache lifecycle behavior."""

from __future__ import annotations

import pytest

from tests.helpers.runtime import import_fresh


@pytest.fixture
def site_store(tmp_path):
    """Import site_store against a temporary data directory."""
    module = import_fresh("chatbot_app.services.site_store")
    module.DATA_DIR = tmp_path / "data"
    module.DATA_DIR.mkdir(parents=True, exist_ok=True)
    module.site_stores.clear()
    return module


@pytest.mark.unit
def test_load_and_save_config(site_store):
    """Saving config should persist custom values and preserve defaults."""
    site_store.save_config("site-a", {"bot_name": "Academic Bot"})

    config = site_store.load_config("site-a")

    assert config["bot_name"] == "Academic Bot"
    assert config["status_text"] == site_store.DEFAULT_CONFIG["status_text"]


@pytest.mark.unit
def test_cache_invalidation_via_rebuild(site_store, monkeypatch):
    """Rebuilding the KB should refresh the in-memory cache with new content."""
    site_store.save_pdf_chunks("site-a", ["First chunk"])
    site_store.save_db_configs("site-a", [{"id": "db1", "path": "sample.db", "label": "Main DB"}])
    monkeypatch.setattr(site_store, "get_all_db_chunks", lambda _configs: ["Fresh DB chunk"])

    kb = site_store.rebuild_kb("site-a")

    assert "First chunk" in kb.chunks
    assert "Fresh DB chunk" in site_store.site_stores["site-a"].chunks


@pytest.mark.unit
def test_knowledge_base_loads_correctly(site_store):
    """Persisted knowledge base data should round-trip from disk correctly."""
    kb = site_store.KnowledgeBase()
    kb.process_chunks(["Alpha knowledge", "Beta knowledge"])

    site_store.save_kb("site-a", kb)
    loaded = site_store.load_kb("site-a")

    assert loaded is not None
    assert loaded.chunks == ["Alpha knowledge", "Beta knowledge"]
    assert loaded.index is not None


@pytest.mark.unit
def test_deduplication_removes_duplicates(site_store):
    """Duplicate chunks should be removed after case and whitespace normalization."""
    deduped, removed = site_store.deduplicate(["Hello world", " hello   world ", "Unique"])

    assert deduped == ["Hello world", "Unique"]
    assert removed == 1
