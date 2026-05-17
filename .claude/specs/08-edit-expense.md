# Spec: Edit Expense

## Overview
Step 8 lets users correct mistakes in expenses they have already recorded.
Until now the `expenses` table is append-only from the UI — a typo in an
amount or a wrong category requires direct DB surgery. This step turns
`/expenses/<id>/edit` from a placeholder string into a real form that loads
an existing expense pre-filled, validates changes with the same rules as Step
7 (Add Expense), and writes the updated row back to the database. The form is
discoverable via Edit links added to each row on `/profile`. After a
successful update the user is redirected back to `/profile` with a flash
confirmation. Ownership is enforced server-side: a user cannot edit another
user's expense.

## Depends on
- Step 1: Database setup (`expenses` table exists with `user_id`, `amount`,
  `category`, `date`, `description` columns)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Backend connection (profile page renders the transaction list)
- Step 7: Add Expense (establishes the form pattern, CSS styles, and
  validation rules this step reuses)

## Routes
- `GET  /expenses/<int:id>/edit` — render the edit form pre-filled with the
  existing expense values — logged-in only
- `POST /expenses/<int:id>/edit` — validate and apply the update, then
  redirect to `/profile` — logged-in only

Both replace the current stub at `app.py` that returns the string
`"Edit expense — coming in Step 8"`. Unauthenticated requests must redirect
to `/login`. Requests for an expense that does not exist must `abort(404)`.
Requests from a user who does not own the expense must `abort(403)`.

## Database changes
No new tables or columns. Two new helper functions are needed in
`database/db.py` to fetch and update a single expense row.

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html`
  - Identical field set to `add_expense.html` (amount, category, date,
    description) with all inputs pre-filled from the fetched expense row
  - Form POSTs to `url_for('edit_expense', id=expense.id)`
  - Renders `{% if error %}<div class="form-error">{{ error }}</div>{% endif %}`
    above the form
  - On validation failure, re-renders with the user's submitted values (not
    the original DB values)
  - Currency hint next to amount uses ₹
  - Submit button labelled "Save changes"
  - Cancel link back to `url_for('profile')`
- **Modify:** `templates/profile.html`
  - Add an "Edit" link to each row in the recent transactions table, pointing
    to `url_for('edit_expense', id=tx.id)`

## Files to change
- `app.py`
  - Replace the `edit_expense` stub with real `GET` / `POST` handlers
  - On `GET`: redirect to `/login` if not authenticated; call
    `get_expense_by_id(id)` — `abort(404)` if `None`; `abort(403)` if
    `expense['user_id'] != session['user_id']`; render `edit_expense.html`
    with the expense values and the canonical category list
  - On `POST`: same auth + ownership checks; read `amount`, `category`,
    `date`, `description` from `request.form`; apply the same validation
    logic as `add_expense`; call `update_expense(...)` on success and
    `redirect(url_for('profile'))` with a flash message; re-render with
    `error` and the submitted values on failure
- `database/db.py`
  - Add `get_expense_by_id(expense_id)` — parameterised `SELECT` returning
    the full expense row (all columns) or `None`
  - Add `update_expense(expense_id, amount, category, date, description)` —
    parameterised `UPDATE` on the `expenses` table; returns nothing
- `templates/profile.html` — add Edit links to each transaction row
- `static/css/style.css` — styles for the Edit link in transaction rows,
  using existing CSS variables; the edit form reuses existing form styles
  from Step 7

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format form values into SQL
- Database logic stays in `database/db.py` — the route must not open
  connections or write SQL directly
- All templates extend `base.html`
- Use CSS variables — never hardcode hex values
- No inline styles, no `<style>` tags, no JS frameworks
- Currency must always display as ₹ — never $ or USD
- Passwords hashed with werkzeug (not relevant here, stated for consistency)
- Ownership must be checked after the 404 check: `get_expense_by_id` first,
  then compare `user_id` — do not leak existence of other users' expenses via
  different error codes (both non-existent and forbidden can return 404 in
  production, but for this learning project 403 is acceptable)
- Validation rules are identical to Step 7:
  - `amount` must parse as a positive `float` (> 0)
  - `category` must be one of the seven canonical values in `CATEGORIES`
  - `date` must parse with `datetime.strptime(value, "%Y-%m-%d")` and must
    not be in the future
  - `description` is optional; trim whitespace and store empty as `NULL`;
    cap at 200 characters
- On any validation failure, re-render the form with the submitted values
  echoed back (not the original DB values) and an inline error message
- After a successful update, `flash("Expense updated.", "success")` then
  `redirect(url_for('profile'))` — do not re-render the form on success
- Do not modify `created_at` during an update — only touch the four
  user-editable columns (`amount`, `category`, `date`, `description`)

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for a non-existent id returns 404
- [ ] Visiting `/expenses/<id>/edit` for an expense owned by another user
      returns 403
- [ ] Visiting `/expenses/<id>/edit` while logged in as the owner renders a
      form with all four fields pre-filled with the current expense values
- [ ] Submitting valid changes redirects to `/profile` and the updated values
      appear in the transaction list
- [ ] The summary stats and category breakdown on `/profile` reflect the
      updated values (e.g. changing a Food expense to Transport shifts the
      breakdown)
- [ ] Submitting with `amount=0`, a negative amount, or a non-numeric amount
      re-renders the form with an inline error and does not update the row
- [ ] Submitting with a category not in the canonical list re-renders with an
      error and does not update
- [ ] Submitting with an unparseable or future date re-renders with an error
      and does not update
- [ ] On any validation failure, the form re-renders with the submitted
      values pre-filled (not the original DB values)
- [ ] Each row in the profile transaction list has an Edit link that navigates
      to the correct `/expenses/<id>/edit` URL
- [ ] All amounts on the edit form and the resulting profile view display ₹
- [ ] Existing Step 5, 6, and 7 tests still pass unchanged
