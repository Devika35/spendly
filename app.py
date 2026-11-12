import calendar
import math
import os
import re
import secrets
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database.db import (
    CATEGORIES,
    create_user,
    get_db,
    get_user_by_email,
    init_db,
    seed_db,
)
from database.queries import (
    delete_expense_by_id,
    get_category_breakdown,
    get_expense_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    insert_expense,
    update_expense,
)

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MIN_PASSWORD_LENGTH = 8
MAX_DESCRIPTION_LENGTH = 200
MAX_AMOUNT = 10_000_000

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-key")
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    # Tests may switch this off to post forms without a token
    CSRF_ENABLED=True,
)

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# CSRF and auth helpers                                               #
# ------------------------------------------------------------------ #

def _csrf_token():
    """Return this session's CSRF token, creating it on first use."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = _csrf_token


@app.before_request
def _check_csrf():
    """Reject any POST whose form token doesn't match the session's."""
    if request.method != "POST" or not app.config["CSRF_ENABLED"]:
        return
    sent = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(sent, expected):
        abort(400)


def login_required(view):
    """Redirect to the login page unless a user is in the session."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------ #
# Date filter helpers                                                 #
# ------------------------------------------------------------------ #

def _parse_iso_date(value):
    """Return value as a canonical 'YYYY-MM-DD' string, or None if invalid.

    strptime also accepts non-padded input like '2026-1-5'; re-serialising
    via isoformat() normalises it so ISO strings compare correctly.
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _resolve_date_range(args):
    """Return the validated (date_from, date_to) from query args.

    Both bounds are required; a missing or malformed bound means no filter.
    A reversed range flashes an error and also means no filter.
    """
    date_from = _parse_iso_date(args.get("date_from"))
    date_to = _parse_iso_date(args.get("date_to"))
    if date_from is None or date_to is None:
        return None, None
    # Canonical ISO date strings sort chronologically
    if date_from > date_to:
        flash("Start date must be before end date.")
        return None, None
    return date_from, date_to


def _months_ago(d, n):
    """Return the date n months before d, clamping the day to the month's end."""
    month_index = d.year * 12 + (d.month - 1) - n
    year, month = divmod(month_index, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _build_presets(today):
    """Quick-select ranges for the profile filter bar, as ISO strings.

    Each preset has a stable `key` (used for the active state), a display
    `label`, and its date bounds. "All Time" has no bounds.
    """
    today_iso = today.isoformat()
    starts = [
        ("this_month", "This Month", today.replace(day=1)),
        ("last_3_months", "Last 3 Months", _months_ago(today, 3)),
        ("last_6_months", "Last 6 Months", _months_ago(today, 6)),
    ]
    presets = [
        {"key": key, "label": label,
         "date_from": start.isoformat(), "date_to": today_iso}
        for key, label, start in starts
    ]
    presets.append(
        {"key": "all_time", "label": "All Time",
         "date_from": None, "date_to": None}
    )
    return presets


# ------------------------------------------------------------------ #
# Expense form helpers                                                #
# ------------------------------------------------------------------ #

def _clean_description(value):
    """Collapse whitespace and drop control characters; '' becomes None."""
    text = " ".join(value.split())
    text = "".join(ch for ch in text if ch.isprintable())
    return text or None


def _validate_expense_form(form):
    """Validate submitted expense fields.

    Returns (values, error). On success error is None and values is a dict of
    insert_expense() / update_expense() keyword arguments (amount, category,
    expense_date, description) ready to store. On failure
    values is None and error is a user-facing message.
    """
    amount_raw = form.get("amount", "").strip()
    category = form.get("category", "").strip()
    date_raw = form.get("date", "").strip()
    description = _clean_description(form.get("description", ""))

    if not (amount_raw and category and date_raw):
        return None, "Amount, category and date are required"

    try:
        amount = float(amount_raw)
    except ValueError:
        return None, "Enter a valid amount greater than 0"
    # float() also accepts "inf" and "nan", so check the value is finite
    if not math.isfinite(amount) or amount <= 0:
        return None, "Enter a valid amount greater than 0"
    if amount > MAX_AMOUNT:
        return None, "Amount is too large"

    if category not in CATEGORIES:
        return None, "Choose a valid category"

    expense_date = _parse_iso_date(date_raw)
    if expense_date is None:
        return None, "Enter a valid date"

    if description and len(description) > MAX_DESCRIPTION_LENGTH:
        return None, (
            f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer"
        )

    return {
        "amount": round(amount, 2),
        "category": category,
        "expense_date": expense_date,
        "description": description,
    }, None


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not (name and email and password and confirm_password):
        error = "All fields are required"
    elif not EMAIL_PATTERN.fullmatch(email):
        error = "Enter a valid email address"
    elif len(password) < MIN_PASSWORD_LENGTH:
        error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    elif password != confirm_password:
        error = "Passwords do not match"
    elif get_user_by_email(email):
        error = "Email already registered"
    else:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            # Another request registered this email after the check above
            error = "Email already registered"
        else:
            return redirect(url_for("login"))

    return render_template("register.html", error=error, name=name, email=email)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not (email and password):
        error = "All fields are required"
    else:
        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("profile"))
        error = "Invalid email or password"

    return render_template("login.html", error=error, email=email)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
@login_required
def profile():
    user = get_user_by_id(session["user_id"])
    if user is None:
        # Stale session, e.g. the DB was reset while the user was logged in
        session.clear()
        return redirect(url_for("login"))
    user["initials"] = "".join(w[0] for w in user["name"].split()[:2]).upper()

    date_from, date_to = _resolve_date_range(request.args)

    transactions = get_recent_transactions(
        session["user_id"], date_from=date_from, date_to=date_to
    )
    for t in transactions:
        t["date"] = datetime.strptime(t["date"], "%Y-%m-%d").strftime("%d %b %Y")

    stats = get_summary_stats(
        session["user_id"], date_from=date_from, date_to=date_to
    )
    categories = get_category_breakdown(
        session["user_id"], date_from=date_from, date_to=date_to
    )

    presets = _build_presets(date.today())
    # Key of the matching preset, or None for a custom range
    active_preset = next(
        (p["key"] for p in presets
         if (p["date_from"], p["date_to"]) == (date_from, date_to)),
        None,
    )

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        presets=presets,
        active_preset=active_preset,
        date_from=date_from,
        date_to=date_to,
    )


@app.route("/analytics")
@login_required
def analytics():
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    error = None
    if request.method == "POST":
        form = request.form
        values, error = _validate_expense_form(form)
        if error is None:
            insert_expense(session["user_id"], **values)
            return redirect(url_for("profile"))
    else:
        form = {"date": date.today().isoformat()}

    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        form=form,
        error=error,
        max_description_length=MAX_DESCRIPTION_LENGTH,
    )


@app.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    user_id = session["user_id"]
    # Scoped by user_id: a missing expense and another user's expense both
    # 404, so the response never reveals whether the id exists
    expense = get_expense_by_id(expense_id, user_id)
    if expense is None:
        abort(404)

    error = None
    if request.method == "POST":
        form = request.form
        values, error = _validate_expense_form(form)
        if error is None:
            if update_expense(expense_id, user_id, **values) == 0:
                # Deleted between the lookup above and this update
                abort(404)
            return redirect(url_for("profile"))
    else:
        form = {
            "amount": f"{expense['amount']:.2f}",
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        }

    return render_template(
        "edit_expense.html",
        expense_id=expense_id,
        categories=CATEGORIES,
        form=form,
        error=error,
        max_description_length=MAX_DESCRIPTION_LENGTH,
    )


@app.route("/expenses/<int:expense_id>/delete", methods=["GET", "POST"])
@login_required
def delete_expense(expense_id):
    user_id = session["user_id"]
    # Scoped by user_id, like edit_expense: missing and foreign ids both 404
    expense = get_expense_by_id(expense_id, user_id)
    if expense is None:
        abort(404)

    # GET only confirms; the row is removed by a CSRF-checked POST
    if request.method == "POST":
        if delete_expense_by_id(expense_id, user_id) == 0:
            # Deleted between the lookup above and this delete
            abort(404)
        return redirect(url_for("profile"))

    expense["display_date"] = datetime.strptime(
        expense["date"], "%Y-%m-%d"
    ).strftime("%d %b %Y")
    return render_template("delete_expense.html", expense=expense)


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


if __name__ == "__main__":
    app.run(debug=True, port=5001)
