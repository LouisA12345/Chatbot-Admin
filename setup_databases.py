"""
setup_databases.py
Run once to create / reset both databases.

customer.db  — data visible / shareable to customers
owner.db     — sensitive business data (orders, sessions)
"""

import sqlite3
import os

for db in ['customer.db', 'owner.db']:
    if os.path.exists(db):
        os.remove(db)

# ── CUSTOMER DATABASE ─────────────────────────────────────────
cust = sqlite3.connect('customer.db')
c = cust.cursor()
c.executescript("""
CREATE TABLE customers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    phone         TEXT,
    address       TEXT,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE products (
    id          INTEGER PRIMARY KEY,
    name        TEXT,
    category    TEXT,
    price       REAL,
    stock       INTEGER,
    description TEXT,
    url         TEXT
);

CREATE TABLE faqs (
    id       INTEGER PRIMARY KEY,
    question TEXT,
    answer   TEXT,
    category TEXT
);

CREATE TABLE promotions (
    id               INTEGER PRIMARY KEY,
    code             TEXT,
    discount_percent INTEGER,
    description      TEXT,
    valid_until      TEXT
);

INSERT INTO products VALUES
(1,'AcmeCam 360','Cameras',79.99,25,'Indoor 360 security camera','http://localhost/products/1'),
(2,'ClearView Webcam 1080p','Cameras',49.99,40,'1080p USB webcam for video calls','http://localhost/products/2');

INSERT INTO faqs VALUES
(1,'Do you ship internationally?','Currently UK only.','Shipping'),
(2,'How can I track my order?','Use the tracking link in your confirmation email.','Shipping'),
(3,'What is your return policy?','30 days from delivery in original condition.','Returns'),
(4,'How long do refunds take?','5 business days after we receive the return.','Returns');

INSERT INTO promotions VALUES
(1,'WELCOME10',10,'10% off your first order','2026-12-31');
""")
cust.commit()
cust.close()

# ── OWNER DATABASE ────────────────────────────────────────────
own = sqlite3.connect('owner.db')
o = own.cursor()
o.executescript("""
CREATE TABLE sessions (
    token       TEXT PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    expires_at  TEXT    NOT NULL,
    created_at  TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id      INTEGER,
    user_id          INTEGER,
    user_email       TEXT,
    user_name        TEXT,
    product_id       INTEGER,
    product_name     TEXT,
    quantity         INTEGER DEFAULT 1,
    total_price      REAL,
    delivery_address TEXT,
    status           TEXT DEFAULT 'pending',
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE admin_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (datetime('now'))
);
""")
own.commit()
own.close()

print("Databases created successfully ✅")
print("  customer.db — customers, products, faqs, promotions")
print("  owner.db    — sessions, orders, admin_users")