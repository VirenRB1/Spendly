# Plan: Step 02 — Registration

## Context
Step 1 stood up the `users` table and a `Demo User` seed but left `/register` as a GET-only route that just renders `register.html`. The form already POSTs to `/register` and the template already renders an `{{ error }}` block, so submitting the form today returns a 405. This step wires up POST handling: server-side validation, werkzeug password hashing, and an insert into `users` via a thin DB helper. Registration must succeed before Step 3 (login) can authenticate anyone other than the seeded demo user, so this is the unblocker for the auth chain.

## Files to modify
- `app.py` — convert `register()` into a GET/POST view; add request-handling imports.
- `database/db.py` — add `create_user()` and `get_user_by_email()` helpers.

## Files to create
None.

---

## Change 1 — `database/db.py`: add user helpers

Add two functions below the existing `seed_db()`. Both must use parameterised queries and the existing `get_db()` connection helper. `werkzeug.security.generate_password_hash` is already imported at the top of the file but is **not** called here — hashing happens in the route so the helper stays a pure DB function.

```python
def get_user_by_email(email):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, password_hash FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return row


def create_user(name, email, password_hash):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id
```

Notes:
- `get_user_by_email` returns a `sqlite3.Row` or `None` (row factory is set in `get_db()`).
- `create_user` returns the new `id` so a future Step 3 can log the user in directly if desired — for now it is unused but cheap to surface.
- Caller is responsible for hashing and lowercasing email before passing in.

## Change 2 — `app.py`: GET/POST register view

Update the Flask import line to include the helpers used by the new view:

```python
from flask import Flask, render_template, request, redirect, url_for
```

Update the DB import to include the new helpers:

```python
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
```

Replace the existing `register()` function with a single view that handles both methods:

```python
@app.route("/register", methods=["GET", "POST"])
def register():
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
```

Add the two new top-level imports needed by the view:

```python
import sqlite3
from werkzeug.security import generate_password_hash
```

Notes:
- Email is `.strip().lower()` once, then used for both the lookup and the insert — this is what makes the duplicate check case-insensitive.
- Password is **not** stripped — leading/trailing spaces are valid in passwords.
- The `IntegrityError` catch is the race-condition backstop required by the spec; the explicit pre-check gives a friendlier UX in the common case.
- `name` and `email` are passed back to the template on every error path so the user does not retype. The template already references `{{ error }}`; passing additional kwargs is harmless because the existing template ignores unknown variables. **No template change required.**

## Change 3 — Verify no template change is needed

`templates/register.html` already:
- POSTs to `/register` (line 20).
- Renders `{{ error }}` inside `auth-error` (lines 16-18).
- Extends `base.html` (line 1).

The optional "preserve typed values" enhancement is a nice-to-have that would require adding `value="{{ name or '' }}"` and `value="{{ email or '' }}"` on the inputs. This is in scope per the spec ("only do this if it does not require restructuring") and is a 2-line change. **Recommend including it.** Edit lines 23-25 and 29-31:

```html
<input type="text" id="name" name="name"
       class="form-input" placeholder="Nitish Kumar"
       value="{{ name or '' }}"
       required autofocus>
```

```html
<input type="email" id="email" name="email"
       class="form-input" placeholder="nitish@example.com"
       value="{{ email or '' }}"
       required>
```

Do **not** preserve the password field — never echo passwords back into HTML.

---

## Verification

Run the app and exercise each path manually. The seeded `demo@spendly.com` from Step 1 is the duplicate-email fixture.

```bash
source venv/Scripts/activate
python app.py
```

| Case | Steps | Expected |
| --- | --- | --- |
| Happy path | Submit name=`Test User`, email=`Test@Example.com`, password=`password123` | 302 redirect to `/login`; `sqlite3 expense_tracker.db "SELECT email, password_hash FROM users WHERE email='test@example.com';"` returns one row, hash starts with `pbkdf2:` or `scrypt:` |
| Email lowercased | Same as above | Stored email is `test@example.com`, not `Test@Example.com` |
| Missing field | Submit with empty name (disable HTML5 via DevTools) | 200, error "Please fill in every field.", no new row |
| Short password | Submit password=`short` | 200, error "Password must be at least 8 characters.", no new row |
| Duplicate email (exact) | Submit email=`demo@spendly.com` | 200, error "An account with that email already exists.", no new row |
| Duplicate email (different case) | Submit email=`DEMO@spendly.com` | 200, same duplicate error, no new row |
| GET regression | Visit `/register` directly | Empty form renders, no error block |
| Persisted form values | Trigger any error | `name` and `email` fields are pre-filled; password field is empty |

Verify row count between cases: `sqlite3 expense_tracker.db "SELECT COUNT(*) FROM users;"` should only increment on the happy path.

## Out of scope
- Login POST handler (Step 3).
- Sessions / auto-login on register (Step 3).
- Email format validation beyond what `<input type="email">` already enforces.
- Password complexity rules beyond the 8-character minimum.
- Flash messages / redirect-to-login-with-banner — out of scope until sessions exist.
