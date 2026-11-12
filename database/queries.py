"""Query helpers for expenses: profile-page reads plus the writes for adding,
editing and deleting.

Pure data access: no Flask imports. Every helper opens its own connection via
get_db() and closes it before returning.
"""

from datetime import datetime

from database.db import get_db


def _date_clause(date_from, date_to):
    """Return (sql_fragment, params) for an inclusive date range.

    Filters only when both bounds are given; otherwise returns ("", []) so the
    query is unchanged. The fragment is a fixed string (never user input) with
    a leading space; the date values are always bound as ? parameters.
    """
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", [date_from, date_to]
    return "", []


def get_user_by_id(user_id):
    """Return {"name", "email", "member_since"} for the user, or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    created = datetime.strptime(row["created_at"][:10], "%Y-%m-%d")
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": created.strftime("%B %Y"),
    }


# --- TRANSACTIONS --------------------------------------------------- #

def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return the user's newest expenses as a list of dicts (newest first).

    Each dict has keys id, date (ISO 'YYYY-MM-DD'), description, category,
    amount.
    Optional date_from / date_to (ISO strings) limit results to that inclusive
    range. Returns [] if the user has no expenses in range.
    """
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, date, description, category, amount FROM expenses "
            f"WHERE user_id = ?{date_sql} ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *date_params, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "id": row["id"],
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]


# --- END TRANSACTIONS ----------------------------------------------- #


# --- SUMMARY STATS -------------------------------------------------- #

def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return {"total_spent", "transaction_count", "top_category"} for the user.

    Optional date_from / date_to (ISO strings) limit stats to that inclusive range.
    """
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            f"FROM expenses WHERE user_id = ?{date_sql}",
            (user_id, *date_params),
        ).fetchone()
        top = conn.execute(
            f"SELECT category FROM expenses WHERE user_id = ?{date_sql} "
            "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id, *date_params),
        ).fetchone()
    finally:
        conn.close()

    if totals["cnt"] == 0:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    return {
        "total_spent": float(totals["total"]),
        "transaction_count": int(totals["cnt"]),
        "top_category": top["category"],
    }


# --- END SUMMARY STATS ---------------------------------------------- #


# --- CATEGORY BREAKDOWN --------------------------------------------- #

def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return [{"name", "amount", "pct"}] per category, largest first.

    pct values are ints that sum to exactly 100; the largest category absorbs
    the rounding remainder. Optional date_from / date_to (ISO strings) limit
    the breakdown to that inclusive range. Returns [] when there are no
    expenses in range.
    """
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            f"WHERE user_id = ?{date_sql} "
            "GROUP BY category ORDER BY SUM(amount) DESC",
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()

    grand_total = sum(row["total"] for row in rows)
    if not rows or grand_total <= 0:
        return []

    categories = [
        {
            "name": row["category"],
            "amount": row["total"],
            "pct": int(round(row["total"] / grand_total * 100)),
        }
        for row in rows
    ]
    categories[0]["pct"] += 100 - sum(c["pct"] for c in categories)
    return categories


# --- END CATEGORY BREAKDOWN ----------------------------------------- #


# --- SINGLE EXPENSE ------------------------------------------------- #

def get_expense_by_id(expense_id, user_id):
    """Return one of the user's expenses as a dict, or None.

    Scoped by user_id, so another user's expense is indistinguishable from a
    missing one. Keys: id, amount, category, date (ISO), description.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    return {
        "id": row["id"],
        "amount": row["amount"],
        "category": row["category"],
        "date": row["date"],
        "description": row["description"],
    }


# --- END SINGLE EXPENSE --------------------------------------------- #


# --- WRITES --------------------------------------------------------- #

def insert_expense(user_id, amount, category, expense_date, description):
    """Insert one expense for the user and return its new id.

    Expects already-validated values: expense_date as an ISO 'YYYY-MM-DD'
    string and description as a string or None.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, expense_date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_expense(expense_id, user_id, amount, category, expense_date, description):
    """Update one of the user's expenses and return the number of rows changed.

    Takes the same already-validated values as insert_expense(). Returns 0 if
    the expense doesn't exist or belongs to another user.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE expenses "
            "SET amount = ?, category = ?, date = ?, description = ? "
            "WHERE id = ? AND user_id = ?",
            (amount, category, expense_date, description, expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def delete_expense_by_id(expense_id, user_id):
    """Delete one of the user's expenses and return the number of rows removed.

    Returns 0 if the expense doesn't exist or belongs to another user.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# --- END WRITES ----------------------------------------------------- #
