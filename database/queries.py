"""Profile-page data helpers — one function per UI concern.

Each helper opens its own connection via database.db.get_db() and closes it
before returning. User values are always bound as `?` parameters; any
dynamic WHERE fragment is assembled from static string constants only —
never from user input.
"""
from datetime import datetime

from database.db import get_db, get_user_by_id as _db_get_user_by_id


def _date_where(start, end):
    """Return a WHERE-clause fragment built from static string constants only.
    Do not pass user-controlled column names or operators into this helper —
    only the booleans `start` / `end` decide which fragments are appended."""
    where = ["user_id = ?"]
    if start:
        where.append("date >= ?")
    if end:
        where.append("date <= ?")
    return " AND ".join(where)


def _date_params(user_id, start, end):
    params = [user_id]
    if start:
        params.append(start)
    if end:
        params.append(end)
    return params


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
def get_recent_transactions(user_id, limit=10, offset=0, start=None, end=None):
    """Return expenses for a user as a list of dicts, newest first.

    Optional `start` / `end` (ISO YYYY-MM-DD strings) bound the date range.
    `offset` supports pagination — combined with `limit` the caller can page
    through results 15 at a time.
    """
    where = _date_where(start, end)
    params = _date_params(user_id, start, end) + [limit, offset]
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, date, description, category, amount "
            "FROM expenses WHERE " + where + " "
            "ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def count_transactions(user_id, start=None, end=None):
    """Return the total number of expenses matching the optional date range."""
    where = _date_where(start, end)
    params = _date_params(user_id, start, end)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM expenses WHERE " + where,
            params,
        ).fetchone()
        return int(row["cnt"]) if row is not None else 0
    finally:
        conn.close()


# <SECTION: SUMMARY>
def get_summary_stats(user_id, start=None, end=None):
    """Return total spent, transaction count, and top category for a user."""
    where = _date_where(start, end)
    params = _date_params(user_id, start, end)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE " + where,
            params,
        ).fetchone()
        top_row = conn.execute(
            "SELECT category FROM expenses WHERE " + where + " "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            params,
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
def get_category_breakdown(user_id, start=None, end=None):
    """Return a list of category dicts with name, amount, and integer pct.

    Percentages are rounded per-row, then the largest row's pct is adjusted
    so the breakdown sums to exactly 100. Empty user → [].
    """
    where = _date_where(start, end)
    params = _date_params(user_id, start, end)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS amount "
            "FROM expenses WHERE " + where + " "
            "GROUP BY category "
            "ORDER BY amount DESC, category ASC",
            params,
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
