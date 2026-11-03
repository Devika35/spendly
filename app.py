import os
import re
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MIN_PASSWORD_LENGTH = 8

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-key")

with app.app_context():
    init_db()
    seed_db()


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

    # Hardcoded sample data — real queries arrive in Step 5
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "January 2026",
    }
    stats = {"total": 5149.50, "count": 8, "top_category": "Bills"}
    transactions = [
        {"date": "25 Oct 2026", "description": None, "category": "Other", "amount": 150.00},
        {"date": "20 Oct 2026", "description": "Dinner with friends", "category": "Food", "amount": 280.00},
        {"date": "15 Oct 2026", "description": "New kurta", "category": "Shopping", "amount": 1299.00},
        {"date": "12 Oct 2026", "description": "Movie tickets", "category": "Entertainment", "amount": 600.00},
        {"date": "08 Oct 2026", "description": "Pharmacy", "category": "Health", "amount": 320.00},
        {"date": "05 Oct 2026", "description": "Electricity bill", "category": "Bills", "amount": 1850.50},
        {"date": "03 Oct 2026", "description": "Metro card recharge", "category": "Transport", "amount": 200.00},
        {"date": "01 Oct 2026", "description": "Weekly groceries", "category": "Food", "amount": 450.00},
    ]
    categories = [
        {"name": "Bills", "total": 1850.50, "percent": 36},
        {"name": "Shopping", "total": 1299.00, "percent": 25},
        {"name": "Food", "total": 730.00, "percent": 14},
        {"name": "Entertainment", "total": 600.00, "percent": 12},
        {"name": "Health", "total": 320.00, "percent": 6},
        {"name": "Transport", "total": 200.00, "percent": 4},
        {"name": "Other", "total": 150.00, "percent": 3},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
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
