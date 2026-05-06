import math
import os
import sqlite3
from datetime import datetime, date, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import (
    get_db,
    init_db,
    seed_db,
    create_user,
    create_expense,
    get_user_by_email,
)
from database.queries import (
    get_user_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_category_breakdown,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SPENDLY_SECRET_KEY", "dev-only-change-me")

PAGE_SIZE = 15
MAX_PAGE = 1000

CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)
DESCRIPTION_MAX_LENGTH = 200

with app.app_context():
    init_db()
    seed_db()


def _build_quick_ranges(anchor):
    """Return the four quick-range presets anchored at `anchor` (a date)."""
    # 30 days ≈ 1 month and 182 days ≈ 6 months — exact calendar months would
    # need dateutil.relativedelta which isn't in the project's dependencies.
    return [
        {"key": "1w",  "label": "1 week",   "start": (anchor - timedelta(days=7)).isoformat(),   "end": anchor.isoformat()},
        {"key": "1m",  "label": "1 month",  "start": (anchor - timedelta(days=30)).isoformat(),  "end": anchor.isoformat()},
        {"key": "6m",  "label": "6 months", "start": (anchor - timedelta(days=182)).isoformat(), "end": anchor.isoformat()},
        {"key": "all", "label": "All time", "start": "",                                         "end": ""},
    ]


def _parse_date_range(raw_start, raw_end):
    """Return (start, end, error). Empty inputs are valid (open-ended).
    On any error, returns (None, None, message) so callers fall back to
    unfiltered data."""
    def parse(value):
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    try:
        start = parse(raw_start)
        end = parse(raw_end)
    except ValueError:
        return None, None, "Please enter valid dates in YYYY-MM-DD format."
    if start and end and end < start:
        return None, None, "End date must be on or after start date."
    return start, end, None


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template(
            "register.html",
            error="Please fill in every field.",
            name=name,
            email=email,
        )

    if len(password) < 8:
        return render_template(
            "register.html",
            error="Password must be at least 8 characters.",
            name=name,
            email=email,
        )

    if get_user_by_email(email) is not None:
        return render_template(
            "register.html",
            error="An account with that email already exists.",
            name=name,
            email=email,
        )

    try:
        create_user(name, email, generate_password_hash(password))
    except sqlite3.IntegrityError:
        return render_template(
            "register.html",
            error="An account with that email already exists.",
            name=name,
            email=email,
        )

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template(
            "login.html",
            error="Please enter your email and password.",
            email=email,
        )

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html",
            error="Invalid email or password.",
            email=email,
        )

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    raw_start = request.args.get("start", "").strip()
    raw_end = request.args.get("end", "").strip()
    start, end, filter_error = _parse_date_range(raw_start, raw_end)

    try:
        page = max(1, min(MAX_PAGE, int(request.args.get("page", 1))))
    except ValueError:
        page = 1

    offset = (page - 1) * PAGE_SIZE

    # <SECTION: TRANSACTIONS>
    recent_transactions = get_recent_transactions(
        user_id, limit=PAGE_SIZE, offset=offset, start=start, end=end
    )
    # <SECTION: SUMMARY>
    summary = get_summary_stats(user_id, start=start, end=end)
    # <SECTION: CATEGORY>
    category_breakdown = get_category_breakdown(user_id, start=start, end=end)

    total_tx = summary["transaction_count"]
    has_prev = page > 1
    has_next = page * PAGE_SIZE < total_tx

    echoed_start = raw_start if not filter_error else ""
    echoed_end = raw_end if not filter_error else ""

    quick_ranges = _build_quick_ranges(date.today())
    active_quick_key = next(
        (r["key"] for r in quick_ranges
         if r["start"] == echoed_start and r["end"] == echoed_end),
        None,
    )

    return render_template(
        "profile.html",
        user=user,
        member_since=user["member_since"],
        recent_transactions=recent_transactions,
        summary=summary,
        category_breakdown=category_breakdown,
        start=echoed_start,
        end=echoed_end,
        filter_error=filter_error,
        filter_active=bool(start or end),
        page=page,
        has_prev=has_prev,
        has_next=has_next,
        quick_ranges=quick_ranges,
        active_quick_key=active_quick_key,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    today = date.today().isoformat()

    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
        )

    raw_amount = request.form.get("amount", "").strip()
    raw_category = request.form.get("category", "").strip()
    raw_date = request.form.get("date", "").strip()
    raw_description = request.form.get("description", "").strip()

    def rerender(message):
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
            error=message,
            amount=raw_amount,
            category=raw_category,
            date=raw_date,
            description=raw_description,
        )

    try:
        amount = float(raw_amount)
    except ValueError:
        return rerender("Amount must be a number.")
    if not math.isfinite(amount) or amount <= 0:
        return rerender("Amount must be greater than zero.")

    if raw_category not in CATEGORIES:
        return rerender("Please choose a category from the list.")

    try:
        parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return rerender("Please enter a valid date in YYYY-MM-DD format.")
    if parsed_date > date.today():
        return rerender("Date cannot be in the future.")

    if len(raw_description) > DESCRIPTION_MAX_LENGTH:
        return rerender(
            f"Description must be {DESCRIPTION_MAX_LENGTH} characters or fewer."
        )
    description = raw_description or None

    create_expense(user_id, amount, raw_category, parsed_date.isoformat(), description)
    flash("Expense added successfully.", "success")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, port=5001)
