# Spec: Registration

## Overview
Implement user registration so new visitors can create a Spendly account. This step upgrades the existing stub `GET /register` route into a fully functional form that accepts a POST, validates input, hashes the password, and inserts a new row into the `users` table. On success the user is shown with a success message and redirected to the login page. This is the entry point for all authenticated features that follow.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`)

## Routes
- `GET /register` — render registration form — public (already exists as stub, upgrade it)
- `POST /register` — process registration form, insert user, redirect to `/login` — public

## Database changes
No new tables or columns. The existing `users` table (id, name, email, password_hash, created_at) already supports registration.

Add one helper function in `database/db.py`:
- `create_user(name, email, password)` — hashes the password with werkzeug's `generate_password_hash` and inserts the user. Returns the new user id.
- `get_user_by_email(email)` — returns the user row or `None`. Used to check for duplicate emails.

## Templates
- Create: none
- Modify: `templates/register.html`
  - Form uses `method="POST"` and `action="/register"`
  - Fields: name, email, password, confirm password
  - Show validation error messages above the form
  - Keep previously entered name and email if the form is re-shown with errors

## Files to change
- `app.py` — upgrade the `/register` route to handle GET and POST
- `database/db.py` — add `create_user()` and `get_user_by_email()`
- `templates/register.html` — wire up the form and error display

## Files to create
- None

## New dependencies
- None (werkzeug is already installed with Flask)

## Rules for implementation
- Follow all rules in CLAUDE.md
- Use parameterized SQL queries only
- Hash passwords with werkzeug's `generate_password_hash` — never store plain text
- Validate on the server, not only in the browser:
  - All fields are required
  - Email must be in a valid format
  - Email must not already exist (case-insensitive)
  - Password must be at least 8 characters
  - Password and confirm password must match
- Store emails in lowercase and trimmed
- Keep business logic out of templates
- Reuse existing styles from static/ — no new CSS frameworks
- Do not implement login, logout or sessions in this step

## Definition of done
- [ ] Visiting `/register` shows the registration form
- [ ] Submitting valid details creates a new row in `users` with a hashed password
- [ ] After successful registration, the user is redirected to `/login`
- [ ] Submitting an email that already exists shows "Email already registered"
- [ ] Empty fields show an error and no user is created
- [ ] Mismatched passwords show an error and no user is created
- [ ] A password shorter than 8 characters shows an error
- [ ]