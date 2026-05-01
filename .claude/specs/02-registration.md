# Spec: Registration

## Overview
Add a working POST handler for `/register` so visitors can create a Spendly account. The GET handler and `register.html` template already exist; this step wires up form submission, server-side validation, password hashing, and persistence to the `users` table created in Step 1. Registration is the gateway feature for everything after this — login (Step 3), profile (Step 4), and expense CRUD (Steps 7–9) all assume a populated `users` table with hashed credentials.

## Depends on
- **Step 1 — Database setup**: requires `users` table, `get_db()`, and `werkzeug.security` to be in place (already complete on `master`).

## Routes
- `POST /register` — accepts `name`, `email`, `password` from the registration form; validates inputs, hashes the password, inserts a new user row, and on success redirects to `/login`. On failure re-renders `register.html` with an `error` message. Access level: **public**.

The existing `GET /register` route stays unchanged. Refactor the `register()` view to dispatch on `request.method`.

## Database changes
No database changes. The `users` table from Step 1 already has every column required: `id`, `name`, `email`, `password_hash`, `created_at`. The `UNIQUE` constraint on `email` is the integrity guarantee for duplicate-account prevention.

## Templates
- **Create:** none.
- **Modify:** none required. `templates/register.html` already renders `{{ error }}` and posts to `/register`. (Optional: pass back the previously submitted `name` / `email` values so the user does not retype on validation failure — only do this if it does not require restructuring the template.)

## Files to change
- `app.py` — replace the current `register()` view with one that handles both `GET` and `POST`. Add `request`, `redirect`, `url_for`, `flash` (only if used) to the Flask import line. Delegate the DB write to a new helper in `database/db.py`.
- `database/db.py` — add `create_user(name, email, password_hash)` and `get_user_by_email(email)` helpers. Both must use parameterised queries.

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.generate_password_hash` is already imported in `database/db.py`.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only.
- Parameterised queries only — never use f-strings or `%` formatting in SQL.
- Hash passwords with `werkzeug.security.generate_password_hash` before insert; never store plaintext.
- All templates extend `base.html` (already true for `register.html`).
- Use CSS variables — never hardcode hex values (no template/CSS edits expected, but applies if any are made).
- All DB access goes through helpers in `database/db.py` — no inline SQL in `app.py`.
- Use `url_for('login')` / `url_for('register')` for redirects — no hardcoded paths.
- Validation must happen server-side even though the form has `required` attributes:
  - `name`, `email`, `password` are all required and stripped of surrounding whitespace.
  - `password` must be at least 8 characters (matches the placeholder hint in the template).
  - `email` must be normalised to lowercase before lookup/insert so duplicates are caught case-insensitively.
- Duplicate-email handling: check with `get_user_by_email` before insert and return a friendly error. Also catch `sqlite3.IntegrityError` as a backstop in case of a race.
- On success: redirect to `GET /login` with HTTP 302. Do not auto-login (login handler does not exist yet — that is Step 3).
- Error messages rendered to the user must be generic and user-facing (e.g., "An account with that email already exists.") — never leak stack traces or raw SQL.

## Definition of done
- [ ] Submitting the registration form with valid `name`, `email`, and an 8+ character `password` creates a new row in `users` and redirects to `/login` (verify with `sqlite3 expense_tracker.db "SELECT id, name, email FROM users;"`).
- [ ] The stored `password_hash` is a werkzeug hash (starts with `pbkdf2:` or `scrypt:`), not the plaintext password.
- [ ] Submitting with a missing field re-renders `register.html` with a visible error and does not insert a row.
- [ ] Submitting with a password shorter than 8 characters re-renders `register.html` with a visible error.
- [ ] Submitting with an email that already exists (any casing) re-renders `register.html` with a duplicate-email error and does not insert a row.
- [ ] Email is stored lowercase in the DB regardless of how the user typed it.
- [ ] `GET /register` still renders the empty form (no regression).
- [ ] No SQL is written inline in `app.py` — all DB access goes through `database/db.py`.
- [ ] App starts on port 5001 with no errors (`python app.py`).
