"""Database read/write helpers used by chat, admin, and auth flows."""

import hashlib
import secrets

# Tables that should not be exposed as searchable knowledge chunks.
_SKIP_TABLES = {"orders", "sessions", "admin_users", "sqlite_sequence"}


def get_db_chunks(db_config: dict) -> list:
    """Read database rows and flatten them into searchable text chunks."""
    db_type = db_config.get("type", "sqlite")
    if db_type == "sqlite":
        return _read_sqlite(db_config)
    if db_type == "postgresql":
        return _read_postgresql(db_config)
    raise ValueError(f"Unsupported database type: {db_type}")


def get_all_db_chunks(db_configs: list) -> list:
    """Aggregate chunks from every configured data source."""
    chunks = []
    for config in db_configs:
        try:
            chunks.extend(get_db_chunks(config))
        except Exception as exc:
            print(f"Warning: could not read DB '{config.get('label', '?')}': {exc}")
    return chunks


def _read_sqlite(config: dict) -> list:
    """Read all non-sensitive SQLite tables into text chunks."""
    import sqlite3

    path = config.get("path", "")
    if not path:
        raise ValueError("SQLite path is required.")

    label = config.get("label", "DB")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    chunks = []
    for table in tables:
        if table in _SKIP_TABLES:
            continue
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        for row in rows:
            parts = [f"{column}: {row[column]}" for column in columns if row[column] is not None]
            chunks.append(f"[{label} / {table}] " + " | ".join(parts))

    connection.close()
    return chunks


def _read_postgresql(config: dict) -> list:
    """Read all non-sensitive PostgreSQL tables into text chunks."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:
        raise ImportError("Run: pip install psycopg2-binary") from exc

    connection = psycopg2.connect(
        host=config.get("host", "localhost"),
        port=config.get("port", 5432),
        dbname=config.get("dbname", ""),
        user=config.get("user", ""),
        password=config.get("password", ""),
    )
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name
        """
    )
    tables = [row[0] for row in cursor.fetchall()]
    label = config.get("label", "DB")
    chunks = []

    for table in tables:
        if table in _SKIP_TABLES:
            continue
        cursor.execute(f"SELECT * FROM {table} LIMIT 500")
        rows = cursor.fetchall()
        if not rows:
            continue
        columns = [description[0] for description in cursor.description]
        for row in rows:
            parts = [f"{column}: {row[column]}" for column in columns if row[column] is not None]
            chunks.append(f"[{label} / {table}] " + " | ".join(parts))

    connection.close()
    return chunks


def test_connection(db_config: dict) -> dict:
    """Validate a DB config by attempting to read chunks from it."""
    try:
        chunks = get_db_chunks(db_config)
        return {"ok": True, "row_count": len(chunks)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def execute_db_action(db_configs: list, action: dict) -> dict:
    """Route a structured DB action to the correct helper implementation."""
    action_type = action.get("type")

    try:
        if action_type == "lookup_user":
            config = _find_db_with_table(db_configs, "customers")
            if not config:
                return {"ok": False, "error": "No customer database connected."}
            user = _lookup_customer(config, action.get("email", ""))
            return {"ok": True, "result": {"found": bool(user), "user": user}} if user else {"ok": True, "result": {"found": False}}

        if action_type == "create_order":
            product_config = _find_db_with_table(db_configs, "products")
            orders_config = _find_db_with_table(db_configs, "orders")
            if not product_config:
                return {"ok": False, "error": "No product database connected."}
            if not orders_config:
                return {"ok": False, "error": "No orders database connected."}
            return _create_order(product_config, orders_config, action)

        if action_type == "get_orders":
            orders_config = _find_db_with_table(db_configs, "orders")
            if not orders_config:
                return {"ok": False, "error": "No orders database connected."}
            return _get_user_orders(orders_config, action)

        if action_type == "register_user":
            config = _find_db_with_table(db_configs, "customers")
            if not config:
                return {"ok": False, "error": "No customer database connected."}
            return _register_customer(config, action)

        return {"ok": False, "error": f"Unknown action: {action_type}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _find_db_with_table(db_configs: list, table_name: str):
    """Return the first configured database that contains the requested table."""
    for config in db_configs:
        try:
            if config.get("type", "sqlite") == "sqlite":
                import sqlite3

                connection = sqlite3.connect(config["path"])
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                found = cursor.fetchone() is not None
                connection.close()
                if found:
                    return config
            elif config.get("type") == "postgresql":
                import psycopg2

                connection = psycopg2.connect(
                    host=config.get("host", "localhost"),
                    port=config.get("port", 5432),
                    dbname=config.get("dbname", ""),
                    user=config.get("user", ""),
                    password=config.get("password", ""),
                )
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_name=%s AND table_schema='public'",
                    (table_name,),
                )
                found = cursor.fetchone() is not None
                connection.close()
                if found:
                    return config
        except Exception:
            continue
    return None


def _lookup_customer(config: dict, email: str):
    """Return a customer record without the stored password hash."""
    try:
        if config.get("type", "sqlite") == "sqlite":
            import sqlite3

            connection = sqlite3.connect(config["path"])
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM customers WHERE email=? COLLATE NOCASE", (email,))
            row = cursor.fetchone()
            connection.close()
            if row:
                data = dict(row)
                data.pop("password_hash", None)
                return data
        elif config.get("type") == "postgresql":
            import psycopg2
            import psycopg2.extras

            connection = psycopg2.connect(
                host=config.get("host", "localhost"),
                port=config.get("port", 5432),
                dbname=config.get("dbname", ""),
                user=config.get("user", ""),
                password=config.get("password", ""),
            )
            cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM customers WHERE LOWER(email)=LOWER(%s)", (email,))
            row = cursor.fetchone()
            connection.close()
            if row:
                data = dict(row)
                data.pop("password_hash", None)
                return data
    except Exception:
        return None
    return None


def _create_order(product_config: dict, orders_config: dict, action: dict) -> dict:
    """Create an order after validating product existence and stock levels."""
    import sqlite3

    data = action.get("data", {})
    quantity = max(1, int(data.get("quantity", 1)))

    if product_config.get("type", "sqlite") != "sqlite":
        return {"ok": False, "error": "PostgreSQL stock check not yet supported."}

    connection = sqlite3.connect(product_config["path"])
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("SELECT id, name, stock, price FROM products WHERE id=?", (data.get("product_id"),))
    product = cursor.fetchone()
    if not product:
        connection.close()
        return {"ok": False, "error": "Product not found."}
    if product["stock"] < quantity:
        connection.close()
        return {"ok": False, "error": f"Only {product['stock']} unit(s) in stock."}

    # Stock is decremented in the product database before the order record
    # is written to the owner database so both systems stay aligned.
    total = round(float(product["price"]) * quantity, 2)
    cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product["id"]))
    connection.commit()
    connection.close()

    if orders_config.get("type", "sqlite") != "sqlite":
        return {"ok": False, "error": "PostgreSQL order write not yet supported."}

    connection = sqlite3.connect(orders_config["path"])
    cursor = connection.cursor()

    customer_id = data.get("customer_id") or data.get("user_id")
    user_id = data.get("user_id")

    # Normalise user identifiers to integers when possible because the
    # model-driven action payload may provide them as strings.
    try:
        customer_id = int(customer_id) if customer_id else None
    except Exception:
        customer_id = None
    try:
        user_id = int(user_id) if user_id else None
    except Exception:
        user_id = None

    cursor.execute(
        """
        INSERT INTO orders
          (customer_id, user_id, user_email, user_name,
           product_id, product_name, quantity,
           total_price, delivery_address, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            customer_id,
            user_id,
            data.get("user_email", ""),
            data.get("user_name", ""),
            product["id"],
            data.get("product_name") or product["name"],
            quantity,
            total,
            data.get("delivery_address", ""),
            "confirmed",
        ),
    )
    order_id = cursor.lastrowid
    connection.commit()
    connection.close()

    return {
        "ok": True,
        "result": {
            "order_id": order_id,
            "product": product["name"],
            "quantity": quantity,
            "total": total,
            "status": "confirmed",
        },
    }


def _get_user_orders(orders_config: dict, action: dict) -> dict:
    """Fetch recent orders for a user matched by customer ID and/or email."""
    import sqlite3

    email = (action.get("user_email") or action.get("email") or "").strip().lower()
    customer_id = action.get("customer_id") or action.get("user_id")

    if not email and not customer_id:
        return {"ok": False, "error": "user_email or customer_id required."}
    if orders_config.get("type", "sqlite") != "sqlite":
        return {"ok": False, "error": "PostgreSQL get_orders not yet supported."}

    connection = sqlite3.connect(orders_config["path"])
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # Build the WHERE clause dynamically so either identifier can work on its own.
    conditions = []
    params = []
    if customer_id:
        try:
            customer_id = int(customer_id)
            conditions.extend(["customer_id = ?", "user_id = ?"])
            params.extend([customer_id, customer_id])
        except (ValueError, TypeError):
            pass
    if email:
        conditions.append("LOWER(user_email) = ?")
        params.append(email)

    if not conditions:
        connection.close()
        return {"ok": True, "result": {"orders": [], "count": 0}}

    where_clause = " OR ".join(conditions)
    cursor.execute(f"SELECT * FROM orders WHERE {where_clause} ORDER BY created_at DESC LIMIT 50", params)
    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()
    return {"ok": True, "result": {"orders": rows, "count": len(rows)}}


def _register_customer(config: dict, action: dict) -> dict:
    """Create a customer row using the same salted hash format as auth."""
    import sqlite3

    data = action.get("data", {})
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    if not email or not name:
        return {"ok": False, "error": "Name and email are required."}

    salt = secrets.token_hex(16)
    password = data.get("password") or secrets.token_hex(8)
    password_hash = salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()

    if config.get("type", "sqlite") != "sqlite":
        return {"ok": False, "error": "PostgreSQL register not yet supported."}

    connection = sqlite3.connect(config["path"])
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO customers (name, email, phone, address, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                email,
                data.get("phone") or None,
                data.get("address") or None,
                password_hash,
            ),
        )
        connection.commit()
        customer_id = cursor.lastrowid
        connection.close()
        return {"ok": True, "result": {"customer_id": customer_id, "email": email}}
    except sqlite3.IntegrityError:
        connection.close()
        return {"ok": False, "error": "An account with this email already exists."}


def get_orders(db_config: dict, limit: int = 50) -> list:
    """Fetch recent orders for admin-oriented views."""
    try:
        if db_config.get("type", "sqlite") == "sqlite":
            import sqlite3

            connection = sqlite3.connect(db_config["path"])
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = [dict(row) for row in cursor.fetchall()]
            connection.close()
            return rows
        if db_config.get("type") == "postgresql":
            import psycopg2
            import psycopg2.extras

            connection = psycopg2.connect(
                host=db_config.get("host", "localhost"),
                port=db_config.get("port", 5432),
                dbname=db_config.get("dbname", ""),
                user=db_config.get("user", ""),
                password=db_config.get("password", ""),
            )
            cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT %s", (limit,))
            rows = [dict(row) for row in cursor.fetchall()]
            connection.close()
            return rows
    except Exception:
        return []
    return []
