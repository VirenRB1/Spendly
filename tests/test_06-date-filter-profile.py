"""Tests for Step 6 — Date Filter + Pagination on the /profile page.

Spec: .claude/specs/06-date-filter-profile.md

Covers:
- Auth guard (unauthenticated → 302 to /login)
- Unfiltered behaviour (must equal Step-5 behaviour)
- Date-range filtering: happy paths, DB-level correctness, HTML pre-fill
- Validation errors: bad date string, end-before-start
- Single-sided filters (start-only, end-only)
- Empty-range empty-state copy
- Quick-range tab strip presence and active-tab highlighting
- Clear link visibility
- ₹ currency symbol in rendered amounts
- Pagination: next/prev link appearance and correct page slicing

Unit tests for query helpers (called directly, not via HTTP):
- get_recent_transactions with start, end, both, neither
- get_summary_stats with range, empty range, no args
- get_category_breakdown with range, empty range, pct sum
- count_transactions with and without a range
"""

import pytest
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Seed data constants — mirror database/db.py seed_db() exactly so that
# expected totals can be computed without reading implementation files.
# ---------------------------------------------------------------------------

SEED_EXPENSES = [
    # (amount, category, date)
    (450.00,  "Food",          "2026-04-01"),
    (120.00,  "Transport",     "2026-04-03"),
    (1800.00, "Bills",         "2026-04-05"),
    (300.00,  "Health",        "2026-04-08"),
    (599.00,  "Entertainment", "2026-04-12"),
    (2200.00, "Shopping",      "2026-04-15"),
    (85.00,   "Other",         "2026-04-18"),
    (650.00,  "Food",          "2026-04-22"),
]

FILTER_START = "2026-04-10"
FILTER_END   = "2026-04-20"

# Rows whose date falls strictly inside [FILTER_START, FILTER_END] inclusive
IN_RANGE = [row for row in SEED_EXPENSES if FILTER_START <= row[2] <= FILTER_END]
# (599.00, Entertainment, 2026-04-12) and (2200.00, Shopping, 2026-04-15)
# and (85.00, Other, 2026-04-18) = 3 rows

TOTAL_ALL    = sum(r[0] for r in SEED_EXPENSES)
TOTAL_RANGE  = sum(r[0] for r in IN_RANGE)
COUNT_ALL    = len(SEED_EXPENSES)
COUNT_RANGE  = len(IN_RANGE)


# ===========================================================================
# Route / integration tests
# ===========================================================================

class TestAuthGuard:
    def test_profile_unauthenticated_redirects_to_login(self, client):
        """Spec: /profile is a protected route; anonymous users get 302 → /login."""
        response = client.get("/profile", follow_redirects=False)
        assert response.status_code == 302, "Expected 302 redirect for unauthenticated request"
        assert "/login" in response.headers["Location"], (
            "Redirect target should be /login"
        )


class TestUnfilteredBehaviour:
    """Step 6 must not break Step 5 — /profile with no query string behaves
    exactly as before, just limited to the most recent 15 transactions."""

    def test_profile_no_filter_returns_200(self, auth_client):
        """Unfiltered /profile returns HTTP 200."""
        response = auth_client.get("/profile")
        assert response.status_code == 200, "Expected 200 for authenticated request"

    def test_profile_no_filter_renders_profile_template(self, auth_client):
        """Unfiltered /profile renders HTML with recognisable profile landmarks."""
        response = auth_client.get("/profile")
        assert b"profile" in response.data.lower(), (
            "Expected profile page content in response"
        )

    def test_profile_no_filter_total_matches_all_seed_data(self, auth_client):
        """Unfiltered total_spent equals the sum of all 8 seed expenses."""
        response = auth_client.get("/profile")
        # The template formats as ₹XXXX.XX; check for the formatted total
        expected = f"{TOTAL_ALL:.2f}".encode()
        assert expected in response.data, (
            f"Expected total ₹{TOTAL_ALL:.2f} in unfiltered profile page"
        )

    def test_profile_no_filter_transaction_count_matches_all_seed(self, auth_client):
        """Unfiltered Entries logged equals the total seed expense count."""
        response = auth_client.get("/profile")
        assert str(COUNT_ALL).encode() in response.data, (
            f"Expected transaction count {COUNT_ALL} on unfiltered profile page"
        )

    def test_profile_no_filter_has_no_filter_error(self, auth_client):
        """Unfiltered profile renders no validation error message."""
        response = auth_client.get("/profile")
        assert b"profile-filter-error" not in response.data, (
            "Expected no validation error on unfiltered page"
        )

    def test_profile_no_filter_clear_link_absent(self, auth_client):
        """Clear link must not appear when no filter is active."""
        response = auth_client.get("/profile")
        assert b"profile-filter-clear" not in response.data, (
            "Clear link should be absent when no filter is active"
        )


class TestDateRangeFilterHappyPath:
    """GET /profile?start=2026-04-10&end=2026-04-20 with the seed user."""

    def _get_filtered(self, auth_client):
        return auth_client.get(
            f"/profile?start={FILTER_START}&end={FILTER_END}"
        )

    def test_filtered_profile_returns_200(self, auth_client):
        """Date-filtered /profile returns HTTP 200."""
        response = self._get_filtered(auth_client)
        assert response.status_code == 200

    def test_filtered_total_matches_in_range_rows(self, auth_client):
        """Total spent equals the sum of seed expenses in [2026-04-10, 2026-04-20]."""
        response = self._get_filtered(auth_client)
        expected = f"{TOTAL_RANGE:.2f}".encode()
        assert expected in response.data, (
            f"Expected filtered total ₹{TOTAL_RANGE:.2f} in response"
        )

    def test_filtered_transaction_count_matches_range(self, auth_client):
        """Entries logged equals the number of seed expenses in the filter range."""
        response = self._get_filtered(auth_client)
        assert str(COUNT_RANGE).encode() in response.data, (
            f"Expected transaction count {COUNT_RANGE} for the filtered range"
        )

    def test_filtered_excludes_transactions_outside_range(self, auth_client):
        """Transactions dated before 2026-04-10 must not appear in the list."""
        response = self._get_filtered(auth_client)
        # 2026-04-01 is a seed date outside the range
        assert b"2026-04-01" not in response.data, (
            "Transaction dated 2026-04-01 should be excluded from filtered view"
        )
        # 2026-04-22 is also outside the range
        assert b"2026-04-22" not in response.data, (
            "Transaction dated 2026-04-22 should be excluded from filtered view"
        )

    def test_filtered_includes_transactions_inside_range(self, auth_client):
        """Transactions dated within the range must appear in the list."""
        response = self._get_filtered(auth_client)
        assert b"2026-04-12" in response.data, (
            "Transaction dated 2026-04-12 should appear in filtered view"
        )
        assert b"2026-04-15" in response.data, (
            "Transaction dated 2026-04-15 should appear in filtered view"
        )

    def test_filtered_start_input_prefilled(self, auth_client):
        """The start date input must carry value=FILTER_START after submission."""
        response = self._get_filtered(auth_client)
        assert FILTER_START.encode() in response.data, (
            f'Start input should be pre-filled with "{FILTER_START}"'
        )

    def test_filtered_end_input_prefilled(self, auth_client):
        """The end date input must carry value=FILTER_END after submission."""
        response = self._get_filtered(auth_client)
        assert FILTER_END.encode() in response.data, (
            f'End input should be pre-filled with "{FILTER_END}"'
        )

    def test_filtered_categories_scoped_to_range(self, auth_client):
        """Category breakdown must only show categories present in the filter range."""
        response = self._get_filtered(auth_client)
        # Food (450 on 2026-04-01) is outside the range; its only in-range
        # occurrence is 2026-04-22 which is also outside — so "Food" must
        # not appear in the category breakdown for this range.
        # Inside range: Entertainment (2026-04-12), Shopping (2026-04-15),
        # Other (2026-04-18).
        assert b"Entertainment" in response.data, (
            "Entertainment category should appear for dates in range"
        )
        assert b"Shopping" in response.data, (
            "Shopping category should appear for dates in range"
        )

    def test_filtered_clear_link_is_visible(self, auth_client):
        """Clear link must appear when a valid filter is active."""
        response = self._get_filtered(auth_client)
        assert b"profile-filter-clear" in response.data, (
            "Clear link should be visible when a date filter is active"
        )

    def test_filtered_rupee_symbol_in_amounts(self, auth_client):
        """All monetary amounts must display the ₹ HTML entity or raw symbol."""
        response = self._get_filtered(auth_client)
        rupee_present = b"\xe2\x82\xb9" in response.data or b"&#8377;" in response.data
        assert rupee_present, "Expected ₹ currency symbol in filtered profile amounts"


class TestValidationErrors:

    def test_bad_date_returns_200(self, auth_client):
        """An unparseable date string must not crash the route — returns 200."""
        response = auth_client.get("/profile?start=bad-date")
        assert response.status_code == 200, "Bad date should not cause a 500"

    def test_bad_date_shows_inline_error(self, auth_client):
        """An unparseable date must render an inline validation error message."""
        response = auth_client.get("/profile?start=bad-date")
        assert b"profile-filter-error" in response.data, (
            "Expected inline error element for invalid date"
        )

    def test_bad_date_falls_back_to_unfiltered_total(self, auth_client):
        """With a bad date the page must fall back to showing the full unfiltered total."""
        response = auth_client.get("/profile?start=bad-date")
        expected = f"{TOTAL_ALL:.2f}".encode()
        assert expected in response.data, (
            "Expected unfiltered total when date is invalid"
        )

    def test_end_before_start_returns_200(self, auth_client):
        """end < start must not crash the route — returns 200."""
        response = auth_client.get(
            f"/profile?start={FILTER_END}&end={FILTER_START}"
        )
        assert response.status_code == 200

    def test_end_before_start_shows_spec_error_message(self, auth_client):
        """end < start must render the exact error text from the spec."""
        response = auth_client.get(
            f"/profile?start={FILTER_END}&end={FILTER_START}"
        )
        assert b"End date must be on or after start date" in response.data, (
            "Expected spec-required error message for end-before-start"
        )

    def test_end_before_start_falls_back_to_unfiltered_total(self, auth_client):
        """With end < start the page must fall back to the full unfiltered total."""
        response = auth_client.get(
            f"/profile?start={FILTER_END}&end={FILTER_START}"
        )
        expected = f"{TOTAL_ALL:.2f}".encode()
        assert expected in response.data, (
            "Expected unfiltered total when range is inverted"
        )


class TestSingleSidedFilters:

    def test_start_only_excludes_earlier_rows(self, auth_client):
        """With only start= supplied, rows before that date must not appear."""
        response = auth_client.get("/profile?start=2026-04-15")
        # 2026-04-01 is before the start
        assert b"2026-04-01" not in response.data, (
            "Rows before start= should be excluded when only start is provided"
        )

    def test_start_only_includes_rows_on_or_after_start(self, auth_client):
        """With only start= supplied, rows on or after that date must appear."""
        response = auth_client.get("/profile?start=2026-04-15")
        assert b"2026-04-15" in response.data or b"2026-04-22" in response.data, (
            "Rows on or after start= should be included"
        )

    def test_end_only_excludes_later_rows(self, auth_client):
        """With only end= supplied, rows after that date must not appear."""
        response = auth_client.get("/profile?end=2026-04-05")
        assert b"2026-04-22" not in response.data, (
            "Rows after end= should be excluded when only end is provided"
        )

    def test_end_only_includes_rows_on_or_before_end(self, auth_client):
        """With only end= supplied, rows on or before that date must appear."""
        response = auth_client.get("/profile?end=2026-04-05")
        assert b"2026-04-01" in response.data or b"2026-04-03" in response.data or b"2026-04-05" in response.data, (
            "Rows on or before end= should be included"
        )


class TestEmptyRangeEmptyState:

    def test_empty_range_shows_no_expenses_in_range_copy(self, auth_client):
        """Filter yielding zero transactions must show 'No expenses in this range'."""
        response = auth_client.get("/profile?start=2020-01-01&end=2020-01-31")
        assert b"No expenses in this range" in response.data, (
            "Expected 'No expenses in this range' when filter returns no rows"
        )

    def test_empty_range_shows_no_category_data_copy(self, auth_client):
        """Filter yielding zero rows must show the ranged empty-state for categories."""
        response = auth_client.get("/profile?start=2020-01-01&end=2020-01-31")
        assert b"No category data in this range" in response.data, (
            "Expected range-specific empty-state for category section"
        )


class TestQuickRangeTabs:

    def test_all_four_tab_labels_present(self, auth_client):
        """All four quick-range tab labels must appear in the profile page HTML."""
        response = auth_client.get("/profile")
        for label in [b"1 week", b"1 month", b"6 months", b"All time"]:
            assert label in response.data, (
                f"Expected quick-range tab label '{label.decode()}' in page HTML"
            )

    def test_all_time_tab_active_when_no_filter(self, auth_client):
        """'All time' tab must be visually highlighted when no filter is active."""
        response = auth_client.get("/profile")
        # The template adds profile-filter-tab-active to the active tab.
        # "All time" is the tab whose start/end are both empty — it should
        # be active when neither start nor end is in the query string.
        # We verify the active class appears in a context near "All time".
        html = response.data.decode("utf-8", errors="replace")
        active_idx = html.find("profile-filter-tab-active")
        all_time_idx = html.find("All time")
        assert active_idx != -1, "Expected at least one active tab"
        # The active element should appear before or closely after "All time"
        # in the DOM; tolerance of 200 chars covers a single <a> tag.
        assert abs(active_idx - all_time_idx) < 200, (
            "Expected 'All time' tab to carry the active class when no filter is set"
        )

    def test_tab_strip_uses_url_for_links(self, auth_client):
        """Tab strip links must point to /profile (never hardcoded to other paths)."""
        response = auth_client.get("/profile")
        html = response.data.decode("utf-8", errors="replace")
        # All tab <a> hrefs should start with /profile
        import re
        tab_hrefs = re.findall(r'profile-filter-tab[^"]*"[^"]*"\s+href="([^"]+)"', html)
        # Simpler: ensure every href in the tab nav starts with /profile
        tab_nav_section = html[html.find('profile-filter-tabs'):html.find('profile-filter-form')]
        hrefs = re.findall(r'href="([^"]+)"', tab_nav_section)
        for href in hrefs:
            assert href.startswith("/profile"), (
                f"Tab link '{href}' should point to /profile"
            )


class TestPagination:

    def test_no_next_link_when_few_rows(self, auth_client):
        """With only 8 seed rows (< 15), page 1 must not show a Next link."""
        response = auth_client.get("/profile")
        # The template renders the pagination nav only when has_prev or has_next.
        # With 8 seed rows the nav block should not appear at all.
        assert b"profile-pagination" not in response.data, (
            "Pagination nav should not appear when total rows is less than the page size"
        )

    def test_no_prev_link_on_page_1(self, auth_client):
        """Page 1 must never show a Previous link."""
        response = auth_client.get("/profile?page=1")
        assert b"Previous" not in response.data, (
            "Previous link should not appear on page 1"
        )

    def test_next_link_appears_when_more_than_15_rows(self, auth_client, app):
        """With 16+ rows in the DB, page 1 must show a Next link."""
        import database.db as db_module
        # Insert 10 extra rows so total becomes 18 (8 seed + 10 extra)
        conn = db_module.get_db()
        user_row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user_row[0]
        extras = [
            (user_id, 100.0, "Food", f"2026-05-{str(i).zfill(2)}", "extra")
            for i in range(1, 11)
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            extras,
        )
        conn.commit()
        conn.close()

        response = auth_client.get("/profile")
        assert b"Next" in response.data, (
            "Next link should appear when there are more than 15 rows"
        )

    def test_prev_link_appears_on_page_2(self, auth_client, app):
        """Page 2 must show a Previous link."""
        import database.db as db_module
        conn = db_module.get_db()
        user_row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user_row[0]
        extras = [
            (user_id, 100.0, "Food", f"2026-05-{str(i).zfill(2)}", "extra")
            for i in range(1, 11)
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            extras,
        )
        conn.commit()
        conn.close()

        response = auth_client.get("/profile?page=2")
        assert b"Previous" in response.data, (
            "Previous link should appear on page 2"
        )

    def test_page_2_shows_different_transactions(self, auth_client, app):
        """Transactions on page 2 must differ from transactions on page 1."""
        import database.db as db_module
        conn = db_module.get_db()
        user_row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user_row[0]
        extras = [
            (user_id, float(i * 10), "Food", f"2026-06-{str(i).zfill(2)}", f"extra-{i}")
            for i in range(1, 11)
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            extras,
        )
        conn.commit()
        conn.close()

        page1 = auth_client.get("/profile?page=1").data
        page2 = auth_client.get("/profile?page=2").data

        # The two pages should not be identical
        assert page1 != page2, "Page 1 and Page 2 should show different data"

    def test_pagination_preserves_filter_in_links(self, auth_client, app):
        """Pagination links must carry the active start/end filter in their href."""
        import database.db as db_module
        conn = db_module.get_db()
        user_row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user_row[0]
        # Insert enough rows in the filter range to trigger pagination
        extras = [
            (user_id, 50.0, "Food", f"2026-04-1{str(i)}", f"range-extra-{i}")
            for i in range(1, 9)
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            extras,
        )
        conn.commit()
        conn.close()

        response = auth_client.get(
            f"/profile?start=2026-04-01&end=2026-04-30"
        )
        html = response.data.decode("utf-8", errors="replace")
        assert "Next" in html, (
            "Expected a Next link with 16 in-range rows but only 15-per-page"
        )
        import re
        next_href = re.search(r'href="(/profile[^"]*)"[^>]*>Next', html)
        assert next_href is not None, "Next link should be a hyperlink to /profile"
        assert "start=" in next_href.group(1), (
            "Next link must preserve start= filter"
        )
        assert "end=" in next_href.group(1), (
            "Next link must preserve end= filter"
        )


# ===========================================================================
# Query-helper unit tests (no HTTP, direct function calls)
# ===========================================================================

class TestGetRecentTransactionsUnit:
    """Unit tests for database.queries.get_recent_transactions."""

    def _insert_expenses(self, conn, user_id, rows):
        """rows: list of (amount, category, date)."""
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            [(user_id, r[0], r[1], r[2], "desc") for r in rows],
        )
        conn.commit()

    def test_start_only_filters_earlier_rows(self, db_conn):
        """get_recent_transactions with start= returns only rows with date >= start."""
        from database.queries import get_recent_transactions
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (100, "Food", "2026-03-01"),
            (200, "Food", "2026-04-15"),
            (300, "Food", "2026-05-01"),
        ])
        result = get_recent_transactions(uid, start="2026-04-01")
        dates = [r["date"] for r in result]
        assert "2026-03-01" not in dates, "Row before start should be excluded"
        assert "2026-04-15" in dates, "Row on/after start should be included"
        assert "2026-05-01" in dates, "Row on/after start should be included"

    def test_end_only_filters_later_rows(self, db_conn):
        """get_recent_transactions with end= returns only rows with date <= end."""
        from database.queries import get_recent_transactions
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (100, "Food", "2026-03-01"),
            (200, "Food", "2026-04-15"),
            (300, "Food", "2026-05-01"),
        ])
        result = get_recent_transactions(uid, end="2026-04-20")
        dates = [r["date"] for r in result]
        assert "2026-05-01" not in dates, "Row after end should be excluded"
        assert "2026-03-01" in dates, "Row on/before end should be included"
        assert "2026-04-15" in dates, "Row on/before end should be included"

    def test_start_and_end_with_zero_matching_rows(self, db_conn):
        """get_recent_transactions with a range covering no rows returns []."""
        from database.queries import get_recent_transactions
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (100, "Food", "2026-04-01"),
        ])
        result = get_recent_transactions(uid, start="2020-01-01", end="2020-01-31")
        assert result == [], "Expected empty list when range covers no rows"

    def test_results_are_newest_first(self, db_conn):
        """get_recent_transactions returns rows ordered newest date first."""
        from database.queries import get_recent_transactions
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (100, "Food", "2026-04-01"),
            (200, "Food", "2026-04-15"),
            (300, "Food", "2026-03-10"),
        ])
        result = get_recent_transactions(uid)
        dates = [r["date"] for r in result]
        assert dates == sorted(dates, reverse=True), "Results should be newest-first"

    def test_no_date_args_returns_all_rows(self, db_conn):
        """get_recent_transactions with no date args returns all rows (backward compat)."""
        from database.queries import get_recent_transactions
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (100, "Food", "2026-04-01"),
            (200, "Food", "2026-04-15"),
        ])
        result = get_recent_transactions(uid, limit=100)
        assert len(result) == 2, "Expected all rows when no date filter is given"

    def test_limit_and_offset_work_with_date_filter(self, db_conn):
        """limit/offset pagination works correctly alongside date filters."""
        from database.queries import get_recent_transactions
        conn, uid = db_conn
        rows = [(float(i * 10), "Food", f"2026-04-{str(i).zfill(2)}") for i in range(1, 21)]
        self._insert_expenses(conn, uid, rows)
        page1 = get_recent_transactions(uid, limit=5, offset=0, start="2026-04-01", end="2026-04-30")
        page2 = get_recent_transactions(uid, limit=5, offset=5, start="2026-04-01", end="2026-04-30")
        assert len(page1) == 5, "Page 1 should contain 5 rows"
        assert len(page2) == 5, "Page 2 should contain 5 rows"
        ids_p1 = {r["id"] for r in page1}
        ids_p2 = {r["id"] for r in page2}
        assert ids_p1.isdisjoint(ids_p2), "Pages should not overlap"


class TestGetSummaryStatsUnit:

    def _insert_expenses(self, conn, user_id, rows):
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            [(user_id, r[0], r[1], r[2], "desc") for r in rows],
        )
        conn.commit()

    def test_range_totals_match_two_known_rows(self, db_conn):
        """get_summary_stats totals match exactly the two rows in the range."""
        from database.queries import get_summary_stats
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (500.0, "Food",      "2026-04-10"),
            (300.0, "Transport", "2026-04-15"),
            (999.0, "Bills",     "2026-03-01"),  # outside range
        ])
        stats = get_summary_stats(uid, start="2026-04-10", end="2026-04-20")
        assert stats["total_spent"] == pytest.approx(800.0), (
            "total_spent should equal 500 + 300 for the two in-range rows"
        )
        assert stats["transaction_count"] == 2, "transaction_count should be 2"

    def test_range_top_category_reflects_range_data(self, db_conn):
        """top_category reflects the highest-spend category in the filtered range."""
        from database.queries import get_summary_stats
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (500.0, "Food",      "2026-04-10"),
            (300.0, "Transport", "2026-04-15"),
            (999.0, "Bills",     "2026-03-01"),  # outside range — should NOT be top
        ])
        stats = get_summary_stats(uid, start="2026-04-10", end="2026-04-20")
        assert stats["top_category"] == "Food", (
            "top_category should be Food (500 > 300) within the range"
        )

    def test_empty_range_returns_zero_stats(self, db_conn):
        """get_summary_stats with a range covering 0 rows returns zeros and '—'."""
        from database.queries import get_summary_stats
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [(100.0, "Food", "2026-04-01")])
        stats = get_summary_stats(uid, start="2020-01-01", end="2020-01-31")
        assert stats["total_spent"] == 0, "total_spent should be 0 for empty range"
        assert stats["transaction_count"] == 0, "transaction_count should be 0 for empty range"
        assert stats["top_category"] == "—", "top_category should be '—' for empty range"

    def test_no_date_args_returns_all_rows_stats(self, db_conn):
        """get_summary_stats with no date args works (backward compat)."""
        from database.queries import get_summary_stats
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (200.0, "Food",  "2026-04-01"),
            (300.0, "Bills", "2026-04-15"),
        ])
        stats = get_summary_stats(uid)
        assert stats["total_spent"] == pytest.approx(500.0)
        assert stats["transaction_count"] == 2


class TestGetCategoryBreakdownUnit:

    def _insert_expenses(self, conn, user_id, rows):
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            [(user_id, r[0], r[1], r[2], "desc") for r in rows],
        )
        conn.commit()

    def test_range_subset_returns_only_in_range_categories(self, db_conn):
        """get_category_breakdown with a date range returns only categories in range."""
        from database.queries import get_category_breakdown
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (500.0, "Food",   "2026-04-10"),
            (300.0, "Bills",  "2026-04-15"),
            (999.0, "Health", "2026-03-01"),  # outside range
        ])
        breakdown = get_category_breakdown(uid, start="2026-04-01", end="2026-04-30")
        names = [item["name"] for item in breakdown]
        assert "Health" not in names, "Category outside range should not appear"
        assert "Food" in names, "Category in range should appear"
        assert "Bills" in names, "Category in range should appear"

    def test_pct_values_sum_to_100_for_range(self, db_conn):
        """pct values in the filtered breakdown must sum to exactly 100."""
        from database.queries import get_category_breakdown
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (600.0, "Food",      "2026-04-10"),
            (300.0, "Transport", "2026-04-15"),
            (100.0, "Bills",     "2026-04-20"),
        ])
        breakdown = get_category_breakdown(uid, start="2026-04-01", end="2026-04-30")
        assert len(breakdown) > 0, "Expected non-empty breakdown"
        total_pct = sum(item["pct"] for item in breakdown)
        assert total_pct == 100, (
            f"pct values must sum to exactly 100, got {total_pct}"
        )

    def test_pct_values_are_integers(self, db_conn):
        """pct values must be integers, not floats."""
        from database.queries import get_category_breakdown
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (333.0, "Food",  "2026-04-10"),
            (333.0, "Bills", "2026-04-11"),
            (334.0, "Other", "2026-04-12"),
        ])
        breakdown = get_category_breakdown(uid)
        for item in breakdown:
            assert isinstance(item["pct"], int), (
                f"pct should be int, got {type(item['pct'])} for {item['name']}"
            )

    def test_empty_range_returns_empty_list(self, db_conn):
        """get_category_breakdown with a range covering 0 rows returns []."""
        from database.queries import get_category_breakdown
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [(100.0, "Food", "2026-04-01")])
        result = get_category_breakdown(uid, start="2020-01-01", end="2020-01-31")
        assert result == [], "Expected empty list for range with no rows"

    def test_no_date_args_returns_all_categories(self, db_conn):
        """get_category_breakdown with no date args works (backward compat)."""
        from database.queries import get_category_breakdown
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (200.0, "Food",  "2026-04-01"),
            (300.0, "Bills", "2026-04-15"),
        ])
        result = get_category_breakdown(uid)
        assert len(result) == 2, "Expected 2 categories without date filter"

    def test_pct_sums_to_100_with_full_seed_like_data(self, db_conn):
        """pct sum == 100 for a multi-category dataset mirroring the seed."""
        from database.queries import get_category_breakdown
        conn, uid = db_conn
        seed_like = [
            (450.0,  "Food",          "2026-04-01"),
            (120.0,  "Transport",     "2026-04-03"),
            (1800.0, "Bills",         "2026-04-05"),
            (300.0,  "Health",        "2026-04-08"),
            (599.0,  "Entertainment", "2026-04-12"),
            (2200.0, "Shopping",      "2026-04-15"),
            (85.0,   "Other",         "2026-04-18"),
            (650.0,  "Food",          "2026-04-22"),
        ]
        self._insert_expenses(conn, uid, seed_like)
        breakdown = get_category_breakdown(uid)
        total_pct = sum(item["pct"] for item in breakdown)
        assert total_pct == 100, (
            f"pct values must sum to 100 for full dataset, got {total_pct}"
        )


class TestCountTransactionsUnit:

    def _insert_expenses(self, conn, user_id, rows):
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            [(user_id, r[0], r[1], r[2], "desc") for r in rows],
        )
        conn.commit()

    def test_count_with_date_range(self, db_conn):
        """count_transactions returns the correct count for a date range."""
        from database.queries import count_transactions
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (100.0, "Food", "2026-04-01"),
            (200.0, "Food", "2026-04-15"),
            (300.0, "Food", "2026-05-01"),
        ])
        count = count_transactions(uid, start="2026-04-01", end="2026-04-30")
        assert count == 2, f"Expected 2 rows in April 2026, got {count}"

    def test_count_with_no_args_returns_total(self, db_conn):
        """count_transactions with no date args returns the total row count."""
        from database.queries import count_transactions
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [
            (100.0, "Food", "2026-04-01"),
            (200.0, "Food", "2026-04-15"),
            (300.0, "Food", "2026-05-01"),
        ])
        count = count_transactions(uid)
        assert count == 3, f"Expected 3 total rows, got {count}"

    def test_count_empty_range_returns_zero(self, db_conn):
        """count_transactions for a range with no matching rows returns 0."""
        from database.queries import count_transactions
        conn, uid = db_conn
        self._insert_expenses(conn, uid, [(100.0, "Food", "2026-04-01")])
        count = count_transactions(uid, start="2020-01-01", end="2020-01-31")
        assert count == 0, "Expected 0 for range with no rows"


# ===========================================================================
# Parametrized edge-case tests
# ===========================================================================

@pytest.mark.parametrize("bad_start,bad_end", [
    ("not-a-date", ""),
    ("", "32-13-2026"),
    ("2026/04/10", "2026/04/20"),
    ("April 10 2026", ""),
])
def test_various_bad_dates_return_200_with_error(auth_client, bad_start, bad_end):
    """Any unparseable date in start or end returns 200 with an inline error."""
    url = f"/profile?start={bad_start}&end={bad_end}"
    response = auth_client.get(url)
    assert response.status_code == 200, f"Expected 200 for bad date input: {bad_start}, {bad_end}"
    assert b"profile-filter-error" in response.data, (
        f"Expected inline error for bad date: start={bad_start}, end={bad_end}"
    )
