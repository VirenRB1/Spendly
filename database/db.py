import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "expense_tracker.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        conn.close()
        return

    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123"))
    )
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    expenses = [
        (user_id, 450.00,  "Food",          "2026-04-01", "Lunch at canteen"),
        (user_id, 120.00,  "Transport",     "2026-04-03", "Auto rickshaw"),
        (user_id, 1800.00, "Bills",         "2026-04-05", "Electricity bill"),
        (user_id, 300.00,  "Health",        "2026-04-08", "Pharmacy"),
        (user_id, 599.00,  "Entertainment", "2026-04-12", "OTT subscription"),
        (user_id, 2200.00, "Shopping",      "2026-04-15", "Clothes"),
        (user_id, 85.00,   "Other",         "2026-04-18", "Stationery"),
        (user_id, 650.00,  "Food",          "2026-04-22", "Dinner with friends"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, password_hash FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return row


def create_user(name, email, password_hash):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id
