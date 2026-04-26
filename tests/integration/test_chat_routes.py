"""Integration tests for the /chat endpoint using the Flask test client."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_chat_endpoint_valid_message_returns_json(client, isolated_app, monkeypatch):
    """A valid chat request should return HTTP 200 with structured JSON."""
    monkeypatch.setattr(isolated_app.chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(isolated_app.chat_service, "load_db_configs", lambda _site_id: [])
    monkeypatch.setattr(isolated_app.chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(
        isolated_app.chat_service,
        "generate_response",
        lambda **_kwargs: {"message": "Hello there.", "options": [], "links": [], "db_action": None},
    )

    response = client.post("/chat", json={"site_id": "site123", "message": "Hello"})

    assert response.status_code == 200
    assert response.get_json()["message"] == "Hello there."


@pytest.mark.integration
def test_chat_endpoint_empty_message_returns_safe_reply(client):
    """Empty user input should not crash the route and should return a prompt."""
    response = client.post("/chat", json={"site_id": "site123", "message": ""})

    assert response.status_code == 200
    assert response.get_json()["reply"] == "Please enter a message."


@pytest.mark.integration
def test_chat_with_db_enrichment(client, isolated_app, monkeypatch):
    """The chat route should enrich logged-in user details before generating a reply."""
    captured = {}
    monkeypatch.setattr(isolated_app.chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(isolated_app.chat_service, "load_db_configs", lambda _site_id: [{"path": "customer.db"}])
    monkeypatch.setattr(isolated_app.chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(isolated_app.chat_service, "_find_db_with_table", lambda _configs, _table: {"path": "customer.db"})
    monkeypatch.setattr(
        isolated_app.chat_service,
        "_lookup_customer",
        lambda _config, _email: {"id": 7, "address": "22 Baker St, London, NW1 6XE"},
    )

    def fake_generate_response(**kwargs):
        captured["user_info"] = kwargs["user_info"]
        return {"message": "Address enriched.", "options": [], "links": [], "db_action": None}

    monkeypatch.setattr(isolated_app.chat_service, "generate_response", fake_generate_response)

    response = client.post(
        "/chat",
        json={"site_id": "site123", "message": "Where is my address?", "user_info": {"name": "Alice", "email": "alice@example.com"}},
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Address enriched."
    assert captured["user_info"]["address"] == "22 Baker St, London, NW1 6XE"


@pytest.mark.integration
def test_chat_order_flow(client, isolated_app, monkeypatch):
    """Create-order actions should execute and return an order confirmation payload."""
    monkeypatch.setattr(isolated_app.chat_service, "get_kb", lambda _site_id: None)
    monkeypatch.setattr(isolated_app.chat_service, "load_db_configs", lambda _site_id: [{"path": "owner.db"}])
    monkeypatch.setattr(isolated_app.chat_service, "load_config", lambda _site_id: {})
    monkeypatch.setattr(isolated_app.chat_service, "build_effective_db_configs", lambda _configs: [{"path": "owner.db"}])
    monkeypatch.setattr(
        isolated_app.chat_service,
        "generate_response",
        lambda **_kwargs: {
            "message": "Order received.",
            "options": [],
            "links": [],
            "db_action": {
                "type": "create_order",
                "data": {
                    "customer_id": 1,
                    "product_id": 1,
                    "quantity": 1,
                    "delivery_address": "10 Downing St, London, SW1A 2AA",
                },
            },
        },
    )
    monkeypatch.setattr(
        isolated_app.chat_service,
        "execute_db_action",
        lambda _configs, _action: {"ok": True, "result": {"order_id": 3, "product": "Red Apple", "quantity": 1, "total": 2.5}},
    )

    response = client.post("/chat", json={"site_id": "site123", "message": "Order a red apple"})

    assert response.status_code == 200
    assert "Your order is confirmed." in response.get_json()["message"]


@pytest.mark.integration
def test_chat_invalid_input_does_not_crash(client):
    """Invalid chat payloads should return a controlled error response."""
    response = client.post("/chat", json={})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request."
