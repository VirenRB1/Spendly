"""Profile-page data helpers — one function per UI concern.

Each helper opens its own connection via database.db.get_db() and closes it
before returning. SQL is parameterised — never f-string into queries.
"""
from datetime import datetime

from database.db import get_db, get_user_by_id as _db_get_user_by_id


def get_user_by_id(user_id):
    """Return a dict with name, email, member_since — or None if user is gone.

    Wraps database.db.get_user_by_id and adds a human-formatted member_since
    string derived from the stored ISO created_at.
    """
    row = _db_get_user_by_id(user_id)
    if row is None:
        return None
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": datetime.fromisoformat(row["created_at"]).strftime("%B %Y"),
    }


# <SECTION: TRANSACTIONS>
def get_recent_transactions(user_id, limit=10):
    """Return the most recent expenses for a user as a list of dicts."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, date, description, category, amount "
            "FROM expenses WHERE user_id = ? "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# <SECTION: SUMMARY>
def get_summary_stats(user_id):
    """Return total spent, transaction count, and top category for a user."""
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top_row = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id,),
        ).fetchone()
        total = totals["total"] if totals is not None else 0
        cnt = totals["cnt"] if totals is not None else 0
        top_category = top_row["category"] if top_row is not None else "—"
        return {
            "total_spent": float(total),
            "transaction_count": int(cnt),
            "top_category": top_category,
        }
    finally:
        conn.close()


# <SECTION: CATEGORY>
def get_category_breakdown(user_id):
    """Return a list of category dicts with name, amount, and integer pct.

    Percentages are rounded per-row, then the largest row's pct is adjusted
    so the breakdown sums to exactly 100. Empty user → [].
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS amount "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category "
            "ORDER BY amount DESC, category ASC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    total = sum(row["amount"] for row in rows)
    breakdown = []
    for row in rows:
        amount = float(row["amount"])
        pct = round(amount * 100 / total) if total else 0
        breakdown.append({
            "name": row["category"],
            "amount": amount,
            "pct": pct,
        })

    remainder = 100 - sum(item["pct"] for item in breakdown)
    if breakdown and remainder:
        breakdown[0]["pct"] += remainder

    return breakdown
