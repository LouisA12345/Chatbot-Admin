"""Unit tests for database read/write helpers."""

from __future__ import annotations

import sqlite3

import pytest

from tests.helpers.db_utils import create_sample_service_dbs, seed_customer, seed_order, seed_product
from tests.helpers.runtime import import_fresh


@pytest.fixture
def db_service():
    """Import the database service with fresh dependency stubs."""
    return import_fresh("chatbot_app.db.service")


@pytest.fixture
def sample_db_configs(tmp_path):
    """Create realistic temporary SQLite databases for unit testing."""
    customer_db, owner_db, product_db = create_sample_service_dbs(tmp_path)
    customer_id = seed_customer(customer_db)
    product_id = seed_product(product_db)
    seed_order(owner_db, customer_id=customer_id)
    return {
        "customer": {"type": "sqlite", "path": str(customer_db), "label": "Customers"},
        "owner": {"type": "sqlite", "path": str(owner_db), "label": "Orders"},
        "product": {"type": "sqlite", "path": str(product_db), "label": "Products"},
        "customer_id": customer_id,
        "product_id": product_id,
        "product_db_path": product_db,
        "owner_db_path": owner_db,
    }


@pytest.mark.unit
def test_db_connection_works(db_service, sample_db_configs):
    """DB connection validation should succeed against a healthy SQLite database."""
    result = db_service.test_connection(sample_db_configs["product"])

    assert result["ok"] is True
    assert result["row_count"] >= 1


@pytest.mark.unit
def test_fetch_user_exists_and_not_exists(db_service, sample_db_configs):
    """Customer lookup should return a sanitized row for known users and None otherwise."""
    found = db_service._lookup_customer(sample_db_configs["customer"], "alice@example.com")
    missing = db_service._lookup_customer(sample_db_configs["customer"], "missing@example.com")

    assert found["email"] == "alice@example.com"
    assert "password_hash" not in found
    assert missing is None


@pytest.mark.unit
def test_order_creation_works(db_service, sample_db_configs):
    """Structured order creation should write a row and decrement product stock."""
    action = {
        "type": "create_order",
        "data": {
            "customer_id": sample_db_configs["customer_id"],
            "user_id": sample_db_configs["customer_id"],
            "user_email": "alice@example.com",
            "user_name": "Alice Smith",
            "product_id": sample_db_configs["product_id"],
            "product_name": "Red Apple",
            "quantity": 3,
            "delivery_address": "10 Downing St, London, SW1A 2AA",
        },
    }

    result = db_service.execute_db_action(
        [sample_db_configs["product"], sample_db_configs["owner"]],
        action,
    )

    assert result["ok"] is True
    assert result["result"]["quantity"] == 3

    connection = sqlite3.connect(sample_db_configs["product_db_path"])
    stock = connection.execute("SELECT stock FROM products WHERE id = ?", (sample_db_configs["product_id"],)).fetchone()[0]
    connection.close()
    assert stock == 5


@pytest.mark.unit
def test_order_history_retrieval(db_service, sample_db_configs):
    """Order history retrieval should return recent orders for a matching customer."""
    result = db_service.execute_db_action(
        [sample_db_configs["owner"]],
        {"type": "get_orders", "customer_id": sample_db_configs["customer_id"]},
    )

    assert result["ok"] is True
    assert result["result"]["count"] == 1
    assert result["result"]["orders"][0]["product_name"] == "Red Apple"
