from datetime import date

import pytest

import database.db as db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

# Seeded demo expenses (see database/db.py:seed_db)
SEED_AMOUNTS = [450.00, 200.00, 1850.50, 320.00, 600.00, 1299.00, 280.00, 150.00]
SEED_TOTAL = sum(SEED_AMOUNTS)  # 5149.50


# --- USER / ROUTE BASICS -------------------------------------------- #

def test_get_user_by_id_valid(demo_user_id):
    user = get_user_by_id(demo_user_id)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    # Seeded just now, so member_since is the current month
    assert user["member_since"] == date.today().strftime("%B %Y")


def test_get_user_by_id_missing():
    assert get_user_by_id(99999) is None


def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_stale_session_redirects(client, login):
    login(99999)
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_shows_demo_user(client, login, demo_user_id):
    login(demo_user_id)
    resp = client.get("/profile")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "₹" in html
    assert ">DU<" in html


def test_profile_empty_user(client, login, empty_user_id):
    login(empty_user_id)
    resp = client.get("/profile")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Asha Verma" in html
    assert "No expenses yet" in html


# --- TRANSACTIONS --------------------------------------------------- #

def test_recent_transactions_demo_user(demo_user_id):
    txns = get_recent_transactions(demo_user_id)
    assert len(txns) == 8
    for t in txns:
        assert set(t) == {"date", "description", "category", "amount"}
    dates = [t["date"] for t in txns]
    assert dates == sorted(dates, reverse=True)
    assert sorted(t["amount"] for t in txns) == sorted(SEED_AMOUNTS)


def test_recent_transactions_limit(demo_user_id):
    txns = get_recent_transactions(demo_user_id, limit=3)
    assert len(txns) == 3
    assert txns[0]["date"] == max(t["date"] for t in get_recent_transactions(demo_user_id))


def test_recent_transactions_empty_user(empty_user_id):
    assert get_recent_transactions(empty_user_id) == []


def test_profile_shows_transactions(client, login, demo_user_id):
    login(demo_user_id)
    resp = client.get("/profile")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert html.count('class="profile-date"') == 8
    newest = date.fromisoformat(get_recent_transactions(demo_user_id)[0]["date"])
    first_cell = html.split('class="profile-date">', 1)[1].split("<", 1)[0]
    assert first_cell == newest.strftime("%d %b %Y")

# --- END TRANSACTIONS ----------------------------------------------- #


# --- SUMMARY STATS -------------------------------------------------- #
def test_summary_stats_demo_user(demo_user_id):
    stats = get_summary_stats(demo_user_id)
    assert stats["total_spent"] == pytest.approx(SEED_TOTAL)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_summary_stats_empty_user(empty_user_id):
    assert get_summary_stats(empty_user_id) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_profile_route_shows_summary_stats(client, login, demo_user_id):
    login(demo_user_id)
    resp = client.get("/profile")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "₹5,149.50" in html
    assert "Bills" in html


def test_profile_route_summary_stats_empty_user(client, login, empty_user_id):
    login(empty_user_id)
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert "₹0.00" in resp.get_data(as_text=True)

# --- END SUMMARY STATS ---------------------------------------------- #


# --- CATEGORY BREAKDOWN --------------------------------------------- #

def test_category_breakdown_demo(demo_user_id):
    cats = get_category_breakdown(demo_user_id)
    assert len(cats) == 7
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert cats[0]["name"] == "Bills"
    assert cats[0]["amount"] == 1850.50
    food = next(c for c in cats if c["name"] == "Food")
    assert food["amount"] == 730
    assert all(isinstance(c["pct"], int) for c in cats)
    assert sum(c["pct"] for c in cats) == 100


def test_category_breakdown_rounding_remainder():
    user_id = db.create_user("Even Split", "even@example.com", "password123")
    conn = db.get_db()
    try:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 100.0, cat, date.today().isoformat(), "split")
                for cat in ("Food", "Transport", "Bills")
            ],
        )
        conn.commit()
    finally:
        conn.close()

    cats = get_category_breakdown(user_id)
    pcts = [c["pct"] for c in cats]
    assert all(isinstance(p, int) for p in pcts)
    assert sum(pcts) == 100
    assert sorted(pcts, reverse=True) == [34, 33, 33]


def test_category_breakdown_empty_user(empty_user_id):
    assert get_category_breakdown(empty_user_id) == []


def test_profile_category_breakdown_route(client, login, demo_user_id):
    login(demo_user_id)
    resp = client.get("/profile")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert html.count('class="profile-bar-row"') == 7
    assert "₹1,850.50" in html


# --- END CATEGORY BREAKDOWN ----------------------------------------- #
