"""Additional integration coverage for chat service branches via the route layer."""

from __future__ import annotations

import sqlite3

import pytest

from tests.helpers.db_utils import create_owner_db, create_product_db, seed_product


@pytest.mark.integration
def test_chat_route_handles_llm_failure(client, isolated_app, monkeypatch):
    monkeypatch.setattr(isolated_app.chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(isolated_app.chat_service, "load_db_configs", lambda _site_id: [])
    monkeypatch.setattr(isolated_app.chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(
        isolated_app.chat_service,
        "generate_response",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("LLM offline")),
    )

    response = client.post("/chat", json={"site_id": "site123", "message": "Hello"})

    assert response.status_code == 200
    assert response.get_json()["message"] == "AI service temporarily unavailable."


@pytest.mark.integration
def test_chat_route_get_orders_formats_history(client, isolated_app, monkeypatch):
    monkeypatch.setattr(isolated_app.chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(isolated_app.chat_service, "load_db_configs", lambda _site_id: [{"path": "owner.db"}])
    monkeypatch.setattr(isolated_app.chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(isolated_app.chat_service, "build_effective_db_configs", lambda configs: configs)
    monkeypatch.setattr(
        isolated_app.chat_service,
        "generate_response",
        lambda **_kwargs: {"message": "Checking history.", "options": [], "links": [], "db_action": {"type": "get_orders"}},
    )
    monkeypatch.setattr(
        isolated_app.chat_service,
        "execute_db_action",
        lambda _configs, _action: {
            "ok": True,
            "result": {
                "orders": [
                    {"id": 4, "product_name": "Red Apple", "quantity": 2, "total_price": 5.0, "status": "confirmed", "created_at": "2026-04-25 09:00:00"}
                ]
            },
        },
    )

    response = client.post("/chat", json={"site_id": "site123", "message": "Show my orders"})

    assert response.status_code == 200
    assert "Here are your 1 order" in response.get_json()["message"]


@pytest.mark.integration
def test_chat_route_lookup_user_follow_up_reply(client, isolated_app, monkeypatch):
    monkeypatch.setattr(isolated_app.chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(isolated_app.chat_service, "load_db_configs", lambda _site_id: [{"path": "customer.db"}])
    monkeypatch.setattr(isolated_app.chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(isolated_app.chat_service, "build_effective_db_configs", lambda configs: configs)
    monkeypatch.setattr(
        isolated_app.chat_service,
        "execute_db_action",
        lambda _configs, _action: {
            "ok": True,
            "result": {"found": True, "user": {"name": "Alice", "email": "alice@example.com", "address": "10 Downing St"}},
        },
    )

    calls = []

    def fake_generate_response(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {"message": "Looking up.", "options": [], "links": [], "db_action": {"type": "lookup_user"}}
        return {"message": "I found your account details.", "options": [], "links": []}

    monkeypatch.setattr(isolated_app.chat_service, "generate_response", fake_generate_response)

    response = client.post("/chat", json={"site_id": "site123", "message": "Find my account"})

    assert response.status_code == 200
    assert response.get_json()["message"] == "I found your account details."
    assert "USER LOOKUP: Found account." in calls[1]["retrieved_chunks"][0]


@pytest.mark.integration
def test_chat_route_requires_complete_address_before_confirmation(client, isolated_app, monkeypatch):
    monkeypatch.setattr(isolated_app.chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(isolated_app.chat_service, "load_db_configs", lambda _site_id: [{"path": "owner.db"}])
    monkeypatch.setattr(isolated_app.chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(isolated_app.chat_service, "build_effective_db_configs", lambda configs: configs)
    monkeypatch.setattr(
        isolated_app.chat_service,
        "generate_response",
        lambda **_kwargs: {
            "message": "Placing order.",
            "options": [],
            "links": [],
            "db_action": {"type": "create_order", "data": {"delivery_address": "London", "product_id": 1}},
        },
    )
    monkeypatch.setattr(
        isolated_app.chat_service,
        "execute_db_action",
        lambda _configs, _action: {"ok": True, "result": {"order_id": 1, "product": "Red Apple", "quantity": 1, "total": 1.25}},
    )

    response = client.post("/chat", json={"site_id": "site123", "message": "Order apples"})

    assert response.status_code == 200
    assert "complete delivery address" in response.get_json()["message"]


@pytest.mark.integration
def test_chat_route_real_db_action_creates_order(client, isolated_app, monkeypatch):
    product_db = create_product_db(isolated_app.data_dir.parent / "products.db")
    seed_product(product_db, stock=6)
    create_owner_db(isolated_app.owner_db)
    isolated_app.site_store.save_db_configs(
        "site123",
        [{"type": "sqlite", "path": str(product_db), "label": "Products"}],
    )

    monkeypatch.setattr(isolated_app.chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(isolated_app.chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(
        isolated_app.chat_service,
        "generate_response",
        lambda **_kwargs: {
            "message": "Placing order.",
            "options": [],
            "links": [],
            "db_action": {
                "type": "create_order",
                "data": {
                    "customer_id": 1,
                    "user_id": 1,
                    "user_email": "alice@example.com",
                    "user_name": "Alice",
                    "product_id": 1,
                    "product_name": "Red Apple",
                    "quantity": 2,
                    "delivery_address": "10 Downing St, London, SW1A 2AA",
                },
            },
        },
    )

    response = client.post("/chat", json={"site_id": "site123", "message": "Order two apples"})

    payload = response.get_json()
    assert response.status_code == 200
    assert "Your order is confirmed." in payload["message"]

    with sqlite3.connect(product_db) as connection:
        stock = connection.execute("SELECT stock FROM products WHERE id = 1").fetchone()[0]
    assert stock == 4
