# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the `/profile` page so users can scope the
recent transactions list, summary stats, and category breakdown to a specific
window (e.g. "April 2026" or a custom range). Today every section reflects the
user's entire history; once spending grows, that snapshot becomes noisy. The
filter is driven by two query-string parameters (`start` and `end`) submitted
from a small form on the profile page, and the existing query helpers in
`database/queries.py` are extended to accept optional date bounds. When no
range is provided the page behaves exactly as it does today but with only the most recent 15 transactions shown and if more than 15 transactions exist then a next page button is shown to load the next 15 transactions. This step is a crucial UX improvement that makes the profile page usable as the user's transaction history grows, and it also sets up the core filtering mechanism that future steps (7–9) will build on for more advanced insights and visualisations.

## Depends on
- Step 1: Database setup (`expenses.date` column exists)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page static UI
- Step 5: Backend connection (live query helpers in `database/queries.py`)

## Routes
The existing `GET /profile` route is modified to read `start` and `end` from
the query string and pass them through to the query helpers. No new routes.

- `GET /profile?start=YYYY-MM-DD&end=YYYY-MM-DD` — logged-in — same template,
  data scoped to the date range

## Database changes
No database changes. Filtering uses the existing `expenses.date` column
(stored as ISO `YYYY-MM-DD` strings, which sort lexicographically).

## Templates
- **Modify:** `templates/profile.html`
  - Add a date-filter form above the profile grid that GETs to `/profile`
    with two `<input type="date">` fields named `start` and `end` plus an
    Apply button and a Clear link (a plain `<a href="{{ url_for('profile') }}">`).
  - Above the form, add a row of quick-range tabs — **1 week**, **1 month**,
    **6 months**, **All time** — rendered as `<a>` elements that link to
    `/profile` with the corresponding `start` / `end` query string already
    populated (e.g. `1 week` → `?start=<today-7d>&end=<today>`). Clicking a
    tab navigates to the filtered view, the date inputs render pre-filled
    with that range, and the active tab is visually highlighted when the
    current `start` / `end` exactly match its preset (or when neither is
    set, in the case of **All time**).
  - The inputs must be pre-filled with the currently active `start` / `end`
    values so the filter is visible after submission.
  - When a filter is active and a section has no rows, the existing empty-
    state copy must reflect the range (e.g. "No expenses in this range").
  - If the submitted range is invalid (end before start, or unparseable
    dates), render an inline error message above the form and fall back to
    showing unfiltered data.
  - Show only the most recent 15 transactions in the list, and if more than 15 transactions exist in the active range then show a next page button to load the next 15 transactions.

## Files to change
- `app.py` — read `start` and `end` from `request.args`, validate them, pass
  them to the four query helpers, build the quick-range presets (1 week,
  1 month, 6 months, All time) anchored at today, mark which preset (if any)
  matches the active range, and forward all of that plus any validation
  error to the template
- `templates/profile.html` — add the quick-range tab strip, the filter form,
  pre-fill inputs, render the validation error, and switch empty-state copy
  when a range is active
- `database/queries.py` — add optional `start` / `end` keyword arguments to
  `get_recent_transactions`, `get_summary_stats`, and `get_category_breakdown`
  and apply them as parameterised `date BETWEEN ? AND ?` (or open-ended)
  filters
- `static/css/style.css` — styles for the quick-range tabs (pill row with an
  active state) and the filter form (layout, inputs, button, error message)
  using existing CSS variables

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format dates into SQL
- Date inputs must be parsed with `datetime.strptime(value, "%Y-%m-%d")` and
  rejected on `ValueError`
- An empty `start` or `end` is valid and means "open ended on that side"
- If only one bound is supplied, the SQL must filter with a single-sided
  comparison (`date >= ?` or `date <= ?`) — do not invent a default range
- All templates extend `base.html`
- Use CSS variables — never hardcode hex values
- No inline styles, no `<style>` tags, no JS frameworks
- Currency must always display as ₹
- The query helpers must keep working with no date arguments (existing
  callers and tests must not break)
- `pct` values in the category breakdown must still sum to exactly 100 after
  filtering, using the same rounding-remainder rule as Step 5

## Tests to write

### Unit tests
File: `tests/test_date_filter.py`

| Function | Input | Expected output |
|---|---|---|
| `get_recent_transactions` | `user_id` + `start="2026-04-10"` | only rows with `date >= "2026-04-10"`, newest first |
| `get_recent_transactions` | `user_id` + `end="2026-04-10"` | only rows with `date <= "2026-04-10"` |
| `get_recent_transactions` | `user_id` + `start` and `end` covering 0 rows | empty list |
| `get_summary_stats` | `user_id` + range covering 2 known rows | totals match those two rows; `top_category` reflects them |
| `get_summary_stats` | `user_id` + range covering 0 rows | `{"total_spent": 0, "transaction_count": 0, "top_category": "—"}` |
| `get_category_breakdown` | `user_id` + range covering subset | only categories present in the range; `pct` values are integers summing to 100 |
| `get_category_breakdown` | `user_id` + range covering 0 rows | empty list |

### Route tests
`GET /profile?start=2026-04-10&end=2026-04-20` — authenticated as seed user:
- Returns 200
- Total spent equals the sum of seed expenses dated 2026-04-10 through
  2026-04-20 inclusive
- Transaction count matches the number of seed expenses in that range
- Transaction list contains only rows in the range
- Category breakdown contains only categories in the range
- The two date inputs in the rendered HTML are pre-filled with `2026-04-10`
  and `2026-04-20`

`GET /profile?start=bad-date` — authenticated:
- Returns 200
- Page contains an inline validation error
- Page falls back to unfiltered totals (matches Step 5 numbers)

`GET /profile?start=2026-04-20&end=2026-04-10` — authenticated:
- Returns 200
- Page contains an inline validation error ("End date must be on or after start date")
- Page falls back to unfiltered totals

`GET /profile` — authenticated, no query string:
- Behaves identically to Step 5 (unfiltered totals, no error)

## Definition of done
- [ ] The profile page shows a date-filter form with two date inputs and an
      Apply button above the recent expenses / summary cards
- [ ] Above the form, a row of quick-range tabs (1 week, 1 month, 6 months,
      All time) is visible and clicking any tab navigates to `/profile` with
      `start` / `end` set to that range; the date inputs render pre-filled
      with the tab's range and the tab is visually highlighted as active
- [ ] Submitting `start=2026-04-10` and `end=2026-04-20` as the seed user
      shows only seed expenses in that range, and the totals, transaction
      count, top category, and category breakdown all reflect that range
- [ ] The two date inputs stay pre-filled with the active range after submit
- [ ] Clicking Clear (or the All time tab) returns to `/profile` with no
      query string and restores the unfiltered view
- [ ] Submitting an invalid range (bad date, or end before start) shows an
      inline error message and the page still renders without a 500
- [ ] Visiting `/profile` with no query string behaves exactly as it did
      before this step
- [ ] All amounts still display the ₹ symbol
- [ ] Existing Step 5 tests still pass unchanged
