import json
import os
import shutil
import tempfile
import uuid

from flask import Blueprint, jsonify, request

from chatbot_app.ai.engine import KnowledgeBase
from chatbot_app.config import DEFAULT_CONFIG
from chatbot_app.db.service import test_connection
from chatbot_app.security import require_admin_key
from chatbot_app.services.site_store import (
    deduplicate,
    find_duplicates,
    get_kb,
    list_sites,
    load_config,
    load_db_configs,
    load_pdf_chunks,
    rebuild_kb,
    save_config,
    save_db_configs,
    save_kb,
    save_pdf_chunks,
    site_dir,
    site_stores,
)

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/sites", methods=["GET"])
@require_admin_key
def get_sites():
    sites = []
    for site_id in list_sites():
        config = load_config(site_id)
        chunks_file = site_dir(site_id) / "chunks.json"
        chunk_count = 0
        if chunks_file.exists():
            try:
                with chunks_file.open(encoding="utf-8") as handle:
                    chunk_count = len(json.load(handle))
            except Exception:
                chunk_count = 0
        db_configs = load_db_configs(site_id)
        sites.append(
            {
                "site_id": site_id,
                "bot_name": config.get("bot_name", site_id),
                "has_knowledge": chunks_file.exists(),
                "has_db": len(db_configs) > 0,
                "db_count": len(db_configs),
                "chunk_count": chunk_count,
                "accent_color": config.get("accent_color", "#667eea"),
            }
        )
    return jsonify({"sites": sites})


@admin_bp.route("/admin/sites", methods=["POST"])
@require_admin_key
def create_site():
    data = request.json or {}
    site_id = data.get("site_id", "").strip().replace(" ", "_")
    if not site_id:
        return jsonify({"error": "site_id required"}), 400
    if site_dir(site_id).exists():
        return jsonify({"error": f"'{site_id}' exists"}), 409
    site_dir(site_id).mkdir(parents=True, exist_ok=True)
    save_config(site_id, {**DEFAULT_CONFIG, **{key: value for key, value in data.items() if key != "site_id"}})
    return jsonify({"message": f"Site '{site_id}' created.", "site_id": site_id})


@admin_bp.route("/admin/sites/<site_id>", methods=["DELETE"])
@require_admin_key
def delete_site(site_id):
    path = site_dir(site_id)
    if not path.exists():
        return jsonify({"error": "Not found"}), 404
    shutil.rmtree(path)
    site_stores.pop(site_id, None)
    return jsonify({"message": f"Site '{site_id}' deleted."})


@admin_bp.route("/admin/upload", methods=["POST"])
@require_admin_key
def upload_knowledge():
    site_id = request.form.get("site_id")
    file = request.files.get("file")
    if not site_id or not file:
        return jsonify({"error": "Missing site_id or file"}), 400

    site_dir(site_id).mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{site_id}.pdf")
    temp_file.close()
    file.save(temp_file.name)
    try:
        temp_kb = KnowledgeBase()
        temp_kb.process_pdf(temp_file.name)
        if not temp_kb.chunks:
            return jsonify({"error": "No text in PDF"}), 422
        save_pdf_chunks(site_id, temp_kb.chunks)
        kb = rebuild_kb(site_id)
        return jsonify({"message": "PDF indexed.", "chunks": len(kb.chunks)})
    finally:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)


@admin_bp.route("/admin/db/<site_id>", methods=["GET"])
@require_admin_key
def get_databases(site_id):
    configs = load_db_configs(site_id)
    safe_configs = [{**config, "password": "********" if config.get("password") else ""} for config in configs]
    return jsonify({"databases": safe_configs, "count": len(safe_configs)})


@admin_bp.route("/admin/db/test", methods=["POST"])
@require_admin_key
def test_db_endpoint():
    return jsonify(test_connection(request.json or {}))


@admin_bp.route("/admin/db/<site_id>/add", methods=["POST"])
@require_admin_key
def add_database(site_id):
    db_config = request.json or {}
    if not db_config:
        return jsonify({"error": "No config"}), 400
    db_config.setdefault("id", str(uuid.uuid4())[:8])

    result = test_connection(db_config)
    if not result["ok"]:
        return jsonify({"error": f"Connection failed: {result['error']}"}), 422

    site_dir(site_id).mkdir(parents=True, exist_ok=True)
    configs = [config for config in load_db_configs(site_id) if config.get("id") != db_config["id"]]
    configs.append(db_config)
    save_db_configs(site_id, configs)
    kb = rebuild_kb(site_id)
    return jsonify(
        {
            "message": f"'{db_config.get('label', 'DB')}' added. {len(kb.chunks)} total chunks.",
            "chunks": len(kb.chunks),
            "id": db_config["id"],
        }
    )


@admin_bp.route("/admin/db/<site_id>/<db_id>", methods=["DELETE"])
@require_admin_key
def remove_database(site_id, db_id):
    configs = [config for config in load_db_configs(site_id) if config.get("id") != db_id]
    save_db_configs(site_id, configs)
    kb = rebuild_kb(site_id)
    return jsonify({"message": "Database removed.", "chunks": len(kb.chunks)})


@admin_bp.route("/admin/db/<site_id>/<db_id>/sync", methods=["POST"])
@require_admin_key
def sync_one_database(site_id, db_id):
    config = next((config for config in load_db_configs(site_id) if config.get("id") == db_id), None)
    if not config:
        return jsonify({"error": "Not found"}), 404
    kb = rebuild_kb(site_id)
    return jsonify({"message": f"Synced. {len(kb.chunks)} total chunks.", "chunks": len(kb.chunks)})


@admin_bp.route("/admin/db/<site_id>/sync-all", methods=["POST"])
@require_admin_key
def sync_all_databases(site_id):
    if not load_db_configs(site_id):
        return jsonify({"error": "No databases connected."}), 404
    kb = rebuild_kb(site_id)
    return jsonify({"message": f"All synced. {len(kb.chunks)} total chunks.", "chunks": len(kb.chunks)})


@admin_bp.route("/admin/pdf-chunks/<site_id>", methods=["GET"])
@require_admin_key
def get_pdf_chunk_count(site_id):
    return jsonify({"count": len(load_pdf_chunks(site_id))})


@admin_bp.route("/admin/chunks/<site_id>/duplicates", methods=["GET"])
@require_admin_key
def check_duplicates(site_id):
    kb = get_kb(site_id)
    if not kb:
        return jsonify({"duplicates": [], "count": 0, "total": 0})
    duplicates = find_duplicates(kb.chunks)
    return jsonify({"duplicates": duplicates, "count": len(duplicates), "total": len(kb.chunks)})


@admin_bp.route("/admin/chunks/<site_id>/deduplicate", methods=["POST"])
@require_admin_key
def deduplicate_chunks_route(site_id):
    kb = get_kb(site_id)
    if not kb:
        return jsonify({"error": "No knowledge base found"}), 404
    clean_chunks, removed = deduplicate(kb.chunks)
    kb.chunks = clean_chunks
    if clean_chunks:
        kb._build_index()
    else:
        kb.index = None
    site_stores[site_id] = kb
    save_kb(site_id, kb)
    pdf_clean, _ = deduplicate(load_pdf_chunks(site_id))
    save_pdf_chunks(site_id, pdf_clean)
    return jsonify({"message": f"Removed {removed} duplicate chunk(s).", "removed": removed, "total": len(clean_chunks)})


@admin_bp.route("/admin/chunks/<site_id>", methods=["GET"])
@require_admin_key
def list_chunks(site_id):
    kb = get_kb(site_id)
    if not kb:
        return jsonify({"chunks": [], "total": 0})

    query = request.args.get("q", "").lower()
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    matching = [{"index": index, "text": chunk} for index, chunk in enumerate(kb.chunks) if not query or query in chunk.lower()]
    start = (page - 1) * limit
    return jsonify({"chunks": matching[start : start + limit], "total": len(matching), "page": page, "limit": limit})


@admin_bp.route("/admin/chunks/<site_id>/<int:index>", methods=["DELETE"])
@require_admin_key
def delete_chunk(site_id, index):
    kb = get_kb(site_id)
    if not kb or index >= len(kb.chunks):
        return jsonify({"error": "Chunk not found"}), 404
    kb.chunks.pop(index)
    if kb.chunks:
        kb._build_index()
    else:
        kb.index = None
    site_stores[site_id] = kb
    save_kb(site_id, kb)

    pdf_chunks = load_pdf_chunks(site_id)
    if index < len(pdf_chunks):
        pdf_chunks.pop(index)
        save_pdf_chunks(site_id, pdf_chunks)
    return jsonify({"message": "Chunk deleted.", "total": len(kb.chunks)})


@admin_bp.route("/admin/chunks/<site_id>/<int:index>", methods=["PUT"])
@require_admin_key
def edit_chunk(site_id, index):
    kb = get_kb(site_id)
    if not kb or index >= len(kb.chunks):
        return jsonify({"error": "Chunk not found"}), 404
    data = request.json or {}
    new_text = (data.get("text") or "").strip()
    if not new_text:
        return jsonify({"error": "Text is required"}), 400
    kb.chunks[index] = new_text
    kb._build_index()
    site_stores[site_id] = kb
    save_kb(site_id, kb)

    pdf_chunks = load_pdf_chunks(site_id)
    if index < len(pdf_chunks):
        pdf_chunks[index] = new_text
        save_pdf_chunks(site_id, pdf_chunks)
    return jsonify({"message": "Chunk updated."})


@admin_bp.route("/admin/chunks/<site_id>", methods=["POST"])
@require_admin_key
def add_chunk(site_id):
    data = request.json or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Text is required"}), 400

    site_dir(site_id).mkdir(parents=True, exist_ok=True)
    kb = get_kb(site_id) or KnowledgeBase()
    kb.chunks.append(text)
    kb._build_index()
    site_stores[site_id] = kb
    save_kb(site_id, kb)

    pdf_chunks = load_pdf_chunks(site_id)
    pdf_chunks.append(text)
    save_pdf_chunks(site_id, pdf_chunks)
    return jsonify({"message": "Chunk added.", "total": len(kb.chunks), "index": len(kb.chunks) - 1})


@admin_bp.route("/admin/config/<site_id>", methods=["GET"])
@require_admin_key
def get_config(site_id):
    return jsonify(load_config(site_id))


@admin_bp.route("/admin/config/<site_id>", methods=["POST"])
@require_admin_key
def update_config(site_id):
    data = request.json or {}
    if not data:
        return jsonify({"error": "No data"}), 400
    site_dir(site_id).mkdir(parents=True, exist_ok=True)
    merged = {**load_config(site_id), **data}
    save_config(site_id, merged)
    return jsonify({"message": "Config saved.", "config": merged})
