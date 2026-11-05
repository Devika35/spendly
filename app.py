import calendar
import os
import re
import sqlite3
from datetime import date, datetime

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MIN_PASSWORD_LENGTH = 8

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-key")

with app.app_context():
    init_db()
    seed_db()


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
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

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


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
