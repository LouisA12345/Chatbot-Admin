import sqlite3

conn = sqlite3.connect("test_store.db")
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT,
    category TEXT,
    price REAL,
    stock INTEGER,
    description TEXT,
    url TEXT
);

INSERT INTO products (name, category, price, stock, description, url) VALUES
('AcmeCam 360 Security', 'Cameras', 79.99, 25, 'Indoor 360 security camera', 'link'),
('ClearView Webcam 1080p', 'Cameras', 49.99, 40, '1080p webcam', 'link');

CREATE TABLE faqs (
    id INTEGER PRIMARY KEY,
    question TEXT,
    answer TEXT
);

INSERT INTO faqs (question, answer) VALUES
('Do you ship internationally?', 'Currently only within the UK'),
('How can I track my order?', 'Use the tracking link in your email');
""")

conn.commit()
conn.close()

print("Database created ✅")