# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Spendly** — a personal expense tracking web app (Indian Rupees). Built with Flask, Jinja2 templates, vanilla JS, and SQLite. Structured as a progressive implementation project with some routes already built and others as placeholders.

## Commands

```bash
# Activate virtual environment
source venv/Scripts/activate

# Run the app (starts on port 5001, debug mode)
python app.py

# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run a single test file
pytest tests/test_auth.py

# Run a single test by name
pytest -k "test_login"
```

## Project Structure

```
expense-tracker/
├── app.py                        # Entry point — all Flask routes (no blueprints)
├── requirements.txt              # Flask, werkzeug, pytest, pytest-flask
├── expense_tracker.db            # SQLite DB (created after init_db() is run)
│
├── database/
│   ├── __init__.py
│   └── db.py                     # STUB — implement get_db / init_db / seed_db here
│
├── templates/
│   ├── base.html                 # Shared layout: navbar, footer, block slots
│   ├── landing.html              # Marketing page (hero + features + CTA + video modal)
│   ├── login.html                # Auth form — renders {{ error }} if set
│   ├── register.html             # Auth form — renders {{ error }} if set
│   ├── terms.html                # Static legal page
│   └── privacy.html              # Static legal page
│
├── static/
│   ├── css/
│   │   ├── style.css             # Global design system (CSS vars, navbar, auth, footer)
│   │   └── landing.css           # Landing-only overrides (hero layout, modal, mockup)
│   └── js/
│       └── main.js               # Minimal — students extend this per step
│
└── venv/                         # Virtual environment (gitignored)
```

## Architecture

**Single-file Flask app** (`app.py`) — all routes live here, no blueprints. Server-side rendering via Jinja2 with `templates/base.html` as the shared layout (navbar, footer, block structure). All child templates use `{% extends "base.html" %}`.

**Database** (`database/db.py`) — stub file. Must implement:
- `get_db()` — SQLite connection with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- `init_db()` — creates tables with `CREATE TABLE IF NOT EXISTS`
- `seed_db()` — inserts sample rows for development

Database file will be `expense_tracker.db` at project root (not yet created).

**No build step** — static assets served directly from `static/css/` and `static/js/`. No bundler, no transpilation.

## Where things belong:
- New routes go in `app.py` only — no blueprints or separate route files
- Database logic goes in `database/db.py` only, never inline in routes
- New pages -> new '.html' file extending `base.html` in `templates/`
- Page specific styles -> new '.css' file, not inline styles or `<style>` tags

## Code Style
- Python: PEP8, snake_case for all variales and functions
- Templates: Jinja2 with 'url_for' for every internal link, no hardcoded paths
- Route functions: one responsibility only - fetch data, render template, done
- DB queries: always use parameterized queries to prevent SQL injection, never string formatting
- Error handling: use 'abort()' with appropriate HTTP status codes for error cases in routes

## Tech constraints

- Flask only - no FastAPI, Django, or other frameworks
- SQLite only - no PostgreSQL, MySQL, or ORMs like SQLAlchemy
- Vanilla JS only - no React, Vue, or other frontend frameworks
- No new pip packages without approval — stick to Flask and its dependencies for simplicity
- Python 3.10+ only - no older versions

## Route Status

| Route | Status |
|-------|--------|
| `/`, `/register`, `/login`, `/terms`, `/privacy` | Implemented (GET only) |
| `/logout` | Stub — Step 3 |
| `/profile` | Stub — Step 4 |
| `/expenses/add` | Stub — Step 7 |
| `/expenses/<id>/edit` | Stub — Step 8 |
| `/expenses/<id>/delete` | Stub — Step 9 |

The register and login forms POST to `/register` and `/login` but only GET handlers exist — submitting returns 405 until POST routes are added.

## Design System

CSS custom properties in `static/css/style.css`:
- Palette: deep green `--accent: #1a472a`, warm gold `--accent-2: #c17f24`, paper background `--paper: #f7f6f3`
- Fonts: `--font-display` (DM Serif Display), `--font-body` (DM Sans) via Google Fonts
- `static/css/landing.css` overrides hero layout for the landing page specifically

## Key Patterns

- Auth pages receive an `error` variable from the route; templates render `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}` inside the form card
- Landing page YouTube modal: iframe `src` is blank by default; JS copies from `data-src` on open and clears on close to stop playback
- `main.js` is intentionally minimal — students add JS here as features are built

## Warning and things to avoid
- Never use raw string returns for stub routes. Once a step is implemented - always render a template
- Never hardcode URLs in templates or JS - always use `url_for` in templates and generate URLs in routes for JS to consume
- Never put database logic directly in route functions - always delegate to functions in `database/db.py` for any DB interactions
- Avoid adding new dependencies or complex patterns that aren't necessary for the learning goals of the project.
- Never use JS frameworks or CSS frameworks - the goal is to build everything from scratch for learning purposes.
- database/db.py is currently empty - do not assume helpers exist there until you implement them. Always write raw SQL queries in that file and call them from routes.
- FK enforcement is manual - SQLite foreign keys are off by default. Make sure to enable them in `get_db()` with `PRAGMA foreign_keys = ON` to avoid silent data integrity issues.
- The app runs on port 5001 to avoid conflicts with other local services. Do not change the port.
