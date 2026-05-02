# Spec: Login and Logout

## Overview
Wire up real session-based authentication for Spendly. Today `/login` only renders the form (GET-only) and `/logout` returns a placeholder string — submitting either form errors out. This step adds the POST handler for `/login` that verifies credentials with `werkzeug.security.check_password_hash`, stores the authenticated user's id in a Flask `session`, and turns `/logout` into a real route that clears the session. It also updates `base.html` so the navbar reflects auth state (Sign in / Get started when logged out; profile + Logout when logged in). This is the prerequisite for every logged-in feature that follows — `/profile` (Step 4) and the expense CRUD routes (Steps 7–9) all assume `session["user_id"]` is set.

## Depends on
- **Step 1 — Database setup**: `users` table with hashed `password_hash` column and `get_user_by_email` helper.
- **Step 2 — Registration**: ensures real users exist with werkzeug-hashed passwords so login has something to authenticate against.

## Routes
- `POST /login` — accepts `email` and `password` from the login form; verifies the password hash; on success stores `session["user_id"]` and redirects to `/profile`; on failure re-renders `login.html` with a generic error. Access level: **public**.
- `GET /logout` — clears the session and redirects to `/`. Access level: **logged-in** (also safe to hit when logged out — just no-ops and redirects).

The existing `GET /login` route stays unchanged (refactor `login()` to dispatch on `request.method`). The `/logout` placeholder gets replaced with a real implementation.

## Database changes
No database changes. The `users` table already has `id`, `email`, and `password_hash` — everything needed to authenticate. Sessions are signed cookies; nothing is persisted server-side.

## Templates
- **Create:** none.
- **Modify:**
  - `templates/login.html` — pass typed `email` back through on validation error so the user does not retype (already supports `{{ error }}`). Two-line edit, no restructuring.
  - `templates/base.html` — make the navbar auth-aware. When `session["user_id"]` is set, show a link to `/profile` and a `Logout` link instead of `Sign in` / `Get started`. Use Jinja's `session` global directly (Flask exposes it to templates).

## Files to change
- `app.py` — set `app.secret_key`; convert `login()` into a GET/POST view; replace the stub `logout()` with `session.clear()` + redirect; add `session` to the Flask import line.
- `templates/login.html` — add `value="{{ email or '' }}"` to the email input.
- `templates/base.html` — conditional nav-links block.

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is a sibling of the already-imported `generate_password_hash`. Flask's built-in `session` module is used as-is.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `database/db.py` helpers.
- Parameterised queries only — reuse `get_user_by_email`; do not write new SQL inline in `app.py`.
- Passwords hashed with werkzeug — verify with `check_password_hash(stored_hash, submitted_password)`. Never compare strings directly. Never log or echo passwords.
- All templates extend `base.html` (already true for `login.html`).
- Use CSS variables — never hardcode hex values (applies if any CSS is touched; expected to be minimal/none).
- `app.secret_key` must be set before any session is read or written. Read it from `os.environ.get("SPENDLY_SECRET_KEY")` with a fallback dev default — leaking the dev default in prod is acceptable for a learning project, but the env-var path must work.
- The login error message must be **generic** ("Invalid email or password.") — do not differentiate between "no such email" and "wrong password". This prevents email enumeration.
- Email is normalised with `.strip().lower()` before lookup so casing matches what registration stored.
- On successful login: `session.clear()` first (drop any stale state), then set `session["user_id"]` to the user's `id`, then redirect to `/profile`.
- On logout: call `session.clear()` and redirect to `/` — do not redirect back to `/login` (UX nicer when logged-out lands on the marketing page).
- `session["user_id"]` is the **single source of truth** for "is this request authenticated". Future steps will consume this; don't introduce parallel session keys (`logged_in` flags, `user_email`, etc.).
- Navbar logic in `base.html` uses `{% if session.user_id %}` — do not call any helpers or read the DB from the template.
- Use `url_for('login')`, `url_for('logout')`, `url_for('profile')`, `url_for('landing')` for every internal link — no hardcoded paths.

## Definition of done
- [ ] Visiting `GET /login` renders the empty form (regression check).
- [ ] Submitting the login form with the seeded `demo@spendly.com` / `demo123` (or any registered user) redirects (302) to `/profile` and sets a `session` cookie.
- [ ] `session["user_id"]` after a successful login matches the row id of the authenticated user.
- [ ] Submitting with a wrong password re-renders `login.html` with the generic error "Invalid email or password." and **no** session cookie is set.
- [ ] Submitting with an unknown email returns the **same** error message as the wrong-password case (no email enumeration).
- [ ] Submitting with a missing field re-renders `login.html` with a visible error and does not authenticate.
- [ ] Email casing is ignored — `DEMO@spendly.com` logs in the same user as `demo@spendly.com`.
- [ ] On the login error page, the email field is pre-filled with what the user typed; the password field is empty.
- [ ] Visiting `GET /logout` while logged in clears `session["user_id"]` and redirects (302) to `/`.
- [ ] Visiting `GET /logout` while logged out redirects (302) to `/` without raising.
- [ ] After logout, navigating to a page that uses session (e.g. the navbar) shows the logged-out links again.
- [ ] Navbar in `base.html`:
  - Logged out → shows `Sign in` and `Get started` links (current behaviour).
  - Logged in → shows a `Profile` link and a `Logout` link.
- [ ] App starts on port 5001 with no errors (`python app.py`); no `RuntimeError: The session is unavailable because no secret key was set` is raised.
- [ ] No SQL is written inline in `app.py` for login — uses `get_user_by_email` from `database/db.py`.
