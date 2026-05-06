"""Tests for Step 7 — Add Expense feature.

Spec: .claude/specs/07-add-expense.md

Covers:
- Auth guard: GET and POST while logged out redirect to /login
- GET form rendering: 200, all 7 canonical categories, today's date pre-filled, ₹ symbol
- POST happy path: redirect to /profile, description in transaction list, total_spent
  increases, transaction count increases, empty description stores NULL in DB
- POST validation failures: amount=0, negative, non-numeric; invalid category; future
  date; unparseable date — each returns 200 with an inline error and no DB insert;
  erroring field value is echoed back in the response
- Nav links: logged-in navbar contains Add expense link; logged-out does not
"""

import sqlite3
from datetime import date, timedelta

import pytest

# ---------------------------------------------------------------------------
# Seed data constants — mirror database/db.py seed_db() exactly so that
# expected totals can be computed without reading implementation files.
# ---------------------------------------------------------------------------

SEED_EXPENSES = [
    (450.00,  "Food",          "2026-04-01"),
    (120.00,  "Transport",     "2026-04-03"),
    (1800.00, "Bills",         "2026-04-05"),
    (300.00,  "Health",        "2026-04-08"),
    (599.00,  "Entertainment", "2026-04-12"),
    (2200.00, "Shopping",      "2026-04-15"),
    (85.00,   "Other",         "2026-04-18"),
    (650.00,  "Food",          "2026-04-22"),
]

SEED_TOTAL = sum(r[0] for r in SEED_EXPENSES)   # 6204.00
SEED_COUNT = len(SEED_EXPENSES)                  # 8

CANONICAL_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

# A valid past date that will never be "in the future" for this spec.
VALID_DATE = "2026-04-25"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_expense_count(db_module):
    """Return the current number of rows in the expenses table."""
    conn = db_module.get_db()
    try:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM expenses").fetchone()
        return int(row["cnt"])
    finally:
        conn.close()


def _get_all_expenses(db_module):
    """Return all rows in expenses as a list of dicts."""
    conn = db_module.get_db()
    try:
        rows = conn.execute(
            "SELECT id, user_id, amount, category, date, description FROM expenses"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ===========================================================================
# Auth guard
# ===========================================================================

class TestAuthGuard:
    """Both HTTP methods must redirect unauthenticated users to /login."""

    def test_get_add_expense_unauthenticated_redirects_to_login(self, client):
        """GET /expenses/add while logged out must return 302 → /login."""
        response = client.get("/expenses/add", follow_redirects=False)
        assert response.status_code == 302, (
            "Expected 302 redirect for unauthenticated GET /expenses/add"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target should be /login for unauthenticated GET"
        )

    def test_post_add_expense_unauthenticated_redirects_to_login(self, client):
        """POST /expenses/add while logged out must return 302 → /login."""
        response = client.post(
            "/expenses/add",
            data={
                "amount": "500",
                "category": "Food",
                "date": VALID_DATE,
                "description": "test",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Expected 302 redirect for unauthenticated POST /expenses/add"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target should be /login for unauthenticated POST"
        )


# ===========================================================================
# GET form rendering
# ===========================================================================

class TestGetForm:
    """Verify the add-expense form renders correctly for a logged-in user."""

    def test_get_returns_200(self, auth_client):
        """GET /expenses/add while logged in must return HTTP 200."""
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, "Expected 200 for authenticated GET /expenses/add"

    @pytest.mark.parametrize("category", CANONICAL_CATEGORIES)
    def test_get_form_contains_all_canonical_categories(self, auth_client, category):
        """The rendered form must include every one of the 7 canonical category options."""
        response = auth_client.get("/expenses/add")
        assert category.encode() in response.data, (
            f"Expected category '{category}' to appear in the add-expense form"
        )

    def test_get_form_date_prefilled_with_today(self, auth_client):
        """The date input must be pre-filled with today's date in YYYY-MM-DD format."""
        today = date.today().isoformat()
        response = auth_client.get("/expenses/add")
        assert today.encode() in response.data, (
            f"Expected today's date {today} to be pre-filled in the date input"
        )

    def test_get_form_contains_rupee_symbol(self, auth_client):
        """The form must display the ₹ symbol (raw UTF-8 or HTML entity &#8377;)."""
        response = auth_client.get("/expenses/add")
        rupee_present = (
            "₹".encode("utf-8") in response.data
            or b"&#8377;" in response.data
        )
        assert rupee_present, "Expected ₹ symbol (UTF-8 or &#8377;) in add-expense form"


# ===========================================================================
# POST — happy path
# ===========================================================================

class TestPostHappyPath:
    """Successful expense submissions must insert a DB row and redirect to /profile."""

    def test_valid_post_redirects_to_profile(self, auth_client):
        """Submitting valid form data must return 302 → /profile."""
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "750.00",
                "category": "Food",
                "date": VALID_DATE,
                "description": "Test lunch",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Expected 302 redirect after valid expense submission"
        )
        assert "/profile" in response.headers["Location"], (
            "Redirect after valid submission should target /profile"
        )

    def test_valid_post_description_appears_on_profile(self, auth_client):
        """After a valid insert, the description must appear in the transaction list on /profile."""
        auth_client.post(
            "/expenses/add",
            data={
                "amount": "999.00",
                "category": "Shopping",
                "date": VALID_DATE,
                "description": "UniqueShoppingTrip2026",
            },
            follow_redirects=True,
        )
        profile_response = auth_client.get("/profile")
        assert b"UniqueShoppingTrip2026" in profile_response.data, (
            "Expected the new expense's description to appear on /profile after insert"
        )

    def test_valid_post_increases_total_spent(self, auth_client, app):
        """After a valid insert, total_spent on /profile must increase by the submitted amount."""
        import database.db as db_module

        before_response = auth_client.get("/profile")
        expected_before = f"{SEED_TOTAL:.2f}".encode()
        assert expected_before in before_response.data, (
            f"Pre-insert total ₹{SEED_TOTAL:.2f} must appear on /profile before the test"
        )

        add_amount = 300.00
        auth_client.post(
            "/expenses/add",
            data={
                "amount": str(add_amount),
                "category": "Transport",
                "date": VALID_DATE,
                "description": "Bus fare",
            },
            follow_redirects=True,
        )

        after_response = auth_client.get("/profile")
        expected_after = f"{SEED_TOTAL + add_amount:.2f}".encode()
        assert expected_after in after_response.data, (
            f"Expected total ₹{SEED_TOTAL + add_amount:.2f} on /profile after insert"
        )

    def test_valid_post_increases_transaction_count(self, auth_client, app):
        """After a valid insert, the transaction count on /profile must increase by 1."""
        auth_client.post(
            "/expenses/add",
            data={
                "amount": "150.00",
                "category": "Health",
                "date": VALID_DATE,
                "description": "Doctor visit",
            },
            follow_redirects=True,
        )
        after_response = auth_client.get("/profile")
        expected_count = SEED_COUNT + 1
        assert str(expected_count).encode() in after_response.data, (
            f"Expected transaction count {expected_count} on /profile after insert"
        )

    def test_valid_post_inserts_row_in_db(self, auth_client, app):
        """After a valid submit, the expenses table must contain exactly one more row."""
        import database.db as db_module

        count_before = _get_expense_count(db_module)

        auth_client.post(
            "/expenses/add",
            data={
                "amount": "500.00",
                "category": "Bills",
                "date": VALID_DATE,
                "description": "Internet bill",
            },
            follow_redirects=False,
        )

        count_after = _get_expense_count(db_module)
        assert count_after == count_before + 1, (
            f"Expected exactly 1 new row in expenses table; before={count_before}, after={count_after}"
        )

    def test_empty_description_redirects_to_profile(self, auth_client):
        """Submitting with an empty description must still succeed with 302 → /profile."""
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "200.00",
                "category": "Other",
                "date": VALID_DATE,
                "description": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302, (
            "Expected 302 redirect when description is empty"
        )
        assert "/profile" in response.headers["Location"], (
            "Redirect target must be /profile when description is empty"
        )

    def test_empty_description_stores_null_in_db(self, auth_client, app):
        """When description is empty the inserted row must have description = NULL."""
        import database.db as db_module

        count_before = _get_expense_count(db_module)

        auth_client.post(
            "/expenses/add",
            data={
                "amount": "250.00",
                "category": "Food",
                "date": VALID_DATE,
                "description": "",
            },
            follow_redirects=False,
        )

        expenses = _get_all_expenses(db_module)
        # The newest row has the highest id — grab all rows inserted after count_before
        inserted = [e for e in expenses if e["id"] > count_before]
        assert len(inserted) == 1, (
            "Expected exactly 1 newly inserted expense row"
        )
        assert inserted[0]["description"] is None, (
            f"Expected description=NULL for empty submission; got {inserted[0]['description']!r}"
        )

    def test_whitespace_only_description_stores_null_in_db(self, auth_client, app):
        """Whitespace-only description must be trimmed to NULL in the DB."""
        import database.db as db_module

        count_before = _get_expense_count(db_module)

        auth_client.post(
            "/expenses/add",
            data={
                "amount": "100.00",
                "category": "Other",
                "date": VALID_DATE,
                "description": "   ",
            },
            follow_redirects=False,
        )

        expenses = _get_all_expenses(db_module)
        inserted = [e for e in expenses if e["id"] > count_before]
        assert len(inserted) == 1, "Expected exactly 1 newly inserted row"
        assert inserted[0]["description"] is None, (
            "Whitespace-only description should be stored as NULL after trimming"
        )

    def test_new_expense_stored_with_correct_amount_category_date(self, auth_client, app):
        """The inserted DB row must have the exact amount, category, and date submitted."""
        import database.db as db_module

        count_before = _get_expense_count(db_module)

        auth_client.post(
            "/expenses/add",
            data={
                "amount": "123.45",
                "category": "Entertainment",
                "date": VALID_DATE,
                "description": "Movie night",
            },
            follow_redirects=False,
        )

        expenses = _get_all_expenses(db_module)
        inserted = [e for e in expenses if e["id"] > count_before]
        assert len(inserted) == 1, "Expected exactly 1 newly inserted row"
        row = inserted[0]
        assert row["amount"] == pytest.approx(123.45), (
            f"Stored amount should be 123.45, got {row['amount']}"
        )
        assert row["category"] == "Entertainment", (
            f"Stored category should be Entertainment, got {row['category']}"
        )
        assert row["date"] == VALID_DATE, (
            f"Stored date should be {VALID_DATE}, got {row['date']}"
        )


# ===========================================================================
# POST — validation failures
# ===========================================================================

class TestPostValidation:
    """Each invalid input must re-render the form (200) with an error message and
    must not insert any row into the expenses table."""

    def _post_and_check_no_insert(self, auth_client, db_module, form_data):
        """Helper: assert response is 200 with an error element, and no DB row inserted."""
        count_before = _get_expense_count(db_module)
        response = auth_client.post(
            "/expenses/add",
            data=form_data,
            follow_redirects=False,
        )
        count_after = _get_expense_count(db_module)
        assert response.status_code == 200, (
            f"Expected 200 (re-render) for invalid data {form_data}, got {response.status_code}"
        )
        # The spec says error is rendered in auth-error div (confirmed from template)
        assert b"auth-error" in response.data, (
            f"Expected inline error element for invalid data {form_data}"
        )
        assert count_after == count_before, (
            f"No new DB row should be inserted for invalid data {form_data}; "
            f"before={count_before}, after={count_after}"
        )
        return response

    def test_amount_zero_is_rejected(self, auth_client, app):
        """amount=0 must re-render with error and no DB insert."""
        import database.db as db_module
        self._post_and_check_no_insert(auth_client, db_module, {
            "amount": "0",
            "category": "Food",
            "date": VALID_DATE,
            "description": "zero test",
        })

    def test_amount_negative_is_rejected(self, auth_client, app):
        """amount=-50 must re-render with error and no DB insert."""
        import database.db as db_module
        self._post_and_check_no_insert(auth_client, db_module, {
            "amount": "-50",
            "category": "Food",
            "date": VALID_DATE,
            "description": "negative test",
        })

    def test_amount_non_numeric_is_rejected(self, auth_client, app):
        """amount='abc' must re-render with error and no DB insert."""
        import database.db as db_module
        self._post_and_check_no_insert(auth_client, db_module, {
            "amount": "abc",
            "category": "Food",
            "date": VALID_DATE,
            "description": "non-numeric test",
        })

    def test_invalid_category_is_rejected(self, auth_client, app):
        """A category not in the canonical list must re-render with error and no DB insert."""
        import database.db as db_module
        self._post_and_check_no_insert(auth_client, db_module, {
            "amount": "500",
            "category": "NotACategory",
            "date": VALID_DATE,
            "description": "tampered category",
        })

    def test_future_date_is_rejected(self, auth_client, app):
        """A date in the future must re-render with error and no DB insert."""
        import database.db as db_module
        future_date = (date.today() + timedelta(days=10)).isoformat()
        self._post_and_check_no_insert(auth_client, db_module, {
            "amount": "500",
            "category": "Food",
            "date": future_date,
            "description": "future date test",
        })

    def test_far_future_date_is_rejected(self, auth_client, app):
        """date=9999-01-01 (far future) must re-render with error and no DB insert."""
        import database.db as db_module
        self._post_and_check_no_insert(auth_client, db_module, {
            "amount": "500",
            "category": "Food",
            "date": "9999-01-01",
            "description": "far future test",
        })

    def test_unparseable_date_is_rejected(self, auth_client, app):
        """date='not-a-date' must re-render with error and no DB insert."""
        import database.db as db_module
        self._post_and_check_no_insert(auth_client, db_module, {
            "amount": "500",
            "category": "Food",
            "date": "not-a-date",
            "description": "bad date test",
        })

    @pytest.mark.parametrize("bad_amount,description", [
        ("0",     "zero amount"),
        ("-100",  "negative amount"),
        ("abc",   "non-numeric amount"),
        ("",      "empty amount"),
    ])
    def test_invalid_amount_parametrized(self, auth_client, app, bad_amount, description):
        """Parametrized check: various invalid amounts must all be rejected with 200 + error."""
        import database.db as db_module
        count_before = _get_expense_count(db_module)
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": bad_amount,
                "category": "Food",
                "date": VALID_DATE,
                "description": description,
            },
            follow_redirects=False,
        )
        count_after = _get_expense_count(db_module)
        assert response.status_code == 200, (
            f"Expected 200 for invalid amount '{bad_amount}', got {response.status_code}"
        )
        assert b"auth-error" in response.data, (
            f"Expected error element for invalid amount '{bad_amount}'"
        )
        assert count_after == count_before, (
            f"No row should be inserted for invalid amount '{bad_amount}'"
        )

    def test_validation_failure_echoes_back_submitted_amount(self, auth_client):
        """On a validation failure the form must echo back the submitted amount value."""
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "777",
                "category": "NotACategory",   # this triggers the error
                "date": VALID_DATE,
                "description": "echo test",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200, "Expected 200 for invalid category"
        assert b"777" in response.data, (
            "Submitted amount '777' should be echoed back in the re-rendered form"
        )

    def test_validation_failure_echoes_back_submitted_description(self, auth_client):
        """On a validation failure the form must echo back the submitted description value."""
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "0",              # this triggers the error
                "category": "Food",
                "date": VALID_DATE,
                "description": "EchoDescriptionValue",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200, "Expected 200 for amount=0"
        assert b"EchoDescriptionValue" in response.data, (
            "Submitted description should be echoed back in the re-rendered form"
        )

    def test_validation_failure_echoes_back_submitted_date(self, auth_client):
        """On a validation failure the form must echo back the submitted date value."""
        submitted_date = VALID_DATE
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "-999",           # this triggers the error
                "category": "Food",
                "date": submitted_date,
                "description": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200, "Expected 200 for negative amount"
        assert submitted_date.encode() in response.data, (
            f"Submitted date '{submitted_date}' should be echoed back in the re-rendered form"
        )

    def test_validation_failure_echoes_back_submitted_category(self, auth_client):
        """On a validation failure the submitted (valid) category must stay selected in the form."""
        # Submit with a valid category but bad amount so the category echo is visible
        response = auth_client.post(
            "/expenses/add",
            data={
                "amount": "0",              # triggers the error
                "category": "Health",
                "date": VALID_DATE,
                "description": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200, "Expected 200 for amount=0"
        assert b"Health" in response.data, (
            "Submitted category 'Health' should appear in the re-rendered form"
        )


# ===========================================================================
# Nav links
# ===========================================================================

class TestNavLinks:
    """The base.html navbar must show the Add expense link only when logged in."""

    def test_logged_in_navbar_contains_add_expense_link(self, auth_client):
        """When logged in, the navbar must include a link pointing to /expenses/add."""
        response = auth_client.get("/profile")
        assert b"/expenses/add" in response.data, (
            "Expected /expenses/add link in the navbar when logged in"
        )

    def test_logged_in_navbar_contains_add_expense_text(self, auth_client):
        """When logged in, the navbar must contain the visible 'Add expense' text."""
        response = auth_client.get("/profile")
        # Case-insensitive search on the decoded page
        html_lower = response.data.lower()
        assert b"add expense" in html_lower, (
            "Expected 'Add expense' text in the navbar when logged in"
        )

    def test_logged_out_navbar_does_not_contain_add_expense_link(self, client):
        """When logged out, the navbar must NOT include a link to /expenses/add."""
        response = client.get("/", follow_redirects=False)
        assert b"/expenses/add" not in response.data, (
            "Expected no /expenses/add link in the navbar when logged out"
        )

    def test_logged_out_landing_page_no_add_expense_nav_link(self, client):
        """The landing page (unauthenticated) must not expose the Add expense nav link."""
        response = client.get("/")
        html_lower = response.data.lower()
        # The nav should not show "add expense" to an anonymous visitor.
        # The page might show it in marketing copy, so we check specifically
        # for the href pointing to /expenses/add.
        assert b"/expenses/add" not in response.data, (
            "Add expense href should not appear in the navbar for anonymous visitors"
        )

    def test_add_expense_page_itself_has_nav_link_when_logged_in(self, auth_client):
        """The /expenses/add page must include the navbar Add expense link (active state)."""
        response = auth_client.get("/expenses/add")
        assert b"/expenses/add" in response.data, (
            "Navbar Add expense link must be present on the add-expense page itself"
        )
