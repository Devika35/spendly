# Spec: Edit Expense

## Overview
Step 8 lets a logged-in user correct an expense they've already recorded. The
`/expenses/<int:id>/edit` route currently returns the placeholder string
"Edit expense — coming in Step 8". This step replaces it with a GET + POST
handler. GET shows a form pre-filled with the expense's current values. POST
validates the submitted values with the same rules as Add Expense, updates the
row, and redirects to the profile page. Users can only see and change their own
expenses. Any other id returns 404, so the app never reveals whether another
user's expense exists. Each row in the profile transaction table gets an "Edit"
link, which is how users reach this form.

## Depends on
- Step 1: Database setup (`expenses` table with `id`, `user_id`, `amount`, `category`, `date`, `description`)
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Steps 4–6: Profile page with the transaction table (where the Edit links go)
- Step 7: Add Expense (`_validate_expense_form`, `CATEGORIES`, `MAX_DESCRIPTION_LENGTH`, CSRF token helper, form styling)

## Routes
- `GET /expenses/<int:expense_id>/edit`: render the edit form pre-filled with the expense's current values. Logged-in only.
- `POST /expenses/<int:expense_id>/edit`: validate, update the expense, and redirect to `/profile`. Logged-in only.

Replace the existing placeholder route; don't add a second one. Keep the
endpoint name `edit_expense`. The URL parameter may be renamed from `id` to
`expense_id` so it no longer shadows the builtin `id`. If you rename it, every
`url_for('edit_expense', ...)` call must use the new name.

## Database changes
No database changes. The `expenses` table already has every column this
feature needs.

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html`
  - Same layout and classes as `add_expense.html` (`auth-section`, `auth-card`, `form-group`, `form-input`, `btn-submit`, `form-cancel`)
  - Title "Edit expense — Spendly", heading "Edit expense"
  - `<form method="POST" action="{{ url_for('edit_expense', expense_id=expense_id) }}">`
  - Hidden `csrf_token` field
  - Fields `amount`, `category` (`<select>` of `CATEGORIES`), `date`, and `description`, with the same attributes and limits as the add form
  - Values come from `form`: the stored expense on GET, or the submitted values when a POST fails validation
  - Shows `error` in `.auth-error` when set
  - Submit button "Save Changes" and a "Cancel" link back to `/profile`
- **Modify:** `templates/profile.html`
  - Add an actions column to the transaction table. The header cell may be empty or visually hidden, but must be accessible.
  - Each row gets an "Edit" link to `url_for('edit_expense', expense_id=t.id)`
  - Change the empty-state `colspan` from 4 to 5

## Files to change
- `app.py`
  - Replace the `edit_expense` placeholder with a GET + POST handler decorated with `@login_required`
  - GET: load the expense with `get_expense_by_id(expense_id, session["user_id"])`, call `abort(404)` if it's `None`, then render `edit_expense.html` with `form` built from the row
  - POST: first check the expense exists and belongs to the user (otherwise 404), then run `_validate_expense_form(request.form)`. On error, re-render with the submitted values and the error. On success, call `update_expense(expense_id, session["user_id"], **values)` and redirect to `url_for("profile")`.
  - Import `get_expense_by_id` and `update_expense` from `database.queries`
  - Update the `_validate_expense_form` docstring to say its values also feed `update_expense()`
- `database/queries.py`
  - Add `get_expense_by_id(expense_id, user_id)`. It returns a dict (`id`, `amount`, `category`, `date`, `description`) or `None`, with the SQL filtered by both `id = ?` and `user_id = ?`.
  - Add `update_expense(expense_id, user_id, amount, category, expense_date, description)`. It runs `UPDATE ... WHERE id = ? AND user_id = ?` and returns `cursor.rowcount`.
  - Add `id` to the SELECT and the returned dicts in `get_recent_transactions`
- `templates/profile.html`: add the Edit link column (see Templates)
- `static/css/profile.css`: add styles for the Edit link and actions column, using CSS variables only

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs. Use raw `sqlite3` through `get_db()` only.
- Use parameterised queries only. Never format values into SQL strings.
- Passwords hashed with werkzeug. This feature doesn't touch passwords; leave the auth code as it is.
- Use CSS variables. Never hardcode hex values.
- All templates extend `base.html`.
- No inline styles.
- Currency always displays as ₹.
- Both GET and POST redirect to `/login` when logged out (`@login_required`).
- **Ownership:** every read and write is scoped by `user_id = session["user_id"]` in SQL. Another user's expense, or an id that doesn't exist, gets a 404 on both GET and POST. Never use a 403, because it would reveal that the expense exists.
- Reuse `_validate_expense_form` for POST validation, with the same rules and error messages as Add Expense. Don't duplicate the checks.
- CSRF is enforced by the existing `before_request` hook. The form must include the hidden `csrf_token` field.
- After a successful update, redirect to the profile page instead of rendering the form again.
- Don't implement delete here. That's Step 9; leave its placeholder alone.

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Each row in the profile transaction table has an "Edit" link that opens that expense's edit form
- [ ] The edit form shows the expense's current amount, category, date and description
- [ ] Changing any field and clicking "Save Changes" redirects to `/profile`, and the transaction list and summary stats show the new values
- [ ] Clearing the description and saving stores no description (the table shows "—")
- [ ] Submitting a blank or zero amount, an invalid category, or an invalid date re-renders the form with an error and keeps the values you entered. The stored expense is unchanged.
- [ ] Visiting `/expenses/99999/edit` (an id that doesn't exist) returns 404
- [ ] Logged in as a second user, visiting the demo user's expense edit URL returns 404, and POSTing to it returns 404 and leaves the expense unchanged
- [ ] A POST without a valid CSRF token returns 400
- [ ] "Cancel" goes back to `/profile` without changing anything
- [ ] The Add Expense flow and the profile date filters still work as before
