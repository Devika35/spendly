# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user permanently remove an expense they recorded by
mistake. The `/expenses/<int:id>/delete` route currently returns the
placeholder string "Delete expense — coming in Step 9" and accepts GET, which
would make deletion a state-changing GET if it were implemented as-is. This step
replaces it with a two-step flow: GET shows a confirmation page summarising the
expense, and POST (with the CSRF token) deletes it and redirects to the profile
page. Users can only see and delete their own expenses. Any other id returns
404, so the app never reveals whether another user's expense exists. Each row in
the profile transaction table gets a "Delete" link next to the existing "Edit"
link, completing the add / edit / delete set of expense actions.

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 3: Login / Logout (`session["user_id"]`, `login_required`)
- Steps 4–6: Profile page with the transaction table and actions column
- Step 7: Add Expense (CSRF token helper and `before_request` check, auth-card form styling)
- Step 8: Edit Expense (`get_expense_by_id`, the actions column and `.profile-edit-link` styling)

## Routes
- `GET /expenses/<int:expense_id>/delete`: render a confirmation page showing the expense's date, description, category and amount. Logged-in only.
- `POST /expenses/<int:expense_id>/delete`: delete the expense and redirect to `/profile`. Logged-in only.

Replace the existing placeholder route (and remove it from the "Placeholder
routes" section); don't add a second one. Keep the endpoint name
`delete_expense`. Rename the URL parameter from `id` to `expense_id` to match
`edit_expense` and stop shadowing the builtin `id`. Every
`url_for('delete_expense', ...)` call must use `expense_id=`.

## Database changes
No database changes. Deleting a row from `expenses` needs no new columns, and
no other table references `expenses`, so there are no foreign-key cascades to
handle.

## Templates
- **Create:** `templates/delete_expense.html`
  - Extends `base.html`
  - Same layout and classes as `edit_expense.html` (`auth-section`, `auth-container`, `auth-header`, `auth-card`, `btn-submit`, `form-cancel`)
  - Title "Delete expense — Spendly", heading "Delete expense", subtitle warning that this can't be undone
  - A summary of the expense: date (formatted `%d %b %Y`), description (or "—"), category badge, and amount as `₹{:,.2f}`
  - `<form method="POST" action="{{ url_for('delete_expense', expense_id=expense.id) }}">` with a hidden `csrf_token` field and no other inputs
  - Submit button "Delete Expense", styled as a destructive action (a modifier class such as `btn-danger` on top of `btn-submit`, using `--danger` / `--danger-light`)
  - A "Cancel" link back to `/profile`
- **Modify:** `templates/profile.html`
  - In each row's `profile-actions` cell, add a "Delete" link to `url_for('delete_expense', expense_id=t.id)` after the Edit link
  - Give it an `aria-label` in the same style as the Edit link, e.g. `Delete {{ t.description or t.category }} on {{ t.date }}`
  - The header cell and empty-state `colspan="5"` stay as they are

## Files to change
- `app.py`
  - Replace the `delete_expense` placeholder with a GET + POST handler decorated with `@login_required`, placed after `edit_expense` in the Routes section
  - Both methods: load the expense with `get_expense_by_id(expense_id, session["user_id"])` and `abort(404)` if it's `None`
  - GET: format the date for display and render `delete_expense.html` with `expense`
  - POST: call `delete_expense_by_id(expense_id, session["user_id"])` (or a similarly named query helper that doesn't clash with the view function name). If it returns 0 (deleted between the lookup and the delete), `abort(404)`. Otherwise redirect to `url_for("profile")`.
  - Import the new delete helper from `database.queries`
  - Remove the now-empty "Placeholder routes" section header
- `database/queries.py`
  - Add `delete_expense_by_id(expense_id, user_id)` in the WRITES section. It runs `DELETE FROM expenses WHERE id = ? AND user_id = ?`, commits, and returns `cursor.rowcount`.
  - Update the module docstring to mention deleting
- `templates/profile.html`: add the Delete link (see Templates)
- `static/css/profile.css`: style `.profile-delete-link` alongside `.profile-edit-link`, using `--danger` for the hover / focus colour and spacing the two links apart
- `static/css/style.css`: add the destructive button modifier (e.g. `.btn-danger`) and any styles for the confirmation summary, using CSS variables only

## Files to create
- `templates/delete_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs. Use raw `sqlite3` through `get_db()` only.
- Use parameterised queries only. Never format values into SQL strings.
- Passwords hashed with werkzeug. This feature doesn't touch passwords; leave the auth code as it is.
- Use CSS variables. Never hardcode hex values.
- All templates extend `base.html`.
- No inline styles and no JavaScript `confirm()` — confirmation happens on the server-rendered page.
- Currency always displays as ₹.
- **Never delete on GET.** GET only renders the confirmation page; the row is removed only by a POST that passes the existing CSRF check.
- Both GET and POST redirect to `/login` when logged out (`@login_required`).
- **Ownership:** the lookup and the `DELETE` are both scoped by `user_id = session["user_id"]` in SQL. Another user's expense, or an id that doesn't exist, gets a 404 on both GET and POST. Never use a 403, because it would reveal that the expense exists.
- CSRF is enforced by the existing `before_request` hook. The form must include the hidden `csrf_token` field.
- After a successful delete, redirect to the profile page instead of rendering a page.
- Don't change the add or edit flows beyond adding the Delete link next to Edit.

## Definition of done
- [ ] Visiting `/expenses/<id>/delete` while logged out redirects to `/login`; POSTing to it while logged out also redirects to `/login` and deletes nothing
- [ ] Each row in the profile transaction table has a "Delete" link next to "Edit"
- [ ] Clicking "Delete" opens a confirmation page showing that expense's date, description, category and amount in ₹
- [ ] Visiting the confirmation page (GET) does not delete the expense — reloading `/profile` still shows it
- [ ] Clicking "Delete Expense" redirects to `/profile`; the expense is gone from the transaction list, and total spent, transaction count, top category and the category breakdown all update
- [ ] "Cancel" on the confirmation page returns to `/profile` with the expense still present
- [ ] Deleting the user's last expense in a date range shows the "No expenses yet" empty states for that range
- [ ] Visiting or POSTing to `/expenses/99999/delete` (an id that doesn't exist) returns 404
- [ ] Logged in as a second user, visiting the demo user's expense delete URL returns 404, and POSTing to it returns 404 and leaves the expense in place
- [ ] POSTing to a delete URL that was already deleted returns 404
- [ ] A POST without a valid CSRF token returns 400 and deletes nothing
- [ ] The Add Expense and Edit Expense flows and the profile date filters still work as before
