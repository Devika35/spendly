# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Spendly** — a personal expense tracker (Flask + Jinja templates + SQLite) built as a step-by-step teaching project. Much of the app is intentionally unwritten: placeholder routes in `app.py` return strings like `"Add expense — coming in Step 7"`, and `database/db.py` contains only comments describing what Step 1 should add. When implementing a step, replace the matching placeholder rather than adding a parallel route.

Known step mapping (from code comments): Step 1 database layer (`database/db.py`), Step 3 `/logout`, Step 4 `/profile`, Step 7 `/expenses/add`, Step 8 `/expenses/<id>/edit`, Step 9 `/expenses/<id>/delete`. Steps 2, 5, 6 are not marked in code (likely register/login handling, dashboard/list, filters).

## Commands

Windows / PowerShell; Python 3.12 in a local `venv/`.

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1   # create venv + install requirements
.\venv\Scripts\Activate.ps1
python app.py                                          # dev server, debug on, http://localhost:5001
pytest                                                 # pytest + pytest-flask are installed; no tests exist yet
pytest path\to\test_file.py::test_name                 # single test
```

There is no linter or build step configured.

## Architecture

- `app.py` — single Flask app with all routes; no blueprints or app factory. Port is **5001**, not Flask's default 5000.
- `database/db.py` — planned API: `get_db()` (SQLite connection with `row_factory` set and foreign keys enabled), `init_db()` (`CREATE TABLE IF NOT EXISTS` for all tables), `seed_db()` (dev sample data). The DB file `expense_tracker.db` is gitignored.
- `templates/base.html` — shared layout (navbar, footer with Terms/Privacy links, Google Fonts DM Serif Display + DM Sans). Pages extend it and use the `title`, `head`, `content`, and `scripts` blocks. Links use `url_for('<endpoint>')`, so route function names matter.
- `templates/login.html` and `register.html` already `POST` to `/login` and `/register` (fields: `email`, `password`; register adds `name`), but those routes currently only accept GET — submitting the forms returns 405 until auth is implemented.
- Static assets: `static/css/style.css` is global; page-specific CSS/JS (e.g. `landing.css`, `landing.js`) is loaded only via that page's `head`/`scripts` blocks. Landing styles use a `home-hero-*` class prefix. `static/js/main.js` is an empty placeholder loaded on every page.
- Currency/copy is India-focused ("Track every rupee").

## Repo notes

- Commit messages use an area prefix, e.g. `landing: add privacy policy page and route`.
- `move-to-d.ps1` is a machine-maintenance script (moves dev tools from C: to D:) and is unrelated to the app; `file.md` is a saved Claude Code transcript, not documentation.
