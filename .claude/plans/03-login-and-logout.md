# Plan: Step 03 — Login and Logout

## Context
After Step 2 the app can create new users with werkzeug-hashed passwords, but `/login` is GET-only (POSTing 405s) and `/logout` returns the placeholder string `"Logout — coming in Step 3"`. Until login actually authenticates and stashes the user id in the Flask session, none of the downstream steps — `/profile` (Step 4), expense CRUD (Steps 7–9) — can gate on "is this request logged in." This step closes that gap: real `POST /login` with `check_password_hash`, a `session.clear()` based logout, an auth-aware navbar in `base.html`, and `app.secret_key` so sessions can actually be signed.

The session key chosen here — `session["user_id"]` — becomes the contract every later step reads. We must not introduce parallel keys.

## Files to modify
- `app.py` — add `session` import + `check_password_hash`; set `app.secret_key`; convert `login()` to GET/POST; replace stub `logout()`.
- `templates/login.html` — pre-fill the email field on validation error.
- `templates/base.html` — auth-aware navbar.

## Files to create
None.

---

## Change 1 — `app.py`: imports and secret key

Add to the top of `app.py`:

```python
import os
```

Update the existing Flask import line to pull in `session`:

```python
from flask import Flask, render_template, request, redirect, url_for, session
```

Update the werkzeug import to include the verifier:

```python
from werkzeug.security import generate_password_hash, check_password_hash
```

Right after `app = Flask(__name__)`:

```python
app.secret_key = os.environ.get("SPENDLY_SECRET_KEY", "dev-only-change-me")
```

Why a fallback default: this is a learning project run from a student laptop with no env file. The fallback keeps `python app.py` zero-config; production override path still works.

## Change 2 — `app.py`: GET/POST login view

Replace the existing `login()` function (currently lines 70–72):

```python
@app.route("/login", methods=["GET", "POST"])
def login():
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
```

Notes:
- Single generic error for both "no such email" and "wrong password" → no email enumeration.
- `session.clear()` before setting the new id wipes any stale state (defence-in-depth against session fixation; cheap to do).
- `email` is passed back to the template on every error path; `password` never is.
- Reuses `get_user_by_email` already in `database/db.py:70`. No new SQL.
- Redirects to `url_for("profile")` — `/profile` is currently a stub returning a string, but `url_for` resolves on the route function name, not on the response, so this is fine. Step 4 will replace the stub.

## Change 3 — `app.py`: real logout

Replace the stub `logout()` (currently lines 89–91):

```python
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))
```

Notes:
- `session.clear()` is a no-op when there is no session, so visiting `/logout` while logged out just redirects to `/` without raising. Spec requires this.
- Redirect target is the landing page, not `/login` — friendlier UX after deliberate sign-out.
- GET-only is acceptable here for the learning project. (CSRF-aware production auth would require POST, but there is no CSRF protection anywhere else in the app yet — out of scope for Step 3.)

## Change 4 — `templates/login.html`: preserve typed email

Edit lines 23–25 to add a `value` attribute. Mirrors the pattern landed in `register.html` for Step 2:

```html
<input type="email" id="email" name="email"
       class="form-input" placeholder="nitish@example.com"
       value="{{ email or '' }}"
       required autofocus>
```

Do **not** add a value to the password field.

## Change 5 — `templates/base.html`: auth-aware navbar

Replace the `<div class="nav-links">` block (currently lines 21–24) with a Jinja conditional. Flask exposes `session` to all templates by default — no helper or context processor needed.

```html
<div class="nav-links">
    {% if session.user_id %}
        <a href="{{ url_for('profile') }}">Profile</a>
        <a href="{{ url_for('logout') }}" class="nav-cta">Logout</a>
    {% else %}
        <a href="{{ url_for('login') }}">Sign in</a>
        <a href="{{ url_for('register') }}" class="nav-cta">Get started</a>
    {% endif %}
</div>
```

Notes:
- Reuses the existing `nav-cta` class for the right-most action button — no CSS changes needed; the green-pill style already lives in `static/css/style.css`.
- `session.user_id` is `None`/missing for logged-out requests, so the `else` branch is the current behaviour. No regression for guests.

---

## Verification

Stop any running server, restart, and exercise each path. The seeded `demo@spendly.com` / `demo123` is the canonical test account.

```bash
source venv/Scripts/activate
python app.py
```

Use `curl` with a cookie jar so the session cookie persists across requests.

| Case | Steps | Expected |
| --- | --- | --- |
| GET regression | `curl -i http://127.0.0.1:5001/login` | 200, empty form, no error block |
| Happy path | `curl -i -c jar.txt -X POST -d "email=demo@spendly.com&password=demo123" http://127.0.0.1:5001/login` | 302 → `/profile`; `jar.txt` contains a `session` cookie |
| Casing ignored | Same with `email=DEMO@spendly.com` | Same 302 → `/profile` |
| Wrong password | POST `password=wrong` | 200, body contains `Invalid email or password.`, no `session` cookie set |
| Unknown email | POST `email=nobody@nowhere.com&password=whatever` | 200, **same** `Invalid email or password.` message (enumeration check) |
| Missing field | POST with empty password | 200, body contains `Please enter your email` |
| Email pre-filled | Trigger any error | `value="..."` attribute on email input is the typed value |
| Logout | `curl -i -b jar.txt http://127.0.0.1:5001/logout` | 302 → `/`; subsequent requests with same cookie jar see logged-out navbar |
| Logout when logged out | `curl -i http://127.0.0.1:5001/logout` (no cookie) | 302 → `/`, no error |
| Navbar logged in | Browser: log in, hit `/` | Navbar shows `Profile` and `Logout` |
| Navbar logged out | Browser: log out, hit `/` | Navbar shows `Sign in` and `Get started` |
| App startup | `python app.py` | Boots on port 5001, no `RuntimeError` about secret key |

Inspect session payload to confirm `user_id` is the integer row id (not the email or anything else):

```python
# In a python -c after the happy-path request:
from itsdangerous import URLSafeTimedSerializer
# Easier: just check via /profile once Step 4 lands. For now confirm the cookie exists.
```

For the navbar checks, view the rendered HTML — the conditional swap is the verification, no DB query needed.

## Out of scope
- `/profile` content (Step 4) — login redirects to the existing stub for now.
- `@login_required` decorator — not needed until Step 4 introduces gated routes.
- CSRF tokens on auth forms — none of the app's forms have CSRF yet; consistent with project scope.
- Password reset, account lockout, rate limiting — not on the Spendly roadmap.
- Switching `/logout` to POST — out of scope per project conventions.
