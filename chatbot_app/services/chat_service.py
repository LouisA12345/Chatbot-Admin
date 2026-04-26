"""Chat orchestration helpers that connect retrieval, AI, and DB actions."""

import sqlite3

from chatbot_app.ai.engine import generate_response
from chatbot_app.config import OWNER_DB_PATH
from chatbot_app.db.service import _find_db_with_table, _lookup_customer, execute_db_action
from chatbot_app.services.site_store import get_kb, load_config, load_db_configs


def looks_like_full_address(text: str) -> bool:
    """Heuristic check to avoid obviously incomplete delivery addresses."""
    import re

    text = text.strip()
    if len(text) < 8:
        return False
    postcode = re.search(r"[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}", text, re.I)
    if postcode:
        before = text[: postcode.start()].strip().strip(",")
        return len(before) >= 4
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) >= 2:
        return True
    return len(text.split()) >= 3


def gather_live_chunks(user_message: str, db_configs: list) -> list:
    """Optionally pull fresh product/order-related rows for live answers."""
    live_chunks = []
    message_lower = user_message.lower()
    live_keywords = ["stock", "available", "price", "cost", "buy", "order", "product", "much", "have", "sell"]
    if not any(keyword in message_lower for keyword in live_keywords):
        return live_chunks

    for config in db_configs:
        try:
            if config.get("type", "sqlite") != "sqlite":
                continue
            connection = sqlite3.connect(config["path"])
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for (table_name,) in cursor.fetchall():
                try:
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 100")
                    rows = cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    for row in rows:
                        parts = [f"{column}: {row[column]}" for column in columns if row[column] is not None]
                        live_chunks.append(f"[LIVE/{config.get('label', 'DB')}/{table_name}] " + " | ".join(parts))
                except Exception:
                    continue
            connection.close()
        except Exception as exc:
            print(f"Live DB error: {exc}")
    return live_chunks


def enrich_user_info(user_info: dict, db_configs: list) -> dict:
    """Fill in missing user fields from the customer database when possible."""
    enriched = dict(user_info or {})
    enriched["is_logged_in"] = bool(enriched.get("name") or enriched.get("email"))
    if enriched.get("is_logged_in") and not (enriched.get("address") or "").strip():
        try:
            customer_config = _find_db_with_table(db_configs, "customers")
            if customer_config and enriched.get("email"):
                fresh = _lookup_customer(customer_config, enriched["email"])
                if fresh and fresh.get("address"):
                    enriched["address"] = fresh["address"]
                if fresh and fresh.get("id") and not enriched.get("user_id"):
                    enriched["user_id"] = fresh["id"]
        except Exception as exc:
            print(f"Address enrichment warning: {exc}")
    return enriched


def format_order_confirmation(result: dict, address: str) -> dict:
    """Return a consistent, readable confirmation message after order creation."""
    message = (
        f"Your order is confirmed.\n\n"
        f"Product: **{result.get('product')}**\n"
        f"Quantity: **{result.get('quantity')}**\n"
        f"Total: **GBP {float(result.get('total', 0)):.2f}**\n"
        f"Order ID: **#{result.get('order_id')}**\n"
        f"Delivery address: **{address}**\n"
        f"Status: **Confirmed**"
    )
    return {"message": message, "options": ["View Order History", "Continue Shopping"], "links": [], "db_action": None}


def format_order_history(orders: list) -> dict:
    """Render order history in a widget-friendly, readable format."""
    if not orders:
        return {
            "message": "You haven't placed any orders yet. Would you like to browse our products?",
            "options": ["Browse Products"],
            "links": [],
            "db_action": None,
        }

    lines = []
    for order in orders:
        date = str(order.get("created_at", ""))[:10]
        status = str(order.get("status", "")).capitalize()
        lines.append(
            f"- **Order #{order.get('id')}**: {order.get('product_name')} x {order.get('quantity')} "
            f"for **GBP {float(order.get('total_price', 0)):.2f}**. {status} on {date}."
        )
    return {
        "message": f"Here are your {len(orders)} order{'s' if len(orders) != 1 else ''}:\n\n" + "\n".join(lines),
        "options": ["Place New Order", "Continue Shopping"],
        "links": [],
        "db_action": None,
    }


def build_effective_db_configs(db_configs: list) -> list:
    """Ensure owner.db is available for order/session operations when present."""
    effective = list(db_configs)
    if OWNER_DB_PATH.exists() and not any(config.get("path", "").endswith("owner.db") for config in effective):
        effective.append({"type": "sqlite", "path": str(OWNER_DB_PATH), "label": "Owner DB", "id": "_owner"})
    return effective


def handle_chat_payload(data):
    """Process a chat request and return a `(payload, status_code)` tuple."""
    if not data:
        return {"error": "Invalid request."}, 400

    site_id = data.get("site_id")
    user_message = data.get("message", "").strip()
    user_info = data.get("user_info", {})
    history = data.get("history", [])
    if not user_message:
        return {"reply": "Please enter a message."}, 200

    kb = get_kb(site_id)
    context_chunks = kb.search(user_message) if kb else []
    db_configs = load_db_configs(site_id)

    # Blend semantic KB results with live database rows for product/order queries.
    live_chunks = gather_live_chunks(user_message, db_configs) if db_configs else []
    all_chunks = list({chunk: None for chunk in (context_chunks + live_chunks)}.keys())[:12]

    user_info = enrich_user_info(user_info, db_configs)
    site_config = load_config(site_id) if site_id else {}

    try:
        result = generate_response(
            user_query=user_message,
            retrieved_chunks=all_chunks,
            user_info=user_info,
            conversation_history=history,
            custom_rules=site_config.get("custom_rules", "").strip(),
            personality=site_config.get("personality", "friendly"),
        )
    except Exception as exc:
        print(f"LLM error: {exc}")
        return {"message": "AI service temporarily unavailable.", "options": [], "links": []}, 200

    db_action = result.get("db_action")
    effective_configs = build_effective_db_configs(db_configs)

    if not db_action or not effective_configs:
        return result, 200

    action_result = execute_db_action(effective_configs, db_action)
    action_type = db_action.get("type", "")

    if not action_result["ok"]:
        result["message"] = f"{result.get('message', '')} Warning: {action_result['error']}".strip()
        return result, 200

    payload = action_result["result"]

    # Some actions are formatted server-side to keep user-facing details precise
    # and avoid hallucinated order IDs, prices, or statuses.
    if action_type == "create_order":
        address = (db_action.get("data") or {}).get("delivery_address", "")
        if not looks_like_full_address(address):
            return {
                "message": "Before I confirm your order, I need a complete delivery address. Please include the street, city and postcode. For example: *12 Park Lane, London, SW1A 1AA*",
                "options": [],
                "links": [],
                "db_action": None,
            }, 200
        return format_order_confirmation(payload, address), 200

    if action_type == "get_orders":
        return format_order_history(payload.get("orders", [])), 200

    if action_type == "lookup_user":
        user = payload.get("user", {})
        explicit_context = (
            f"USER LOOKUP: Found account. Name={user.get('name')}, email={user.get('email')}, address={user.get('address', 'not set')}."
            if payload.get("found")
            else "USER LOOKUP: No account found for that email."
        )
    elif action_type == "register_user":
        explicit_context = f"USER REGISTERED successfully. customer_id={payload.get('customer_id')}, email={payload.get('email')}."
    else:
        explicit_context = f"ACTION '{action_type}' result: {payload}"

    try:
        # For actions that need another assistant turn, feed the DB result back
        # as explicit system context so the follow-up answer stays grounded.
        follow_up = generate_response(
            user_query=user_message,
            retrieved_chunks=[explicit_context],
            user_info=user_info,
            conversation_history=list(history) + [{"role": "assistant", "content": f"[SYSTEM: {explicit_context}]"}],
        )
        follow_up["db_action"] = None
        return follow_up, 200
    except Exception as exc:
        print(f"Follow-up LLM error: {exc}")
        return result, 200
