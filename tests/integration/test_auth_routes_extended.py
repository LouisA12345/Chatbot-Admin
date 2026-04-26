"""Additional integration coverage for auth and chat-adjacent route branches."""

from __future__ import annotations

import sqlite3

import pytest


@pytest.mark.integration
def test_register_validation_errors_and_login_missing_fields(client, auth_databases):
    missing = client.post("/auth/register", json={"email": "alice@example.com"})
    short = client.post("/auth/register", json={"name": "Alice", "email": "alice@example.com", "password": "short"})
    login_missing = client.post("/auth/login", json={"email": "alice@example.com"})

    assert missing.status_code == 400
    assert "required" in missing.get_json()["error"]
    assert short.status_code == 400
    assert "at least 8 characters" in short.get_json()["error"]
    assert login_missing.status_code == 400


@pytest.mark.integration
def test_logout_and_orders_require_and_use_tokens(client, auth_databases, isolated_app):
    unauthorized_logout = client.post("/auth/logout")
    unauthorized_orders = client.get("/auth/orders")

    register = client.post(
        "/auth/register",
        json={"name": "Alice Smith", "email": "alice@example.com", "password": "strongpass123"},
    )
    token = register.get_json()["token"]
    customer_id = register.get_json()["user"]["id"]

    with sqlite3.connect(isolated_app.owner_db) as connection:
        connection.execute(
            """
            INSERT INTO orders (customer_id, user_email, user_name, product_name, quantity, total_price, delivery_address, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (customer_id, "alice@example.com", "Alice Smith", "Red Apple", 2, 5.0, "10 Downing St", "confirmed"),
        )

    orders = client.get("/auth/orders", headers={"Authorization": f"Bearer {token}"})
    logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    after_logout = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert unauthorized_logout.status_code == 401
    assert unauthorized_orders.status_code == 401
    assert orders.status_code == 200
    assert orders.get_json()["orders"][0]["product_name"] == "Red Apple"
    assert logout.status_code == 200
    assert after_logout.status_code == 401

