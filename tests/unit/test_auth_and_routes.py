"""Unit tests for auth helpers, app setup, security, and public routes."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest
from flask import Flask, jsonify

from tests.helpers.db_utils import create_customer_db, create_owner_db, seed_customer, seed_order
from tests.helpers.runtime import bootstrap_app, import_fresh


@pytest.mark.unit
def test_create_app_registers_blueprints_and_admin_key(monkeypatch, tmp_path):
    app_pkg = import_fresh("chatbot_app")

    app = app_pkg.create_app()

    assert app.config["ADMIN_API_KEY"] == "test-admin-key"
    assert "auth" in app.blueprints
    assert "admin" in app.blueprints
    assert "public" in app.blueprints
    assert "chat" in app.blueprints


@pytest.mark.unit
def test_get_admin_api_key_requires_env(monkeypatch):
    config = import_fresh("chatbot_app.config")
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)

    with pytest.raises(EnvironmentError):
        config.get_admin_api_key()


@pytest.mark.unit
def test_require_admin_key_blocks_and_allows_requests():
    security = import_fresh("chatbot_app.security")
    app = Flask(__name__)
    app.config["ADMIN_API_KEY"] = "secret"

    @security.require_admin_key
    def protected():
        return jsonify({"ok": True})

    with app.test_request_context("/", headers={"X-Admin-Key": "wrong"}):
        payload, status = protected()
        assert status == 401
        assert payload.get_json()["error"] == "Unauthorized"

    with app.test_request_context("/", headers={"X-Admin-Key": "secret"}):
        response = protected()
        assert response.get_json()["ok"] is True


@pytest.mark.unit
def test_public_config_returns_default_shaped_payload(monkeypatch):
    public = import_fresh("chatbot_app.routes.public")
    app = Flask(__name__)
    monkeypatch.setattr(public, "load_config", lambda _site_id: {"bot_name": "Course Bot"})

    with app.test_request_context("/config/site123"):
        response = public.public_config("site123")

    payload = response.get_json()
    assert payload["bot_name"] == "Course Bot"
    assert payload["status_text"] == public.DEFAULT_CONFIG["status_text"]
    assert set(payload) == set(public.DEFAULT_CONFIG)


@pytest.mark.unit
def test_auth_helpers_cover_hash_verify_and_row_to_dict(tmp_path, monkeypatch):
    auth = import_fresh("chatbot_app.routes.auth")
    customer_db = tmp_path / "customer.db"
    owner_db = tmp_path / "owner.db"
    monkeypatch.setattr(auth, "CUSTOMER_DB_PATH", customer_db)
    monkeypatch.setattr(auth, "OWNER_DB_PATH", owner_db)
    create_customer_db(customer_db)
    create_owner_db(owner_db)
    auth.ensure_tables()

    hashed = auth.hash_password("strongpass123")
    assert auth.verify_password("strongpass123", hashed) is True
    assert auth.verify_password("wrongpass", hashed) is False
    assert auth.verify_password("anything", "bad-format") is False

    with auth.customer_connection() as connection:
        connection.execute(
            "INSERT INTO customers (name, email, password_hash) VALUES (?, ?, ?)",
            ("Alice", "alice@example.com", hashed),
        )
        row = connection.execute("SELECT * FROM customers WHERE email=?", ("alice@example.com",)).fetchone()

    data = auth.row_to_dict(row)
    assert data["email"] == "alice@example.com"
    assert "password_hash" not in data
    assert auth.row_to_dict(None) is None


@pytest.mark.unit
def test_auth_token_lifecycle_and_expiry_cleanup(tmp_path, monkeypatch):
    auth = import_fresh("chatbot_app.routes.auth")
    customer_db = tmp_path / "customer.db"
    owner_db = tmp_path / "owner.db"
    monkeypatch.setattr(auth, "CUSTOMER_DB_PATH", customer_db)
    monkeypatch.setattr(auth, "OWNER_DB_PATH", owner_db)
    create_customer_db(customer_db)
    create_owner_db(owner_db)
    auth.ensure_tables()

    customer_id = seed_customer(customer_db)
    token = auth.create_token(customer_id)
    customer = auth.get_customer_from_token(token)
    assert customer["email"] == "alice@example.com"

    expired_token = "expired-token"
    expired_at = (datetime.utcnow() - timedelta(days=1)).isoformat()
    with auth.owner_connection() as connection:
        connection.execute(
            "INSERT INTO sessions (token, customer_id, expires_at) VALUES (?, ?, ?)",
            (expired_token, customer_id, expired_at),
        )

    assert auth.get_customer_from_token(expired_token) is None
    with auth.owner_connection() as connection:
        deleted = connection.execute("SELECT * FROM sessions WHERE token=?", (expired_token,)).fetchone()
    assert deleted is None


@pytest.mark.unit
def test_require_token_decorator_handles_missing_invalid_and_valid_tokens(tmp_path, monkeypatch):
    auth = import_fresh("chatbot_app.routes.auth")
    customer_db = tmp_path / "customer.db"
    owner_db = tmp_path / "owner.db"
    monkeypatch.setattr(auth, "CUSTOMER_DB_PATH", customer_db)
    monkeypatch.setattr(auth, "OWNER_DB_PATH", owner_db)
    create_customer_db(customer_db)
    create_owner_db(owner_db)
    auth.ensure_tables()
    customer_id = seed_customer(customer_db)
    token = auth.create_token(customer_id)
    app = Flask(__name__)

    @auth.require_token
    def protected():
        return jsonify({"email": auth.request.customer["email"]})

    with app.test_request_context("/secure"):
        payload, status = protected()
        assert status == 401
        assert payload.get_json()["error"] == "Unauthorized"

    with app.test_request_context("/secure", headers={"Authorization": "Bearer missing"}):
        payload, status = protected()
        assert status == 401
        assert payload.get_json()["error"] == "Invalid or expired token"

    with app.test_request_context("/secure", headers={"Authorization": f"Bearer {token}"}):
        response = protected()
        assert response.get_json()["email"] == "alice@example.com"


@pytest.mark.unit
def test_auth_orders_route_returns_matching_orders(tmp_path, monkeypatch):
    auth = import_fresh("chatbot_app.routes.auth")
    customer_db = tmp_path / "customer.db"
    owner_db = tmp_path / "owner.db"
    monkeypatch.setattr(auth, "CUSTOMER_DB_PATH", customer_db)
    monkeypatch.setattr(auth, "OWNER_DB_PATH", owner_db)
    create_customer_db(customer_db)
    create_owner_db(owner_db)
    auth.ensure_tables()

    customer_id = seed_customer(customer_db)
    seed_order(owner_db, customer_id=customer_id)
    token = auth.create_token(customer_id)
    app = Flask(__name__)

    with app.test_request_context("/auth/orders", headers={"Authorization": f"Bearer {token}"}):
        auth.request.customer = auth.get_customer_from_token(token)
        response = auth.orders.__wrapped__()

    payload = response.get_json()
    assert payload["orders"][0]["product_name"] == "Red Apple"


@pytest.mark.unit
def test_route_exports_include_all_blueprints():
    routes_pkg = import_fresh("chatbot_app.routes")

    assert routes_pkg.__all__ == ["admin_bp", "auth_bp", "chat_bp", "public_bp"]


@pytest.mark.unit
def test_chat_route_delegates_to_service(monkeypatch):
    chat_route = import_fresh("chatbot_app.routes.chat")
    app = Flask(__name__)
    monkeypatch.setattr(chat_route, "handle_chat_payload", lambda payload: ({"echo": payload["message"]}, 202))

    with app.test_request_context("/chat", json={"message": "Hello"}):
        response, status = chat_route.chat()

    assert status == 202
    assert response.get_json()["echo"] == "Hello"

