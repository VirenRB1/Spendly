"""Tests for Step 8 — Edit Expense feature.

Spec: .claude/specs/08-edit-expense.md

Covers:
- Auth guard: GET and POST while unauthenticated redirect to /login
- GET with non-existent expense id returns 404
- GET with expense owned by another user returns 403
- GET as owner: 200, form pre-filled with all four fields (amount, category, date,
  description), ₹ symbol present
- POST happy path: 302 → /profile, updated values appear in transaction list and DB row
- POST category change: category breakdown on /profile shifts accordingly
- POST validation failures — amount=0, negative, non-numeric: 200 + inline error,
  DB row unchanged
- POST invalid category: 200 + inline error, DB row unchanged
- POST unparseable date: 200 + inline error, DB row unchanged
- POST future date: 200 + inline error, DB row unchanged
- On any validation failure the form re-renders with submitted (not original) values
- Each transaction row on /profile has an Edit link pointing to the correct URL
"""

import sqlite3
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Seed data constants — mirror database/db.py seed_db() exactly so that
# expected values can be computed without reading the implementation files.
# Seed inserts 8 expenses for the demo user; IDs will be 1-8.
# ---------------------------------------------------------------------------

SEED_EXPENSES = [
    (1, 450.00, "Food", "2026-04-01", "Lunch at canteen"),
    (2, 120.00, "Transport", "2026-04-03", "Auto rickshaw"),
    (3, 1800.00, "Bills", "2026-04-05", "Electricity bill"),
    (4, 300.00, "Health", "2026-04-08", "Pharmacy"),
    (5, 599.00, "Entertainment", "2026-04-12", "OTT subscription"),
    (6, 2200.00, "Shopping", "2026-04-15", "Clothes"),
    (7, 85.00, "Other", "2026-04-18", "Stationery"),
    (8, 650.00, "Food", "2026-04-22", "Dinner with friends"),
]

# Use the first seeded expense as the canonical target for most tests.
TARGET_ID = 1
TARGET_AMOUNT = 450.00
TARGET_CATEGORY = "Food"
TARGET_DATE = "2026-04-01"
TARGET_DESCRIPTION = "Lunch at canteen"

SEED_TOTAL = sum(r[1] for r in SEED_EXPENSES)  # 6204.00
SEED_COUNT = len(SEED_EXPENSES)  # 8

CANONICAL_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

# A valid past date that will never be "in the future".
VALID_DATE = "2026-04-25"
EDIT_URL = f"/expenses/{TARGET_ID}/edit"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_expense_by_id(db_module, expense_id):
    """Return a dict for the given expense id, or None."""
    conn = db_module.get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id, amount, category, date, description "
            "FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _create_second_user(db_module):
    """Insert a second user and return their id."""
    conn = db_module.get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other User", "other@spendly.com", generate_password_hash("otherpass")),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _login_as_second_user(client):
    """Log in via the HTTP test client as the second user."""
    client.post(
        "/login",
        data={"email": "other@spendly.com", "password": "otherpass"},
        follow_redirects=False,
    )


# ===========================================================================
# Auth guard
# ===========================================================================


class TestAuthGuard:
    """GET and POST to /expenses/<id>/edit while unauthenticated must redirect to /login."""

    def test_get_edit_unauthenticated_redirects_to_login(self, client):
        """GET /expenses/1/edit without a session must return 302 → /login."""
        response = client.get(EDIT_URL, follow_redirects=False)
        assert (
            response.status_code == 302
        ), "Expected 302 redirect for unauthenticated GET /expenses/<id>/edit"
        assert (
            "/login" in response.headers["Location"]
        ), "Redirect target must be /login for unauthenticated GET"

    def test_post_edit_unauthenticated_redirects_to_login(self, client):
        """POST /expenses/1/edit without a session must return 302 → /login."""
        response = client.post(
            EDIT_URL,
            data={
                "amount": "500",
                "category": "Food",
                "date": VALID_DATE,
                "description": "should not save",
            },
            follow_redirects=False,
        )
        assert (
            response.status_code == 302
        ), "Expected 302 redirect for unauthenticated POST /expenses/<id>/edit"
        assert (
            "/login" in response.headers["Location"]
        ), "Redirect target must be /login for unauthenticated POST"


# ===========================================================================
# 404 — non-existent expense id
# ===========================================================================


class TestNotFound:
    """Requests for a non-existent expense id must return 404."""

    def test_get_nonexistent_id_returns_404(self, auth_client):
        """GET /expenses/99999/edit for an id that does not exist must return 404."""
        response = auth_client.get("/expenses/99999/edit", follow_redirects=False)
        assert (
            response.status_code == 404
        ), "Expected 404 when GETting edit form for a non-existent expense id"

    def test_post_nonexistent_id_returns_404(self, auth_client):
        """POST /expenses/99999/edit for an id that does not exist must return 404."""
        response = auth_client.post(
            "/expenses/99999/edit",
            data={
                "amount": "100",
                "category": "Food",
                "date": VALID_DATE,
                "description": "ghost",
            },
            follow_redirects=False,
        )
        assert (
            response.status_code == 404
        ), "Expected 404 when POSTing to edit form for a non-existent expense id"


# ===========================================================================
# 403 — expense owned by another user
# ===========================================================================


class TestOwnershipGuard:
    """Requests for an expense owned by a different user must return 403."""

    def test_get_other_users_expense_returns_403(self, app, client):
        """GET /expenses/<id>/edit for expense owned by another user must return 403."""
        import database.db as db_module

        _create_second_user(db_module)
        _login_as_second_user(client)

        # Expense id=1 belongs to the demo (seed) user, not the second user.
        response = client.get(EDIT_URL, follow_redirects=False)
        assert (
            response.status_code == 403
        ), "Expected 403 when a user tries to GET another user's edit form"

    def test_post_other_users_expense_returns_403(self, app, client):
        """POST /expenses/<id>/edit for expense owned by another user must return 403."""
        import database.db as db_module

        _create_second_user(db_module)
        _login_as_second_user(client)

        response = client.post(
            EDIT_URL,
            data={
                "amount": "999",
                "category": "Food",
                "date": VALID_DATE,
                "description": "unauthorized update attempt",
            },
            follow_redirects=False,
        )
        assert (
            response.status_code == 403
        ), "Expected 403 when a user tries to POST to another user's edit form"


# ===========================================================================
# GET — form rendering
# ===========================================================================


class TestGetForm:
    """The edit form must render correctly and pre-fill all four fields."""

    def test_get_returns_200_for_owner(self, auth_client):
        """GET /expenses/<id>/edit as the owning user must return 200."""
        response = auth_client.get(EDIT_URL, follow_redirects=False)
        assert (
            response.status_code == 200
        ), "Expected 200 for authenticated GET /expenses/<id>/edit as owner"

    def test_get_form_prefills_amount(self, auth_client):
        """The rendered form must pre-fill the amount field with the stored value."""
        response = auth_client.get(EDIT_URL)
        # 450.0 is stored; the template may render as 450.0 or 450.00
        assert (
            b"450" in response.data
        ), f"Expected amount {TARGET_AMOUNT} to be pre-filled in the edit form"

    def test_get_form_prefills_category(self, auth_client):
        """The rendered form must pre-fill (select) the stored category."""
        response = auth_client.get(EDIT_URL)
        assert (
            TARGET_CATEGORY.encode() in response.data
        ), f"Expected category '{TARGET_CATEGORY}' to be pre-filled in the edit form"

    def test_get_form_prefills_date(self, auth_client):
        """The rendered form must pre-fill the date field with the stored value."""
        response = auth_client.get(EDIT_URL)
        assert (
            TARGET_DATE.encode() in response.data
        ), f"Expected date '{TARGET_DATE}' to be pre-filled in the edit form"

    def test_get_form_prefills_description(self, auth_client):
        """The rendered form must pre-fill the description field with the stored value."""
        response = auth_client.get(EDIT_URL)
        assert (
            TARGET_DESCRIPTION.encode() in response.data
        ), f"Expected description '{TARGET_DESCRIPTION}' to be pre-filled in the edit form"

    @pytest.mark.parametrize("category", CANONICAL_CATEGORIES)
    def test_get_form_contains_all_canonical_categories(self, auth_client, category):
        """The edit form must include all 7 canonical category options."""
        response = auth_client.get(EDIT_URL)
        assert (
            category.encode() in response.data
        ), f"Expected category '{category}' to appear in the edit form options"

    def test_get_form_contains_rupee_symbol(self, auth_client):
        """The edit form must display the ₹ symbol (UTF-8 or &#8377;)."""
        response = auth_client.get(EDIT_URL)
        rupee_present = (
            "₹".encode("utf-8") in response.data or b"&#8377;" in response.data
        )
        assert (
            rupee_present
        ), "Expected ₹ symbol (UTF-8 or &#8377;) in the edit expense form"

    def test_get_form_has_save_changes_button(self, auth_client):
        """The edit form must have a submit button labelled 'Save changes'."""
        response = auth_client.get(EDIT_URL)
        html_lower = response.data.lower()
        assert (
            b"save changes" in html_lower
        ), "Expected 'Save changes' submit button in the edit form"

    def test_get_form_action_points_to_edit_url(self, auth_client):
        """The form action must point to the correct /expenses/<id>/edit URL."""
        response = auth_client.get(EDIT_URL)
        assert (
            EDIT_URL.encode() in response.data
        ), f"Expected form action URL '{EDIT_URL}' to appear in the rendered page"


# ===========================================================================
# POST — happy path
# ===========================================================================


class TestPostHappyPath:
    """A valid POST must update the DB row and redirect to /profile."""

    def test_valid_post_redirects_to_profile(self, auth_client):
        """Submitting valid updated data must return 302 → /profile."""
        response = auth_client.post(
            EDIT_URL,
            data={
                "amount": "500.00",
                "category": "Food",
                "date": VALID_DATE,
                "description": "Updated lunch",
            },
            follow_redirects=False,
        )
        assert (
            response.status_code == 302
        ), "Expected 302 redirect after valid expense update"
        assert (
            "/profile" in response.headers["Location"]
        ), "Redirect after valid update must target /profile"

    def test_valid_post_updates_db_row(self, auth_client, app):
        """After a valid POST the DB row must reflect the submitted values."""
        import database.db as db_module

        new_amount = 750.00
        new_category = "Transport"
        new_date = VALID_DATE
        new_description = "Updated description"

        auth_client.post(
            EDIT_URL,
            data={
                "amount": str(new_amount),
                "category": new_category,
                "date": new_date,
                "description": new_description,
            },
            follow_redirects=False,
        )

        row = _get_expense_by_id(db_module, TARGET_ID)
        assert row is not None, "Expense row must still exist after update"
        assert row["amount"] == pytest.approx(
            new_amount
        ), f"DB amount should be {new_amount}, got {row['amount']}"
        assert (
            row["category"] == new_category
        ), f"DB category should be '{new_category}', got '{row['category']}'"
        assert (
            row["date"] == new_date
        ), f"DB date should be '{new_date}', got '{row['date']}'"
        assert (
            row["description"] == new_description
        ), f"DB description should be '{new_description}', got '{row['description']}'"

    def test_valid_post_does_not_change_row_count(self, auth_client, app):
        """A valid edit must update the existing row, not insert a new one."""
        import database.db as db_module

        conn = db_module.get_db()
        count_before = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        conn.close()

        auth_client.post(
            EDIT_URL,
            data={
                "amount": "600",
                "category": "Food",
                "date": VALID_DATE,
                "description": "Still just one row",
            },
            follow_redirects=False,
        )

        conn = db_module.get_db()
        count_after = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        conn.close()

        assert (
            count_after == count_before
        ), f"Edit must not change the number of rows; before={count_before}, after={count_after}"

    def test_valid_post_updated_description_appears_on_profile(self, auth_client):
        """After a valid update, the new description must appear on /profile."""
        unique_description = "UniqueEditedDescription8765"
        auth_client.post(
            EDIT_URL,
            data={
                "amount": "450",
                "category": "Food",
                "date": VALID_DATE,
                "description": unique_description,
            },
            follow_redirects=True,
        )
        profile_response = auth_client.get("/profile")
        assert (
            unique_description.encode() in profile_response.data
        ), "Expected the updated description to appear in the transaction list on /profile"

    def test_valid_post_empty_description_stores_null(self, auth_client, app):
        """Submitting an empty description during edit must store NULL in the DB."""
        import database.db as db_module

        auth_client.post(
            EDIT_URL,
            data={
                "amount": "450",
                "category": "Food",
                "date": VALID_DATE,
                "description": "",
            },
            follow_redirects=False,
        )

        row = _get_expense_by_id(db_module, TARGET_ID)
        assert (
            row["description"] is None
        ), f"Expected description=NULL for empty submission, got {row['description']!r}"

    def test_valid_post_whitespace_description_stores_null(self, auth_client, app):
        """Whitespace-only description must be trimmed to NULL in the DB on edit."""
        import database.db as db_module

        auth_client.post(
            EDIT_URL,
            data={
                "amount": "450",
                "category": "Food",
                "date": VALID_DATE,
                "description": "   ",
            },
            follow_redirects=False,
        )

        row = _get_expense_by_id(db_module, TARGET_ID)
        assert (
            row["description"] is None
        ), "Whitespace-only description should be stored as NULL after trimming"


# ===========================================================================
# POST — category change shifts /profile breakdown
# ===========================================================================


class TestCategoryChangeBreakdown:
    """Changing a category via edit must be reflected in the /profile breakdown."""

    def test_category_change_shifts_breakdown_on_profile(self, auth_client):
        """Editing expense id=1 from Food to Bills must change the category totals on /profile."""
        # Before: expense 1 is Food ₹450. Get the profile and confirm Food appears.
        before_response = auth_client.get("/profile")
        assert (
            b"Food" in before_response.data
        ), "Expected 'Food' category to appear on /profile before the edit"

        # Edit: change category from Food to Bills.
        auth_client.post(
            EDIT_URL,
            data={
                "amount": str(TARGET_AMOUNT),
                "category": "Bills",
                "date": TARGET_DATE,
                "description": TARGET_DESCRIPTION,
            },
            follow_redirects=True,
        )

        after_response = auth_client.get("/profile")
        assert (
            b"Bills" in after_response.data
        ), "Expected 'Bills' to appear in the category breakdown after editing expense to Bills"

    def test_category_change_updates_db_category(self, auth_client, app):
        """After changing the category, the DB row must store the new category."""
        import database.db as db_module

        auth_client.post(
            EDIT_URL,
            data={
                "amount": str(TARGET_AMOUNT),
                "category": "Shopping",
                "date": TARGET_DATE,
                "description": TARGET_DESCRIPTION,
            },
            follow_redirects=False,
        )

        row = _get_expense_by_id(db_module, TARGET_ID)
        assert (
            row["category"] == "Shopping"
        ), f"DB category should be 'Shopping' after update, got '{row['category']}'"


# ===========================================================================
# POST — validation failures
# ===========================================================================


class TestPostValidation:
    """Each invalid input must re-render the form (200) with an error, and must NOT
    update the DB row."""

    def _post_invalid_and_check(self, auth_client, db_module, form_data):
        """Helper: post to EDIT_URL with invalid data; assert 200 + error element + DB unchanged."""
        original = _get_expense_by_id(db_module, TARGET_ID)

        response = auth_client.post(
            EDIT_URL,
            data=form_data,
            follow_redirects=False,
        )

        after = _get_expense_by_id(db_module, TARGET_ID)

        assert (
            response.status_code == 200
        ), f"Expected 200 (re-render) for invalid data {form_data}, got {response.status_code}"
        # The spec says an inline error is rendered; check for a form-error element.
        assert (
            b"form-error" in response.data or b"error" in response.data.lower()
        ), f"Expected an inline error message for invalid data {form_data}"
        assert after["amount"] == pytest.approx(
            original["amount"]
        ), "DB amount must not change after a validation failure"
        assert (
            after["category"] == original["category"]
        ), "DB category must not change after a validation failure"
        assert (
            after["date"] == original["date"]
        ), "DB date must not change after a validation failure"
        return response

    def test_amount_zero_is_rejected(self, auth_client, app):
        """amount=0 must re-render with error and leave the DB row unchanged."""
        import database.db as db_module

        self._post_invalid_and_check(
            auth_client,
            db_module,
            {
                "amount": "0",
                "category": "Food",
                "date": VALID_DATE,
                "description": "zero amount test",
            },
        )

    def test_amount_negative_is_rejected(self, auth_client, app):
        """A negative amount must re-render with error and leave the DB row unchanged."""
        import database.db as db_module

        self._post_invalid_and_check(
            auth_client,
            db_module,
            {
                "amount": "-100",
                "category": "Food",
                "date": VALID_DATE,
                "description": "negative amount test",
            },
        )

    def test_amount_non_numeric_is_rejected(self, auth_client, app):
        """A non-numeric amount must re-render with error and leave the DB row unchanged."""
        import database.db as db_module

        self._post_invalid_and_check(
            auth_client,
            db_module,
            {
                "amount": "abc",
                "category": "Food",
                "date": VALID_DATE,
                "description": "non-numeric amount test",
            },
        )

    def test_invalid_category_is_rejected(self, auth_client, app):
        """A category not in the canonical list must re-render with error and DB unchanged."""
        import database.db as db_module

        self._post_invalid_and_check(
            auth_client,
            db_module,
            {
                "amount": "500",
                "category": "NotACategory",
                "date": VALID_DATE,
                "description": "invalid category test",
            },
        )

    def test_unparseable_date_is_rejected(self, auth_client, app):
        """An unparseable date string must re-render with error and DB unchanged."""
        import database.db as db_module

        self._post_invalid_and_check(
            auth_client,
            db_module,
            {
                "amount": "500",
                "category": "Food",
                "date": "not-a-date",
                "description": "bad date test",
            },
        )

    def test_future_date_is_rejected(self, auth_client, app):
        """A date in the future must re-render with error and leave the DB row unchanged."""
        import database.db as db_module

        future_date = (date.today() + timedelta(days=10)).isoformat()
        self._post_invalid_and_check(
            auth_client,
            db_module,
            {
                "amount": "500",
                "category": "Food",
                "date": future_date,
                "description": "future date test",
            },
        )

    def test_far_future_date_is_rejected(self, auth_client, app):
        """date=9999-01-01 (far future) must re-render with error and DB unchanged."""
        import database.db as db_module

        self._post_invalid_and_check(
            auth_client,
            db_module,
            {
                "amount": "500",
                "category": "Food",
                "date": "9999-01-01",
                "description": "far future test",
            },
        )

    @pytest.mark.parametrize("bad_amount", ["0", "-50", "abc", ""])
    def test_invalid_amounts_parametrized(self, auth_client, app, bad_amount):
        """All invalid amount variants must be rejected with 200 and an error message."""
        import database.db as db_module

        response = auth_client.post(
            EDIT_URL,
            data={
                "amount": bad_amount,
                "category": "Food",
                "date": VALID_DATE,
                "description": "parametrized amount test",
            },
            follow_redirects=False,
        )
        assert (
            response.status_code == 200
        ), f"Expected 200 for invalid amount '{bad_amount}', got {response.status_code}"
        assert (
            b"form-error" in response.data or b"error" in response.data.lower()
        ), f"Expected an error message for invalid amount '{bad_amount}'"


# ===========================================================================
# POST — submitted values echoed back on validation failure
# ===========================================================================


class TestEchoOnValidationFailure:
    """On any validation failure the form must echo the submitted values, not the
    original DB values."""

    def test_submitted_amount_echoed_back(self, auth_client):
        """When category is invalid the form must echo the submitted (wrong) amount."""
        response = auth_client.post(
            EDIT_URL,
            data={
                "amount": "8888",  # valid, but category below is not
                "category": "NotACategory",
                "date": VALID_DATE,
                "description": "echo test",
            },
            follow_redirects=False,
        )
        assert (
            response.status_code == 200
        ), "Expected 200 re-render for invalid category"
        assert b"8888" in response.data, (
            "Submitted amount '8888' must be echoed back into the form on validation failure, "
            f"not the original value {TARGET_AMOUNT}"
        )

    def test_submitted_description_echoed_back(self, auth_client):
        """When amount=0 the form must echo the submitted description, not the original."""
        submitted_desc = "ThisIsTheSubmittedDescription"
        response = auth_client.post(
            EDIT_URL,
            data={
                "amount": "0",  # triggers the error
                "category": "Food",
                "date": VALID_DATE,
                "description": submitted_desc,
            },
            follow_redirects=False,
        )
        assert response.status_code == 200, "Expected 200 re-render for amount=0"
        assert submitted_desc.encode() in response.data, (
            f"Submitted description '{submitted_desc}' must be echoed back on validation failure, "
            f"not the original '{TARGET_DESCRIPTION}'"
        )

    def test_submitted_date_echoed_back(self, auth_client):
        """When amount is negative the form must echo the submitted date, not the original."""
        submitted_date = "2026-03-15"
        response = auth_client.post(
            EDIT_URL,
            data={
                "amount": "-999",  # triggers the error
                "category": "Food",
                "date": submitted_date,
                "description": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200, "Expected 200 re-render for negative amount"
        assert submitted_date.encode() in response.data, (
            f"Submitted date '{submitted_date}' must be echoed back on validation failure, "
            f"not the original '{TARGET_DATE}'"
        )

    def test_submitted_category_echoed_back(self, auth_client):
        """When amount=0 the form must echo the submitted (valid) category as the selected option."""
        response = auth_client.post(
            EDIT_URL,
            data={
                "amount": "0",  # triggers the error
                "category": "Health",  # different from original Food
                "date": VALID_DATE,
                "description": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200, "Expected 200 re-render for amount=0"
        assert (
            b"Health" in response.data
        ), "Submitted category 'Health' must appear in the re-rendered form on validation failure"

    def test_original_values_not_used_on_failure(self, auth_client):
        """The echoed amount must match the submitted value, not the original DB value."""
        # Submit a different valid amount but trigger failure with bad category.
        # If the form echoes original (450), this test fails.
        response = auth_client.post(
            EDIT_URL,
            data={
                "amount": "9999",
                "category": "InvalidCategory",
                "date": VALID_DATE,
                "description": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 200, "Expected 200 re-render"
        assert (
            b"9999" in response.data
        ), "The submitted amount '9999' must be echoed back, not the original '450'"
        # The original amount should not replace the submitted one in the form field value.
        # We cannot assert 450 is absent (it may appear elsewhere), so we assert 9999 is present.


# ===========================================================================
# Edit links on /profile
# ===========================================================================


class TestEditLinksOnProfile:
    """Every transaction row on /profile must include an Edit link to the correct URL."""

    def test_profile_transaction_rows_contain_edit_links(self, auth_client):
        """The /profile page must contain at least one Edit link in the transaction list."""
        response = auth_client.get("/profile")
        # The href pattern /expenses/<id>/edit must appear in the page.
        assert (
            b"/expenses/" in response.data
        ), "Expected expense URLs to appear on /profile"
        assert (
            b"/edit" in response.data
        ), "Expected '/edit' links in the transaction list on /profile"

    def test_profile_edit_link_for_seed_expense_1(self, auth_client):
        """The /profile page must include an edit link pointing to /expenses/1/edit."""
        response = auth_client.get("/profile")
        assert (
            b"/expenses/1/edit" in response.data
        ), "Expected href='/expenses/1/edit' to appear in the transaction list on /profile"

    def test_profile_edit_links_are_labelled_edit(self, auth_client):
        """The Edit links on /profile must have visible 'Edit' text."""
        response = auth_client.get("/profile")
        html = response.data.lower()
        assert (
            b"edit" in html
        ), "Expected 'Edit' text to appear in the transaction list on /profile"

    def test_each_seed_expense_has_a_unique_edit_link(self, auth_client):
        """Every seeded expense id must have a corresponding /expenses/<id>/edit link on /profile."""
        response = auth_client.get("/profile")
        # Seed has 8 expenses; all IDs 1-8 should have edit links.
        for seed_row in SEED_EXPENSES:
            expense_id = seed_row[0]
            expected_href = f"/expenses/{expense_id}/edit".encode()
            assert expected_href in response.data, (
                f"Expected edit link for expense id={expense_id} to appear on /profile; "
                f"href '{expected_href.decode()}' not found in page"
            )

    def test_edit_link_navigates_to_correct_form(self, auth_client):
        """Clicking the edit link for a seed expense must render that expense's pre-filled form."""
        # Use expense id=6 (Shopping ₹2200 "Clothes") to verify independently of id=1.
        response = auth_client.get("/expenses/6/edit", follow_redirects=False)
        assert (
            response.status_code == 200
        ), "Expected 200 for GET /expenses/6/edit as owner"
        # The stored description "Clothes" must appear in the pre-filled form.
        assert (
            b"Clothes" in response.data
        ), "Expected stored description 'Clothes' to be pre-filled in /expenses/6/edit form"
        # The stored category "Shopping" must appear.
        assert (
            b"Shopping" in response.data
        ), "Expected stored category 'Shopping' to be pre-filled in /expenses/6/edit form"
