# Spec: Login and Logout

## Overview
Implement session-based authentication so registered users can sign in and out of Spendly. This step upgrades the stub `GET /login` route to verify submitted credentials and start a Flask session, and replaces the `/logout` placeholder with a route that ends it. The navbar also starts reflecting whether the visitor is signed in. Registration already redirects to `/login`, so this completes the account flow and gives later steps, starting with the Step 4 profile page, a signed-in user to work with.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`, seeded demo user)
- Step 02 — Registration (`get_user_by_email()`, hashed passwords, redirect to `/login`)

## Routes
- `GET /login` — render the sign-in form; redirect to `/` if already signed in — public (already exists as stub, upgrade it)
- `POST /login` — verify credentials, start the session, redirect to `/` — public
- `GET /logout` — clear the session and redirect to `/` — public; safe to call when signed out (already exists as placeholder, replace it)
- `GET /register`, `POST /register` — redirect to `/` if already signed in, otherwise unchanged — public (already exists, add the redirect)

## Database changes
No database changes. The existing `users` table (id, name, email, password_hash, created_at) and `get_user_by_email(email)` in `database/db.py` already support login.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html`
    - Keep the previously entered email when the form is re-shown with an error
    - Never re-populate the password field
    - The existing `{% if error %}` block displays login errors
    - Use `url_for('login')` for the form action instead of the hardcoded `/login`
  - `templates/base.html`
    - Signed in: show the user's name and a "Sign out" link to `url_for('logout')`
    - Signed out: keep the existing "Sign in" and "Get started" links

## Files to change
- `app.py` — set `app.secret_key`, upgrade `/login` to handle GET and POST, replace the `/logout` placeholder, redirect signed-in users away from `/register`
- `templates/login.html` — retain the email on error, use `url_for` for the form action
- `templates/base.html` — make the navbar depend on sign-in state

## Files to create
None

## New dependencies
No new dependencies. Sessions are built into Flask, and `check_password_hash` comes from werkzeug, which is installed with Flask.

## Rules for implementation
- Follow all rules in CLAUDE.md
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with `check_password_hash`, never compare plain text
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Replace the existing `/login` and `/logout` routes rather than adding parallel ones
- Read the secret key from the `SECRET_KEY` environment variable, with a clearly named development-only fallback
- Normalise the submitted email the same way as registration: trimmed and lowercase
- Do not trim the password
- Do not apply `MIN_PASSWORD_LENGTH` at login — the seeded demo user's password, `demo123`, is only 7 characters
- Show the same "Invalid email or password" error for an unknown email and a wrong password, so the form does not reveal which emails are registered
- Show "All fields are required" if either field is empty, without querying the database
- Call `session.clear()` before setting session values on login
- Store only `user_id` and `user_name` in the session — never the password hash
- Do not build the profile page, or add route protection for pages that are still placeholders

## Definition of done
- [ ] Visiting `/login` shows the sign-in form
- [ ] Signing in with `demo@spendly.com` / `demo123` redirects to `/`
- [ ] An account created through `/register` can sign in with its email and password
- [ ] The email is matched regardless of case or surrounding spaces
- [ ] A wrong password shows "Invalid email or password" and keeps the email in the form
- [ ] An unknown email shows the same "Invalid email or password" message
- [ ] Submitting an empty field shows "All fields are required"
- [ ] After signing in, the navbar shows the user's name and "Sign out", not "Sign in" or "Get started"
- [ ] Visiting `/login` while signed in redirects to `/`
- [ ] Visiting or submitting `/register` while signed in redirects to `/` and creates no user
- [ ] Clicking "Sign out" redirects to `/` and the navbar shows "Sign in" and "Get started" again
- [ ] Visiting `/logout` while signed out redirects to `/` without an error
- [ ] The session persists across page loads until the user signs out
