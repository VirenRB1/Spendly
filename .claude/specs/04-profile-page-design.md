# Spec: Profile Page Design

## Overview
Replace the `/profile` placeholder string with a real, designed profile page — the first authenticated landing surface in Spendly. This is the page a user lands on immediately after registration or login (both routes already redirect to `/profile`), so it sets the tone for the logged-in experience. Scope is intentionally narrow: render a polished, read-only profile view that displays the authenticated user's name, email, and account-created date, plus an empty-state placeholder for the expense list/summary panels that future steps (7–9) will fill in. No edit-profile functionality, no expense CRUD — this step is the visual and structural foundation that subsequent expense features will plug into.

## Depends on
- **Step 1 — Database setup**: `users` table with `id`, `name`, `email`, `created_at` columns.
- **Step 2 — Registration**: real users exist to display.
- **Step 3 — Login and Logout**: `session["user_id"]` is the source of truth for "who is logged in"; navbar already reflects auth state.

## Routes
- `GET /profile` — replaces the current stub. Reads `session["user_id"]`, fetches the user row, renders `profile.html`. If the session is missing or the user row no longer exists, redirect to `/login`. Access level: **logged-in**.

The route signature stays `@app.route("/profile")` — no method change, no URL change.

## Database changes
No database changes. The `users` table already has `id`, `name`, `email`, and `created_at`. One new helper function in `database/db.py` to fetch a user by id (mirrors the existing `get_user_by_email`).

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`. Two-section layout: a profile header card (avatar circle with first initial, name, email, "Member since {{ date }}") and a content area with placeholder cards for "Recent expenses" and "This month at a glance" that will be populated in later steps. Empty-state copy makes it clear the data is coming, not broken.
- **Modify:** none.

## Files to change
- `app.py` — replace the `/profile` stub: read `session.get("user_id")`, redirect to `login` if missing, fetch the user via the new helper, redirect to `login` if the row is gone, render `profile.html` with the user row. Add `get_user_by_id` to the import line from `database.db`.
- `database/db.py` — add `get_user_by_id(user_id)` returning a `sqlite3.Row` with `id`, `name`, `email`, `created_at` (or `None` if not found). Parameterised query.
- `static/css/style.css` — add a `.profile-*` block for the profile page (header card, avatar circle, info column, placeholder cards, grid). Reuse existing CSS variables (`--accent`, `--accent-2`, `--paper`, `--font-display`, `--font-body`).

## Files to create
- `templates/profile.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `database/db.py` helpers.
- Parameterised queries only — `get_user_by_id` must use `WHERE id = ?`, never string formatting.
- Passwords hashed with werkzeug — N/A here, but never expose `password_hash` to the template; the new helper must not select that column.
- All templates extend `base.html`.
- Use CSS variables — never hardcode hex values. Pull all colours from the variables already defined in `static/css/style.css`. New shades (e.g. a translucent overlay) should be expressed as `rgb()`/`rgba()` of an existing variable via `color-mix()` or by adding one new variable to the `:root` block — do not sprinkle raw hex into `.profile-*` rules.
- Profile-specific styles go in `static/css/style.css` under a clearly labelled `/* Profile page */` section. Do **not** create `static/css/profile.css` — `landing.css` is a one-off override; `style.css` is the home for app-wide page styles, and the profile page is part of the core app surface.
- No inline `style="..."` attributes and no `<style>` tags in `profile.html`.
- All internal links use `url_for(...)` — no hardcoded paths.
- The route function does one thing: auth-check, fetch user, render. No business logic, no inline SQL.
- Auth guard: if `session.get("user_id")` is falsy **or** `get_user_by_id(...)` returns `None`, redirect to `url_for("login")`. Do not 401/403 — this is a user-facing app, not an API.
- Date display: `created_at` is stored as `datetime('now')` (ISO-ish text). Format it for humans in the template using a Jinja filter or pass a pre-formatted string from the route — pick one and stick to it. Recommended: format in the route (`datetime.fromisoformat(row["created_at"]).strftime("%B %Y")`) so the template stays logic-free.
- Avatar: a CSS circle with the user's first initial uppercased — no image upload, no gravatar. Pure CSS + one Jinja expression (`{{ user.name[0]|upper }}`).
- Placeholder cards for "Recent expenses" and "This month at a glance" must include short empty-state copy (e.g. "No expenses yet — add your first one to see it here.") — do **not** leave them blank or use lorem ipsum. They must visually match the rest of the page so future steps only need to swap content, not restyle.
- Currency: any monetary placeholder shown on the page uses `₹` (INR) — never `$`.
- Responsive: the profile header should stack vertically below ~640px (avatar above text). Use a media query in the new CSS block, not JS.

## Definition of done
- [ ] Visiting `GET /profile` while logged in renders `profile.html` (200) showing the authenticated user's name, email, and a human-readable "Member since" date.
- [ ] Visiting `GET /profile` while logged out redirects (302) to `/login`.
- [ ] Visiting `GET /profile` with a `session["user_id"]` that no longer exists in the `users` table redirects (302) to `/login` (does not 500).
- [ ] The avatar circle shows the uppercased first letter of the user's name.
- [ ] The page extends `base.html` — the existing navbar (logged-in variant: `Profile` + `Logout`) and footer are present.
- [ ] No raw hex codes appear in the new `.profile-*` CSS rules — every colour resolves to a CSS variable.
- [ ] `templates/profile.html` contains no inline `style="..."` attributes and no `<style>` tags.
- [ ] `app.py` contains no inline SQL for the profile route — it calls `get_user_by_id` from `database/db.py`.
- [ ] `get_user_by_id` is a parameterised query and does **not** select `password_hash`.
- [ ] The two placeholder cards ("Recent expenses", "This month at a glance") render with empty-state copy and match the visual style of the profile header card.
- [ ] At viewport widths ≤640px the profile header stacks vertically (avatar above name/email) without horizontal scroll.
- [ ] Any monetary values shown on the page use the `₹` symbol — no `$` anywhere on `/profile`.
- [ ] App starts on port 5001 with no errors and the seeded demo user (`demo@spendly.com` / `demo123`) can log in and see their profile.
