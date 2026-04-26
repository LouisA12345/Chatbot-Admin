"""Unit tests for chat orchestration and DB action handling."""

from __future__ import annotations

import pytest

from tests.helpers.runtime import import_fresh


@pytest.fixture
def chat_service():
    """Import chat_service fresh so monkeypatches stay isolated."""
    return import_fresh("chatbot_app.services.chat_service")


@pytest.mark.unit
def test_valid_chat_request_works(chat_service, monkeypatch):
    """A normal chat payload should return a structured assistant response."""
    monkeypatch.setattr(chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(chat_service, "load_db_configs", lambda _site_id: [])
    monkeypatch.setattr(chat_service, "load_config", lambda _site_id: {"personality": "friendly", "custom_rules": ""})
    monkeypatch.setattr(
        chat_service,
        "generate_response",
        lambda **_kwargs: {"message": "Hello from the chatbot.", "options": [], "links": [], "db_action": None},
    )

    payload, status = chat_service.handle_chat_payload({"site_id": "site123", "message": "Hello"})

    assert status == 200
    assert payload["message"] == "Hello from the chatbot."


@pytest.mark.unit
def test_missing_input_handled(chat_service):
    """Missing or empty payloads should return safe non-crashing responses."""
    missing_payload, missing_status = chat_service.handle_chat_payload(None)
    empty_payload, empty_status = chat_service.handle_chat_payload({"site_id": "site123", "message": ""})

    assert missing_status == 400
    assert missing_payload["error"] == "Invalid request."
    assert empty_status == 200
    assert empty_payload["reply"] == "Please enter a message."


@pytest.mark.unit
def test_db_enrichment_works(chat_service, monkeypatch):
    """Logged-in users without an address should be enriched from the customer DB."""
    monkeypatch.setattr(chat_service, "_find_db_with_table", lambda _configs, _table: {"path": "dummy.db"})
    monkeypatch.setattr(chat_service, "_lookup_customer", lambda _config, _email: {"id": 7, "address": "22 Baker St, London, NW1 6XE"})

    enriched = chat_service.enrich_user_info({"email": "alice@example.com", "name": "Alice"}, [{"path": "dummy.db"}])

    assert enriched["address"] == "22 Baker St, London, NW1 6XE"
    assert enriched["user_id"] == 7


@pytest.mark.unit
def test_order_flow_triggers_db_actions(chat_service, monkeypatch):
    """A create_order action should call the DB layer and return formatted confirmation."""
    monkeypatch.setattr(chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(chat_service, "load_db_configs", lambda _site_id: [{"path": "owner.db"}])
    monkeypatch.setattr(chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(chat_service, "build_effective_db_configs", lambda _configs: [{"path": "owner.db"}])
    monkeypatch.setattr(
        chat_service,
        "generate_response",
        lambda **_kwargs: {
            "message": "Placing your order.",
            "options": [],
            "links": [],
            "db_action": {
                "type": "create_order",
                "data": {
                    "customer_id": 1,
                    "user_id": 1,
                    "product_id": 3,
                    "product_name": "Red Apple",
                    "quantity": 2,
                    "delivery_address": "10 Downing St, London, SW1A 2AA",
                },
            },
        },
    )
    monkeypatch.setattr(
        chat_service,
        "execute_db_action",
        lambda _configs, _action: {"ok": True, "result": {"order_id": 19, "product": "Red Apple", "quantity": 2, "total": 5.0}},
    )

    payload, status = chat_service.handle_chat_payload({"site_id": "site123", "message": "Order red apples"})

    assert status == 200
    assert "Your order is confirmed." in payload["message"]
    assert payload["db_action"] is None


@pytest.mark.unit
def test_invalid_actions_handled_safely(chat_service, monkeypatch):
    """Unknown DB actions should surface a warning instead of crashing the request."""
    monkeypatch.setattr(chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(chat_service, "load_db_configs", lambda _site_id: [{"path": "owner.db"}])
    monkeypatch.setattr(chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(chat_service, "build_effective_db_configs", lambda _configs: [{"path": "owner.db"}])
    monkeypatch.setattr(
        chat_service,
        "generate_response",
        lambda **_kwargs: {
            "message": "Trying an unsupported action.",
            "options": [],
            "links": [],
            "db_action": {"type": "unsupported_action"},
        },
    )
    monkeypatch.setattr(chat_service, "execute_db_action", lambda _configs, _action: {"ok": False, "error": "Unknown action: unsupported_action"})

    payload, status = chat_service.handle_chat_payload({"site_id": "site123", "message": "Do something unsupported"})

    assert status == 200
    assert "Warning: Unknown action: unsupported_action" in payload["message"]
