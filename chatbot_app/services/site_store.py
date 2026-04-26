"""Helpers for per-site config, chunk storage, and knowledge base persistence."""

import json

import faiss

from chatbot_app.ai.engine import KnowledgeBase
from chatbot_app.config import DATA_DIR, DEFAULT_CONFIG
from chatbot_app.db.service import get_all_db_chunks

# Ensure the site storage root exists before any route tries to write into it.
DATA_DIR.mkdir(exist_ok=True)

site_stores = {}


def site_dir(site_id: str):
    """Return the filesystem directory for a specific site ID."""
    return DATA_DIR / site_id


def load_kb(site_id):
    """Load a site's persisted FAISS index and chunks if available."""
    base = site_dir(site_id)
    chunks_file = base / "chunks.json"
    index_file = base / "index.faiss"
    if chunks_file.exists() and index_file.exists():
        kb = KnowledgeBase()
        with chunks_file.open(encoding="utf-8") as handle:
            kb.chunks = json.load(handle)
        kb.index = faiss.read_index(str(index_file))
        return kb
    return None


def save_kb(site_id, kb):
    """Persist a site's chunks and vector index to disk."""
    base = site_dir(site_id)
    base.mkdir(parents=True, exist_ok=True)
    with (base / "chunks.json").open("w", encoding="utf-8") as handle:
        json.dump(kb.chunks, handle)
    faiss.write_index(kb.index, str(base / "index.faiss"))


def load_pdf_chunks(site_id) -> list:
    """Load PDF-sourced chunks kept separately from DB-derived chunks."""
    path = site_dir(site_id) / "pdf_chunks.json"
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    return []


def save_pdf_chunks(site_id, chunks: list):
    """Persist PDF chunks so the knowledge base can be rebuilt later."""
    base = site_dir(site_id)
    base.mkdir(parents=True, exist_ok=True)
    with (base / "pdf_chunks.json").open("w", encoding="utf-8") as handle:
        json.dump(chunks, handle)


def load_config(site_id):
    """Load site config merged on top of global defaults."""
    path = site_dir(site_id) / "config.json"
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            return {**DEFAULT_CONFIG, **json.load(handle)}
    return {**DEFAULT_CONFIG}


def save_config(site_id, config):
    """Save a site's widget and behavior configuration."""
    base = site_dir(site_id)
    base.mkdir(parents=True, exist_ok=True)
    with (base / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)


def load_db_configs(site_id) -> list:
    """Load DB configs, supporting both current and legacy file formats."""
    new_format = site_dir(site_id) / "db_configs.json"
    if new_format.exists():
        with new_format.open(encoding="utf-8") as handle:
            return json.load(handle)

    old_format = site_dir(site_id) / "db_config.json"
    if old_format.exists():
        with old_format.open(encoding="utf-8") as handle:
            config = json.load(handle)
        config.setdefault("id", "legacy")
        config.setdefault("label", "Database")
        return [config]
    return []


def save_db_configs(site_id, configs: list):
    """Persist DB configs and remove the old single-config file if present."""
    base = site_dir(site_id)
    base.mkdir(parents=True, exist_ok=True)
    with (base / "db_configs.json").open("w", encoding="utf-8") as handle:
        json.dump(configs, handle, indent=2)
    old_path = base / "db_config.json"
    if old_path.exists():
        old_path.unlink()


def rebuild_kb(site_id) -> KnowledgeBase:
    """Rebuild a site's KB from PDF chunks plus live DB-derived chunks."""
    pdf_chunks = load_pdf_chunks(site_id)
    db_configs = load_db_configs(site_id)
    db_chunks = get_all_db_chunks(db_configs) if db_configs else []
    all_chunks, _ = deduplicate(pdf_chunks + db_chunks)
    kb = KnowledgeBase()
    if all_chunks:
        kb.process_chunks(all_chunks)
    site_stores[site_id] = kb
    save_kb(site_id, kb)
    return kb


def get_kb(site_id):
    """Return the cached KB for a site, loading it from disk on first access."""
    if site_id not in site_stores:
        kb = load_kb(site_id)
        if kb:
            site_stores[site_id] = kb
    return site_stores.get(site_id)


def list_sites():
    """List every site folder currently stored under the data directory."""
    if not DATA_DIR.exists():
        return []
    return [entry.name for entry in DATA_DIR.iterdir() if entry.is_dir()]


def normalize_chunk(text: str) -> str:
    """Normalise chunk text for duplicate comparisons."""
    return " ".join(text.lower().split())


def find_duplicates(chunks: list) -> list:
    """Return duplicate metadata for chunks with identical normalized content."""
    seen = {}
    duplicates = []
    for index, chunk in enumerate(chunks):
        normalized = normalize_chunk(chunk)
        if normalized in seen:
            duplicates.append({"index": index, "duplicate_of": seen[normalized], "preview": chunk[:120]})
        else:
            seen[normalized] = index
    return duplicates


def deduplicate(chunks: list):
    """Remove duplicate chunks while preserving first-seen order."""
    seen = {}
    result = []
    for chunk in chunks:
        normalized = normalize_chunk(chunk)
        if normalized not in seen:
            seen[normalized] = True
            result.append(chunk)
    return result, len(chunks) - len(result)
