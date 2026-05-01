# Plan: 01 — Database Setup

## Context

`database/db.py` is currently a comment-only stub. No database exists. All future steps (auth, profile, expenses) depend on the data layer being in place. This step replaces the stub with a working SQLite implementation and wires it into app startup.

---

## Files to Change

| File | Change |
|------|--------|
| `database/db.py` | Implement `get_db`, `init_db`, `seed_db` |
| `app.py` | Import the three functions; call `init_db()` + `seed_db()` at startup |

---

## 1. `database/db.py`

### `get_db()`
- Opens `expense_tracker.db` at project root (derived via `os.path` relative to `__file__`)
- Sets `row_factory = sqlite3.Row`
- Runs `PRAGMA foreign_keys = ON`
- Returns connection

### `init_db()`
- Creates `users` and `expenses` tables with `CREATE TABLE IF NOT EXISTS`
- Safe to call on every startup

### `seed_db()`
- Guards with `SELECT COUNT(*) FROM users` — exits early if data already exists
- Inserts Demo User (`demo@spendly.com` / `demo123` hashed via werkzeug)
- Inserts 8 sample expenses in ₹ spread across April 2026, covering all 7 categories

---

## 2. `app.py`

```python
from database.db import get_db, init_db, seed_db

with app.app_context():
    init_db()
    seed_db()
```

No routes change.

---

## Verification

1. `source venv/Scripts/activate && python app.py` — starts on port 5001 without errors
2. `expense_tracker.db` appears in project root
3. `SELECT * FROM users;` → 1 row; `SELECT * FROM expenses;` → 8 rows
4. Re-running app does not duplicate seed data
5. `pytest` passes
