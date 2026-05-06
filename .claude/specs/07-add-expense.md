# Spec: Add Expense

## Overview
Step 7 introduces the first write path for expense data. Until now the
database has only ever been populated by `seed_db()` and registration; users
can read their spending on `/profile` but have no way to record a new expense.
This step turns `/expenses/add` from a placeholder string into a real form
that lets a logged-in user create an expense (amount, category, date,
optional description) and persists it to the `expenses` table. After a
successful submission the user is redirected back to `/profile`, where the
new row immediately shows up in the transaction list, summary stats, and
category breakdown thanks to the live queries built in Steps 5–6. This is
the foundation that Steps 8 (edit) and 9 (delete) will build on.

## Depends on
- Step 1: Database setup (`expenses` table and `get_db()` exist)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page static UI (target of the post-submit redirect)
- Step 5: Backend connection (live queries on `/profile` will surface the new row)

## Routes
- `GET  /expenses/add` — render the new-expense form — logged-in
- `POST /expenses/add` — validate and insert a new expense, then redirect to `/profile` — logged-in

Both replace the current stub at `app.py` that returns the string
`"Add expense — coming in Step 7"`. Unauthenticated requests to either
method must redirect to `/login` (matching the `/profile` pattern).

## Database changes
No database changes. The `expenses` table already has every column needed
(`user_id`, `amount`, `category`, `date`, `description`, `created_at`).

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`
  - Renders a single form that POSTs to `url_for('add_expense')` with these fields:
    - `amount` — `<input type="number" step="0.01" min="0.01" required>`
    - `category` — `<select required>` populated with the canonical set:
      Food, Transport, Bills, Health, Entertainment, Shopping, Other
    - `date` — `<input type="date" required>`, defaulted to today on GET
    - `description` — `<input type="text" maxlength="200">` (optional)
    - Submit button labelled "Add expense"
    - Cancel link back to `url_for('profile')`
  - Renders `{% if error %}<div class="form-error">{{ error }}</div>{% endif %}`
    above the form
  - On validation failure, re-renders the form with the user's previously
    entered values pre-filled (so they don't have to retype)
  - Currency hint next to the amount field uses ₹ (e.g. `<span>₹</span>` prefix)
- **Modify:** `templates/base.html`
  - Add an "Add expense" link to the logged-in nav (alongside the existing
    Profile / Logout links) pointing at `url_for('add_expense')`
- **Modify:** `templates/profile.html`
  - Add a primary "Add expense" call-to-action button near the top of the
    page (e.g. next to the page heading or in the filter bar) linking to
    `url_for('add_expense')`. This makes the new flow discoverable from the
    main screen the user lands on after login.

## Files to change
- `app.py`
  - Replace the existing `add_expense` stub with a real `GET`/`POST` route
  - On `GET`: redirect to `/login` if not logged in, otherwise render
    `add_expense.html` with `today=date.today().isoformat()` and the
    canonical category list
  - On `POST`: redirect to `/login` if not logged in, otherwise read
    `amount`, `category`, `date`, `description` from `request.form`,
    validate them, call the new DB helper, and `redirect(url_for('profile'))`
    on success; re-render with `error` and echoed values on failure
- `database/db.py`
  - Add `create_expense(user_id, amount, category, date, description)` that
    runs a parameterised `INSERT` and returns the new row id
- `templates/base.html` — add the nav link (see Templates above)
- `templates/profile.html` — add the CTA button (see Templates above)
- `static/css/style.css` — styles for the add-expense form layout, the
  inline ₹ prefix, the form-error block, and the new CTA button, all using
  existing CSS variables

## Files to create
- `templates/add_expense.html`

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
- Passwords hashed with werkzeug (not relevant here, but stated for
  consistency across specs)
- The route must reject unauthenticated requests with a redirect to
  `/login`, matching the `/profile` pattern
- Server-side validation is mandatory — the `required`, `min`, and
  `maxlength` HTML attributes are a UX nicety, not a security boundary:
  - `amount` must parse as a positive `float` (> 0); reject otherwise
  - `category` must be one of the seven canonical values listed above;
    reject anything else (defends against tampered selects)
  - `date` must parse with `datetime.strptime(value, "%Y-%m-%d")` and must
    not be in the future
  - `description` is optional; trim whitespace and treat empty as `NULL`;
    cap length at 200 characters
- On any validation failure, re-render the form with an inline error
  message and echo the user's submitted values back into the inputs
- The expense must be inserted with the logged-in user's `user_id` from
  `session["user_id"]` — never trust a client-supplied user id
- After a successful insert, redirect (HTTP 302) to `/profile` — do not
  render the form again on success (avoids the double-submit refresh trap)

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders a form with amount,
      category, date, and description fields, with the date pre-filled to today
- [ ] Submitting a valid expense as the seed user redirects to `/profile`
      and the new row appears at the top of the transaction list
- [ ] The new expense is reflected in the summary stats (total spent and
      transaction count both increase by the expected amounts)
- [ ] The new expense is reflected in the category breakdown for its category
- [ ] Submitting with `amount=0`, a negative amount, or a non-numeric
      amount re-renders the form with an inline error and does not insert
- [ ] Submitting with a category not in the canonical list re-renders with
      an error and does not insert
- [ ] Submitting with an unparseable or future date re-renders with an
      error and does not insert
- [ ] Submitting with a missing description still succeeds; the row is
      stored with `description = NULL`
- [ ] On any validation failure, the form re-renders with the user's
      previously entered values pre-filled
- [ ] The base navbar shows an "Add expense" link only when logged in
- [ ] The profile page shows a primary "Add expense" CTA linking to the form
- [ ] All amounts on the new form and the resulting profile view display
      the ₹ symbol
- [ ] Existing Step 5 and Step 6 tests still pass unchanged
