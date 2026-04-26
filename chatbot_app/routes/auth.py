"""Authentication routes and token/session helpers."""

import hashlib
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

import secrets
from flask import Blueprint, jsonify, request
from flask_cors import cross_origin

from chatbot_app.config import CUSTOMER_DB_PATH, OWNER_DB_PATH

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def customer_connection():
    """Open a row-aware connection to the customer database."""
    connection = sqlite3.connect(CUSTOMER_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def owner_connection():
    """Open a row-aware connection to the owner database."""
    connection = sqlite3.connect(OWNER_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_tables():
    """Create auth/session/order tables if they do not exist yet."""
    with customer_connection() as connection:
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

    with owner_connection() as connection:
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


ensure_tables()


def hash_password(password: str) -> str:
    """Hash a password using the project's simple salt:digest format."""
    salt = secrets.token_hex(16)
    return f"{salt}:{hashlib.sha256((salt + password).encode()).hexdigest()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a previously stored salted digest."""
    try:
        salt, digest = stored.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == digest
    except Exception:
        return False


def create_token(customer_id: int) -> str:
    """Create and persist a long-lived session token for a customer."""
    token = secrets.token_hex(32)
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    with owner_connection() as connection:
        connection.execute(
            "INSERT INTO sessions (token, customer_id, expires_at) VALUES (?,?,?)",
            (token, customer_id, expires),
        )
    return token


def get_customer_from_token(token: str):
    """Resolve a session token to its customer row, removing expired tokens."""
    with owner_connection() as owner_db:
        row = owner_db.execute("SELECT customer_id, expires_at FROM sessions WHERE token=?", (token,)).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
            owner_db.execute("DELETE FROM sessions WHERE token=?", (token,))
            return None
        customer_id = row["customer_id"]

    with customer_connection() as customer_db:
        return customer_db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()


def row_to_dict(row):
    """Convert a DB row to JSON-safe output without sensitive fields."""
    if row is None:
        return None
    data = dict(row)
    data.pop("password_hash", None)
    return data


def require_token(func):
    """Protect routes that require a valid bearer token."""
    @wraps(func)
    def decorated(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        token = authorization[7:]
        customer = get_customer_from_token(token)
        if not customer:
            return jsonify({"error": "Invalid or expired token"}), 401
        request.customer = customer
        request.token = token
        return func(*args, **kwargs)

    return decorated


@auth_bp.route("/register", methods=["POST"])
@cross_origin()
def register():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    try:
        with customer_connection() as connection:
            connection.execute(
                "INSERT INTO customers (name, email, phone, address, password_hash) VALUES (?,?,?,?,?)",
                (name, email, phone or None, address or None, hash_password(password)),
            )
            customer_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        token = create_token(customer_id)
        with customer_connection() as connection:
            row = connection.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        return jsonify({"user": row_to_dict(row), "token": token}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists."}), 409


@auth_bp.route("/login", methods=["POST"])
@cross_origin()
def login():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    with customer_connection() as connection:
        row = connection.execute("SELECT * FROM customers WHERE email=?", (email,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return jsonify({"error": "Incorrect email or password."}), 401

    return jsonify({"user": row_to_dict(row), "token": create_token(row["id"])})


@auth_bp.route("/me", methods=["GET"])
@cross_origin()
@require_token
def me():
    return jsonify({"user": row_to_dict(request.customer)})


@auth_bp.route("/logout", methods=["POST"])
@cross_origin()
@require_token
def logout():
    with owner_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE token=?", (request.token,))
    return jsonify({"message": "Logged out."})


@auth_bp.route("/orders", methods=["GET"])
@cross_origin()
@require_token
def orders():
    customer_id = request.customer["id"]
    with owner_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM orders WHERE customer_id=? OR user_email=? ORDER BY created_at DESC LIMIT 20",
            (customer_id, request.customer["email"]),
        ).fetchall()
    return jsonify({"orders": [dict(row) for row in rows]})
