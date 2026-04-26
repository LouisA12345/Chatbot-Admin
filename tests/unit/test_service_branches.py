"""Additional unit tests for service-layer branches and error handling."""

from __future__ import annotations

import json
import sqlite3

import pytest

from tests.helpers.db_utils import create_customer_db, create_owner_db, create_sample_service_dbs, seed_customer, seed_order, seed_product
from tests.helpers.runtime import import_fresh


@pytest.fixture
def db_service():
    return import_fresh("chatbot_app.db.service")


@pytest.fixture
def chat_service():
    return import_fresh("chatbot_app.services.chat_service")


@pytest.fixture
def site_store():
    module = import_fresh("chatbot_app.services.site_store")
    return module


@pytest.mark.unit
def test_get_db_chunks_rejects_unsupported_type(db_service):
    with pytest.raises(ValueError):
        db_service.get_db_chunks({"type": "mysql"})


@pytest.mark.unit
def test_get_all_db_chunks_skips_faulty_sources(db_service, tmp_path):
    _, _, product_db = create_sample_service_dbs(tmp_path)
    seed_product(product_db)

    chunks = db_service.get_all_db_chunks(
        [
            {"type": "sqlite", "path": str(product_db), "label": "Products"},
            {"type": "sqlite", "path": "", "label": "Broken"},
        ]
    )

    assert any("Red Apple" in chunk for chunk in chunks)


@pytest.mark.unit
def test_create_order_and_get_orders_cover_error_branches(db_service, tmp_path):
    customer_db, owner_db, product_db = create_sample_service_dbs(tmp_path)
    customer_id = seed_customer(customer_db)
    product_id = seed_product(product_db)

    missing_product = db_service.execute_db_action(
        [{"type": "sqlite", "path": str(product_db), "label": "Products"}],
        {"type": "create_order", "data": {"product_id": product_id}},
    )
    assert missing_product["error"] == "No orders database connected."

    out_of_stock = db_service._create_order(
        {"type": "sqlite", "path": str(product_db), "label": "Products"},
        {"type": "sqlite", "path": str(owner_db), "label": "Orders"},
        {"data": {"product_id": product_id, "quantity": 99, "customer_id": customer_id}},
    )
    assert "Only" in out_of_stock["error"]

    missing = db_service._create_order(
        {"type": "sqlite", "path": str(product_db), "label": "Products"},
        {"type": "sqlite", "path": str(owner_db), "label": "Orders"},
        {"data": {"product_id": 999, "quantity": 1, "customer_id": customer_id}},
    )
    assert missing["error"] == "Product not found."

    not_supported = db_service._get_user_orders({"type": "postgresql"}, {})
    assert not_supported["error"] == "user_email or customer_id required."


@pytest.mark.unit
def test_get_user_orders_and_register_customer_branches(db_service, tmp_path):
    customer_db, owner_db, _ = create_sample_service_dbs(tmp_path)
    customer_id = seed_customer(customer_db)
    seed_order(owner_db, customer_id=customer_id)

    invalid_id = db_service._get_user_orders({"type": "sqlite", "path": str(owner_db)}, {"customer_id": "bad-id"})
    assert invalid_id["result"]["count"] == 0

    by_email = db_service._get_user_orders({"type": "sqlite", "path": str(owner_db)}, {"user_email": "alice@example.com"})
    assert by_email["result"]["count"] == 1

    missing_data = db_service._register_customer({"type": "sqlite", "path": str(customer_db)}, {"data": {"email": ""}})
    assert missing_data["error"] == "Name and email are required."

    created = db_service._register_customer(
        {"type": "sqlite", "path": str(customer_db)},
        {"data": {"name": "Bob", "email": "bob@example.com", "phone": "123", "address": "Somewhere"}},
    )
    assert created["ok"] is True

    duplicate = db_service._register_customer(
        {"type": "sqlite", "path": str(customer_db)},
        {"data": {"name": "Bob", "email": "bob@example.com"}},
    )
    assert "already exists" in duplicate["error"]


@pytest.mark.unit
def test_lookup_find_and_get_orders_helpers(db_service, tmp_path):
    customer_db, owner_db, _ = create_sample_service_dbs(tmp_path)
    customer_id = seed_customer(customer_db)
    seed_order(owner_db, customer_id=customer_id)

    found = db_service._find_db_with_table(
        [
            {"type": "sqlite", "path": str(customer_db)},
            {"type": "sqlite", "path": str(owner_db)},
        ],
        "orders",
    )
    assert found["path"] == str(owner_db)

    missing = db_service._find_db_with_table([{"type": "sqlite", "path": str(customer_db)}], "unknown")
    assert missing is None

    no_customer = db_service._lookup_customer({"type": "sqlite", "path": "missing.db"}, "nobody@example.com")
    assert no_customer is None

    orders = db_service.get_orders({"type": "sqlite", "path": str(owner_db)}, limit=5)
    assert len(orders) == 1

    assert db_service.get_orders({"type": "sqlite", "path": "missing.db"}) == []


@pytest.mark.unit
def test_site_store_legacy_configs_and_duplicates(site_store, tmp_path, monkeypatch):
    site_store.DATA_DIR = tmp_path / "data"
    site_store.DATA_DIR.mkdir(parents=True, exist_ok=True)
    site_store.site_stores.clear()

    base = site_store.site_dir("site-a")
    base.mkdir(parents=True, exist_ok=True)
    (base / "db_config.json").write_text(json.dumps({"type": "sqlite", "path": "legacy.db"}), encoding="utf-8")

    configs = site_store.load_db_configs("site-a")
    assert configs[0]["id"] == "legacy"
    assert configs[0]["label"] == "Database"

    duplicates = site_store.find_duplicates(["Hello World", " hello   world ", "Another"])
    assert duplicates == [{"index": 1, "duplicate_of": 0, "preview": " hello   world "}]

    site_store.save_pdf_chunks("site-a", ["One", "Two"])
    assert site_store.load_pdf_chunks("site-a") == ["One", "Two"]
    assert sorted(site_store.list_sites()) == ["site-a"]


@pytest.mark.unit
def test_site_store_get_kb_loads_from_disk(site_store, tmp_path):
    site_store.DATA_DIR = tmp_path / "data"
    site_store.DATA_DIR.mkdir(parents=True, exist_ok=True)
    site_store.site_stores.clear()

    kb = site_store.KnowledgeBase()
    kb.process_chunks(["Stored knowledge"])
    site_store.save_kb("site-a", kb)

    loaded = site_store.get_kb("site-a")
    assert loaded.chunks == ["Stored knowledge"]
    assert site_store.get_kb("site-a") is loaded


@pytest.mark.unit
def test_chat_service_branch_helpers(chat_service, tmp_path):
    assert chat_service.looks_like_full_address("10 Downing St, London, SW1A 2AA") is True
    assert chat_service.looks_like_full_address("London") is False

    assert chat_service.format_order_history([])["options"] == ["Browse Products"]
    history = chat_service.format_order_history(
        [{"id": 7, "product_name": "Red Apple", "quantity": 2, "total_price": 5.0, "status": "confirmed", "created_at": "2026-04-25 10:00:00"}]
    )
    assert "Order #7" in history["message"]


@pytest.mark.unit
def test_chat_service_live_chunks_and_follow_up_paths(chat_service, tmp_path, monkeypatch):
    db_path = tmp_path / "products.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL)")
    connection.execute("INSERT INTO products (name, price) VALUES (?, ?)", ("Red Apple", 1.25))
    connection.commit()
    connection.close()

    live_chunks = chat_service.gather_live_chunks("What products do you have?", [{"type": "sqlite", "path": str(db_path), "label": "Products"}])
    assert any("Red Apple" in chunk for chunk in live_chunks)
    assert chat_service.gather_live_chunks("Hello there", [{"type": "sqlite", "path": str(db_path)}]) == []

    monkeypatch.setattr(chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(chat_service, "load_db_configs", lambda _site_id: [{"path": str(db_path)}])
    monkeypatch.setattr(chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(chat_service, "build_effective_db_configs", lambda configs: configs)
    monkeypatch.setattr(
        chat_service,
        "execute_db_action",
        lambda _configs, _action: {"ok": True, "result": {"found": True, "user": {"name": "Alice", "email": "alice@example.com", "address": "10 Downing St"}}},
    )

    calls = []

    def fake_generate_response(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {"message": "Checking account.", "options": [], "links": [], "db_action": {"type": "lookup_user"}}
        return {"message": "Found your account.", "options": [], "links": [], "db_action": "should be removed"}

    monkeypatch.setattr(chat_service, "generate_response", fake_generate_response)

    payload, status = chat_service.handle_chat_payload({"site_id": "site123", "message": "Find my account"})
    assert status == 200
    assert payload["message"] == "Found your account."
    assert payload["db_action"] is None
    assert "USER LOOKUP" in calls[1]["retrieved_chunks"][0]


@pytest.mark.unit
def test_chat_service_invalid_address_and_llm_failures(chat_service, monkeypatch):
    monkeypatch.setattr(chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(chat_service, "load_db_configs", lambda _site_id: [{"path": "owner.db"}])
    monkeypatch.setattr(chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(chat_service, "build_effective_db_configs", lambda configs: configs)
    monkeypatch.setattr(
        chat_service,
        "generate_response",
        lambda **_kwargs: {
            "message": "Placing order.",
            "options": [],
            "links": [],
            "db_action": {"type": "create_order", "data": {"delivery_address": "London", "product_id": 1}},
        },
    )
    monkeypatch.setattr(chat_service, "execute_db_action", lambda _configs, _action: {"ok": True, "result": {"order_id": 1, "product": "Red Apple", "quantity": 1, "total": 1.25}})

    payload, status = chat_service.handle_chat_payload({"site_id": "site123", "message": "Order please"})
    assert status == 200
    assert "complete delivery address" in payload["message"]

    monkeypatch.setattr(chat_service, "load_db_configs", lambda _site_id: [])
    monkeypatch.setattr(chat_service, "generate_response", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("LLM down")))
    payload, status = chat_service.handle_chat_payload({"site_id": "site123", "message": "Hello"})
    assert status == 200
    assert payload["message"] == "AI service temporarily unavailable."
