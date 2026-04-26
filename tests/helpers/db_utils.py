"""SQLite helpers and realistic fixtures for chatbot tests."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


def _connect(path: Path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def create_customer_db(path: Path) -> Path:
    with _connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                phone TEXT,
                address TEXT,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
    return path


def create_owner_db(path: Path) -> Path:
    with _connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                user_id INTEGER,
                user_email TEXT,
                user_name TEXT,
                product_id INTEGER,
                product_name TEXT,
                quantity INTEGER DEFAULT 1,
                total_price REAL,
                delivery_address TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
    return path


def create_product_db(path: Path) -> Path:
    with _connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                description TEXT
            )
            """
        )
    return path


def create_sample_service_dbs(tmp_path):
    customer_db = create_customer_db(tmp_path / "customers.db")
    owner_db = create_owner_db(tmp_path / "owner.db")
    product_db = create_product_db(tmp_path / "products.db")
    return customer_db, owner_db, product_db


def seed_customer(path: Path, *, name="Alice Smith", email="alice@example.com", address="10 Downing St, London, SW1A 2AA"):
    salt = "testsalt"
    password_hash = f"{salt}:{hashlib.sha256((salt + 'strongpass123').encode()).hexdigest()}"
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO customers (name, email, phone, address, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, email, "07123456789", address, password_hash),
        )
        return cursor.lastrowid


def seed_product(path: Path, *, name="Red Apple", price=2.5, stock=8):
    with _connect(path) as connection:
        cursor = connection.execute(
            "INSERT INTO products (name, price, stock, description) VALUES (?, ?, ?, ?)",
            (name, price, stock, f"{name} description"),
        )
        return cursor.lastrowid


def seed_order(
    path: Path,
    *,
    customer_id=1,
    user_email="alice@example.com",
    product_name="Red Apple",
    quantity=2,
    total_price=5.0,
):
    with _connect(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO orders (
                customer_id, user_id, user_email, user_name, product_id,
                product_name, quantity, total_price, delivery_address, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                customer_id,
                user_email,
                "Alice Smith",
                1,
                product_name,
                quantity,
                total_price,
                "10 Downing St, London, SW1A 2AA",
                "confirmed",
            ),
        )
        return cursor.lastrowid
