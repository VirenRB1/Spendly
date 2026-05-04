"""Shared pytest fixtures for the Spendly test suite.

Every test gets an isolated in-memory SQLite database so tests never
touch the project's expense_tracker.db file and never interfere with
each other.

The DATABASE config key is read by get_db() only when tests patch the
connection call; since db.py hard-codes DB_PATH we monkey-patch it at
the module level inside the `app` fixture so each test truly starts
from a blank slate.
"""

import sqlite3
import tempfile
import os

import pytest
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """Create a Flask test app wired to a temporary SQLite file.

    Using a real file (not :memory:) keeps the connection-per-call
    pattern in db.py working correctly — each helper opens and closes
    its own connection, so :memory: would return an empty DB on the
    second call.
    """
    db_file = str(tmp_path / "test_spendly.db")

    # Patch the DB_PATH used by every helper in database.db BEFORE
    # importing the Flask app so init_db() / seed_db() use the temp file.
    import database.db as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_file

    # Now import the app; it calls init_db() + seed_db() at module level
    # inside `with app.app_context()` — we need to trigger that again
    # against the patched path.
    from app import app as flask_app
    from database.db import init_db, seed_db

    flask_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with flask_app.app_context():
        init_db()
        seed_db()

    yield flask_app

    # Restore original path so other test modules / sessions are not affected.
    db_module.DB_PATH = original_path


@pytest.fixture
def client(app):
    """Plain (unauthenticated) test client."""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Test client already logged in as the seed demo user."""
    client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )
    return client


# ---------------------------------------------------------------------------
# DB-level fixture for unit-testing query helpers directly
# ---------------------------------------------------------------------------

@pytest.fixture
def db_conn(tmp_path):
    """Return a raw sqlite3 connection to a freshly initialised temp DB
    and patch database.db.DB_PATH so query helpers use the same file.

    Yields (conn, user_id) so tests can insert their own rows and call
    helpers without going through HTTP.
    """
    db_file = str(tmp_path / "unit_test.db")

    import database.db as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_file

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Unit User", "unit@test.com", generate_password_hash("password")),
    )
    conn.commit()
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    yield conn, user_id

    conn.close()
    db_module.DB_PATH = original_path
