"""Tests for Step 7: Add Expense (GET/POST /expenses/add) and insert_expense."""
import re

import pytest

from database.db import get_db
from database.queries import insert_expense

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
URL = "/expenses/add"

VALID = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}


def fetch_expenses(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_id, amount, category, date, description "
        "FROM expenses WHERE user_id = ? ORDER BY id",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def count_all():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn.close()
    return n


def form(**overrides):
    data = dict(VALID)
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def assert_error_page(resp):
    assert resp.status_code == 200, "Validation failure must re-render form with 200"
    body = resp.get_data(as_text=True).lower()
    assert "<form" in body, "Form should be re-rendered"
    assert any(w in body for w in ("error", "invalid", "required", "must", "please")), (
        "Expected an error message in the response"
    )


# ---------------------------------------------------------------- insert_expense

class TestInsertExpense:
    def test_insert_expense_valid_inserts_row(self, empty_user_id):
        insert_expense(empty_user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = fetch_expenses(empty_user_id)
        assert len(rows) == 1
        r = rows[0]
        assert r["user_id"] == empty_user_id
        assert r["amount"] == 50.0
        assert r["category"] == "Food"
        assert r["date"] == "2026-03-20"
        assert r["description"] == "Lunch"

    def test_insert_expense_none_description_stored_as_null(self, empty_user_id):
        insert_expense(empty_user_id, 20.0, "Bills", "2026-03-21", None)
        rows = fetch_expenses(empty_user_id)
        assert len(rows) == 1
        assert rows[0]["description"] is None

    def test_insert_expense_sql_injection_in_description_stored_literally(self, empty_user_id):
        payload = "x'); DROP TABLE expenses;--"
        insert_expense(empty_user_id, 5.0, "Other", "2026-03-22", payload)
        rows = fetch_expenses(empty_user_id)
        assert rows[0]["description"] == payload

    def test_insert_expense_does_not_touch_other_users(self, empty_user_id, demo_user_id):
        before = len(fetch_expenses(demo_user_id))
        insert_expense(empty_user_id, 5.0, "Other", "2026-03-22", "a")
        assert len(fetch_expenses(demo_user_id)) == before


# ---------------------------------------------------------------- auth guards

class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        resp = client.get(URL)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_post_logged_out_redirects_to_login(self, client):
        resp = client.post(URL, data=form())
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_post_logged_out_inserts_nothing(self, client):
        before = count_all()
        client.post(URL, data=form())
        assert count_all() == before


# ---------------------------------------------------------------- GET form

class TestGetForm:
    def test_get_logged_in_returns_200(self, client, login, empty_user_id):
        login(empty_user_id)
        assert client.get(URL).status_code == 200

    def test_get_contains_post_form(self, client, login, empty_user_id):
        login(empty_user_id)
        body = client.get(URL).get_data(as_text=True)
        m = re.search(r"<form[^>]*>", body, re.I)
        assert m, "Expected a <form> tag"
        assert re.search(r'method=["\']?post', m.group(0), re.I), "Form must use POST"

    def test_get_contains_all_fields(self, client, login, empty_user_id):
        login(empty_user_id)
        body = client.get(URL).get_data(as_text=True)
        for name in ("amount", "category", "date", "description"):
            assert re.search(r'name=["\']%s["\']' % name, body), f"Missing field {name}"

    def test_get_category_select_has_exactly_seven_options(self, client, login, empty_user_id):
        login(empty_user_id)
        body = client.get(URL).get_data(as_text=True)
        select = re.search(
            r'<select[^>]*name=["\']category["\'][^>]*>(.*?)</select>', body, re.I | re.S
        )
        assert select, "Expected category <select>"
        options = re.findall(r"<option([^>]*)>(.*?)</option>", select.group(1), re.I | re.S)
        # Ignore a disabled "Choose a category" placeholder; only real choices count
        options = [
            label.strip() for attrs, label in options
            if "disabled" not in attrs and not re.search(r'value=["\']["\']', attrs)
        ]
        assert options == CATEGORIES, f"Unexpected options: {options}"

    def test_get_date_defaults_to_today(self, client, login, empty_user_id):
        from datetime import date
        login(empty_user_id)
        body = client.get(URL).get_data(as_text=True)
        assert date.today().isoformat() in body, "Date should default to today"

    def test_get_has_save_button_and_cancel_link_to_profile(self, client, login, empty_user_id):
        login(empty_user_id)
        body = client.get(URL).get_data(as_text=True)
        assert "Save Expense" in body
        assert 'href="/profile"' in body, "Cancel link should point to /profile"


# ---------------------------------------------------------------- POST valid

class TestPostValid:
    def test_post_valid_redirects_to_profile(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(URL, data=form())
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")

    def test_post_valid_inserts_row_for_user(self, client, login, empty_user_id):
        login(empty_user_id)
        client.post(URL, data=form())
        rows = fetch_expenses(empty_user_id)
        assert len(rows) == 1
        r = rows[0]
        assert r["amount"] == 50.0
        assert r["category"] == "Food"
        assert r["date"] == "2026-03-20"
        assert r["description"] == "Lunch"

    def test_post_valid_does_not_add_to_other_user(self, client, login, empty_user_id, demo_user_id):
        before = len(fetch_expenses(demo_user_id))
        login(empty_user_id)
        client.post(URL, data=form())
        assert len(fetch_expenses(demo_user_id)) == before

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_post_each_valid_category_accepted(self, client, login, empty_user_id, category):
        login(empty_user_id)
        resp = client.post(URL, data=form(category=category))
        assert resp.status_code == 302
        assert fetch_expenses(empty_user_id)[0]["category"] == category

    def test_post_decimal_amount_stored(self, client, login, empty_user_id):
        login(empty_user_id)
        client.post(URL, data=form(amount="12.34"))
        assert fetch_expenses(empty_user_id)[0]["amount"] == pytest.approx(12.34)

    def test_post_minimum_amount_accepted(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(URL, data=form(amount="0.01"))
        assert resp.status_code == 302
        assert fetch_expenses(empty_user_id)[0]["amount"] == pytest.approx(0.01)

    def test_post_new_expense_appears_on_profile(self, client, login, empty_user_id):
        login(empty_user_id)
        client.post(URL, data=form(description="ZZ-unique-lunch", date="2026-03-20"))
        resp = client.get("/profile?date_from=2026-01-01&date_to=2026-12-31", follow_redirects=True)
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "ZZ-unique-lunch" in body, "New expense should appear in transaction list"
        assert "₹" in body

    def test_post_valid_follow_redirect_lands_on_profile(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(URL, data=form(), follow_redirects=True)
        assert resp.status_code == 200
        assert resp.request.path == "/profile"

    def test_post_sql_injection_description_stored_literally(self, client, login, empty_user_id):
        payload = "'; DROP TABLE expenses;--"
        login(empty_user_id)
        client.post(URL, data=form(description=payload))
        assert fetch_expenses(empty_user_id)[0]["description"] == payload


# ---------------------------------------------------------------- description

class TestDescription:
    def test_post_missing_description_redirects_and_stores_null(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(URL, data=form(description=None))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")
        assert fetch_expenses(empty_user_id)[0]["description"] is None

    @pytest.mark.parametrize("blank", ["", "   ", "\t "])
    def test_post_blank_description_stored_as_null(self, client, login, empty_user_id, blank):
        login(empty_user_id)
        resp = client.post(URL, data=form(description=blank))
        assert resp.status_code == 302
        assert fetch_expenses(empty_user_id)[0]["description"] is None

    def test_post_description_is_stripped(self, client, login, empty_user_id):
        login(empty_user_id)
        client.post(URL, data=form(description="  Dinner  "))
        assert fetch_expenses(empty_user_id)[0]["description"] == "Dinner"

    def test_post_description_newlines_and_control_chars_removed(
        self, client, login, empty_user_id
    ):
        login(empty_user_id)
        client.post(URL, data=form(description="Team\nlunch\x00\t at  cafe"))
        assert fetch_expenses(empty_user_id)[0]["description"] == "Team lunch at cafe"


# ---------------------------------------------------------------- validation

class TestValidation:
    @pytest.mark.parametrize(
        "amount",
        [None, "", "   ", "0", "0.00", "-5", "-0.01", "abc", "12abc", "1,00"],
        ids=["missing", "empty", "spaces", "zero", "zero-dec", "negative",
             "neg-small", "alpha", "mixed", "comma"],
    )
    def test_post_bad_amount_rerenders_with_error_and_inserts_nothing(
        self, client, login, empty_user_id, amount
    ):
        login(empty_user_id)
        resp = client.post(URL, data=form(amount=amount))
        assert_error_page(resp)
        assert fetch_expenses(empty_user_id) == []

    @pytest.mark.parametrize(
        "category",
        [None, "", "Groceries", "food", "FOOD", "Food; DROP TABLE expenses", "<script>"],
        ids=["missing", "empty", "unknown", "lowercase", "uppercase", "sqli", "xss"],
    )
    def test_post_bad_category_rerenders_with_error_and_inserts_nothing(
        self, client, login, empty_user_id, category
    ):
        login(empty_user_id)
        resp = client.post(URL, data=form(category=category))
        assert_error_page(resp)
        assert fetch_expenses(empty_user_id) == []

    @pytest.mark.parametrize(
        "bad_date",
        [None, "", "not-a-date", "2026-13-01", "2026-02-30", "20-03-2026", "2026/03/20"],
        ids=["missing", "empty", "text", "month13", "feb30", "dmy", "slashes"],
    )
    def test_post_bad_date_rerenders_with_error_and_inserts_nothing(
        self, client, login, empty_user_id, bad_date
    ):
        login(empty_user_id)
        resp = client.post(URL, data=form(date=bad_date))
        assert_error_page(resp)
        assert fetch_expenses(empty_user_id) == []

    @pytest.mark.parametrize("amount", ["inf", "nan", "10000000.01", "1e300"])
    def test_post_non_finite_or_huge_amount_rejected(self, client, login, empty_user_id, amount):
        login(empty_user_id)
        resp = client.post(URL, data=form(amount=amount))
        assert_error_page(resp)
        assert fetch_expenses(empty_user_id) == []

    def test_post_max_amount_accepted(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(URL, data=form(amount="10000000"))
        assert resp.status_code == 302
        assert fetch_expenses(empty_user_id)[0]["amount"] == 10_000_000

    def test_post_description_over_200_chars_rejected(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(URL, data=form(description="x" * 201))
        assert_error_page(resp)
        assert fetch_expenses(empty_user_id) == []

    def test_post_validation_error_does_not_redirect(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(URL, data=form(amount="0"))
        assert "Location" not in resp.headers

    def test_post_validation_error_leaves_total_row_count_unchanged(self, client, login, demo_user_id):
        login(demo_user_id)
        before = count_all()
        client.post(URL, data=form(amount="-1"))
        assert count_all() == before


# ---------------------------------------------------------------- re-population

class TestRepopulation:
    def test_error_rerender_retains_submitted_values(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(
            URL,
            data=form(amount="0", category="Health", date="2026-04-05", description="ZZ-keep-me"),
        )
        body = resp.get_data(as_text=True)
        assert "2026-04-05" in body, "Date should be retained"
        assert "ZZ-keep-me" in body, "Description should be retained"
        sel = re.search(r"<option[^>]*selected[^>]*>\s*Health\s*</option>", body, re.I)
        assert sel, "Category Health should remain selected"

    def test_invalid_category_rerender_retains_amount_and_description(
        self, client, login, empty_user_id
    ):
        login(empty_user_id)
        resp = client.post(
            URL, data=form(amount="77.5", category="Bogus", description="ZZ-desc-kept")
        )
        body = resp.get_data(as_text=True)
        assert "77.5" in body, "Amount should be retained"
        assert "ZZ-desc-kept" in body

    def test_invalid_date_rerender_retains_amount(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(URL, data=form(amount="42.25", date="garbage"))
        assert "42.25" in resp.get_data(as_text=True)

    def test_rerender_escapes_html_in_description(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.post(URL, data=form(amount="0", description="<script>alert(1)</script>"))
        body = resp.get_data(as_text=True)
        assert "<script>alert(1)</script>" not in body, "User input must be HTML-escaped"


# ---------------------------------------------------------------- navigation links

class TestNavigation:
    def test_profile_has_add_expense_link(self, client, login, demo_user_id):
        login(demo_user_id)
        body = client.get("/profile").get_data(as_text=True)
        assert "Add Expense" in body
        assert 'href="/expenses/add"' in body

    def test_navbar_shows_add_expense_when_logged_in(self, client, login, demo_user_id):
        login(demo_user_id)
        body = client.get("/").get_data(as_text=True)
        assert "Add Expense" in body
        assert 'href="/expenses/add"' in body

    def test_navbar_hides_add_expense_when_logged_out(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "/expenses/add" not in body
        assert "Add Expense" not in body

    def test_add_expense_link_from_profile_target_returns_200(self, client, login, demo_user_id):
        login(demo_user_id)
        assert client.get(URL).status_code == 200


# ---------------------------------------------------------------- CSRF

@pytest.fixture
def csrf_on(app, monkeypatch):
    monkeypatch.setitem(app.config, "CSRF_ENABLED", True)


def csrf_token_from(body):
    m = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert m, "Form should include a hidden csrf_token field"
    return m.group(1)


class TestCsrf:
    def test_form_includes_csrf_token(self, client, login, empty_user_id, csrf_on):
        login(empty_user_id)
        csrf_token_from(client.get(URL).get_data(as_text=True))

    def test_post_without_token_rejected(self, client, login, empty_user_id, csrf_on):
        login(empty_user_id)
        client.get(URL)  # creates the session token
        resp = client.post(URL, data=form())
        assert resp.status_code == 400
        assert fetch_expenses(empty_user_id) == []

    def test_post_with_wrong_token_rejected(self, client, login, empty_user_id, csrf_on):
        login(empty_user_id)
        client.get(URL)
        resp = client.post(URL, data=form(csrf_token="not-the-token"))
        assert resp.status_code == 400
        assert fetch_expenses(empty_user_id) == []

    def test_post_with_valid_token_succeeds(self, client, login, empty_user_id, csrf_on):
        login(empty_user_id)
        token = csrf_token_from(client.get(URL).get_data(as_text=True))
        resp = client.post(URL, data=form(csrf_token=token))
        assert resp.status_code == 302
        assert len(fetch_expenses(empty_user_id)) == 1

    @pytest.mark.parametrize("page", ["/login", "/register"])
    def test_auth_forms_include_csrf_token(self, client, csrf_on, page):
        csrf_token_from(client.get(page).get_data(as_text=True))

    def test_login_post_without_token_rejected(self, client, csrf_on):
        client.get("/login")
        resp = client.post(
            "/login", data={"email": "demo@spendly.com", "password": "demo123"}
        )
        assert resp.status_code == 400
