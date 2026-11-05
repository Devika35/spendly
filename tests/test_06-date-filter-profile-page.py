"""Tests for Step 6: date-range filter on GET /profile (spec 06)."""
from datetime import date, timedelta

import pytest

from database.db import get_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

TODAY = date.today()


def _iso(offset_days):
    return (TODAY - timedelta(days=offset_days)).isoformat()


def add_expense(user_id, amount, category, iso_date, description):
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, iso_date, description),
    )
    conn.commit()
    conn.close()


def snapshot_expenses():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, user_id, amount, category, date, description "
        "FROM expenses ORDER BY id"
    ).fetchall()
    conn.close()
    return [tuple(r) for r in rows]


@pytest.fixture
def spread_user(empty_user_id):
    """User with expenses at known distances from today."""
    uid = empty_user_id
    add_expense(uid, 100.00, "Food", _iso(0), "ZZ-today")
    add_expense(uid, 200.00, "Transport", _iso(60), "ZZ-60d")
    add_expense(uid, 400.00, "Bills", _iso(150), "ZZ-150d")
    add_expense(uid, 800.00, "Health", _iso(400), "ZZ-400d")
    return uid


@pytest.fixture
def fixed_user(empty_user_id):
    """User with expenses on fixed absolute dates for custom-range tests."""
    uid = empty_user_id
    add_expense(uid, 100.00, "Food", "2024-01-10", "FX-jan10")
    add_expense(uid, 200.00, "Food", "2024-01-20", "FX-jan20")
    add_expense(uid, 300.00, "Bills", "2024-02-15", "FX-feb15")
    add_expense(uid, 400.00, "Health", "2024-03-05", "FX-mar05")
    return uid


# ------------------------------------------------------------------ #
# Auth guard
# ------------------------------------------------------------------ #

class TestAuthGuard:
    @pytest.mark.parametrize("qs", ["", "?date_from=2024-01-01&date_to=2024-12-31"])
    def test_profile_unauthenticated_redirects_to_login(self, client, qs):
        resp = client.get("/profile" + qs)
        assert resp.status_code == 302, "Expected redirect for anonymous user"
        assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# Query helpers: date range
# ------------------------------------------------------------------ #

class TestQueryHelpers:
    def test_summary_stats_range_is_inclusive_on_both_ends(self, fixed_user):
        stats = get_summary_stats(fixed_user, "2024-01-10", "2024-02-15")
        assert stats["transaction_count"] == 3
        assert stats["total_spent"] == pytest.approx(600.00)

    def test_summary_stats_top_category_respects_range(self, fixed_user):
        stats = get_summary_stats(fixed_user, "2024-02-01", "2024-03-31")
        assert stats["transaction_count"] == 2
        assert stats["top_category"] == "Health"

    def test_summary_stats_no_match_returns_zero_and_dash(self, fixed_user):
        stats = get_summary_stats(fixed_user, "1999-01-01", "1999-12-31")
        assert stats["total_spent"] == 0
        assert stats["transaction_count"] == 0
        assert stats["top_category"] == "—"

    def test_recent_transactions_only_within_range(self, fixed_user):
        txs = get_recent_transactions(fixed_user, date_from="2024-01-15", date_to="2024-02-28")
        assert {t["description"] for t in txs} == {"FX-jan20", "FX-feb15"}

    def test_recent_transactions_ordered_newest_first_when_filtered(self, fixed_user):
        txs = get_recent_transactions(fixed_user, date_from="2024-01-01", date_to="2024-12-31")
        dates = [t["date"] for t in txs]
        assert dates == sorted(dates, reverse=True), "Ordering must be unchanged"

    def test_recent_transactions_limit_still_applies_with_filter(self, fixed_user):
        txs = get_recent_transactions(
            fixed_user, limit=2, date_from="2024-01-01", date_to="2024-12-31"
        )
        assert len(txs) == 2

    def test_recent_transactions_no_match_returns_empty(self, fixed_user):
        assert get_recent_transactions(fixed_user, date_from="1999-01-01", date_to="1999-01-02") == []

    def test_category_breakdown_only_within_range(self, fixed_user):
        cats = get_category_breakdown(fixed_user, "2024-01-01", "2024-01-31")
        assert [c["name"] for c in cats] == ["Food"]
        assert cats[0]["amount"] == pytest.approx(300.00)

    def test_category_breakdown_percentages_recalculated_for_range(self, fixed_user):
        cats = get_category_breakdown(fixed_user, "2024-02-01", "2024-03-31")
        by_name = {c["name"]: c for c in cats}
        # Bills 300 / Health 400 of 700 -> 43% / 57%
        assert by_name["Bills"]["pct"] == 43
        assert by_name["Health"]["pct"] == 57

    def test_category_breakdown_no_match_returns_empty(self, fixed_user):
        assert get_category_breakdown(fixed_user, "1999-01-01", "1999-12-31") == []

    def test_helpers_without_dates_match_unfiltered_totals(self, demo_user_id):
        stats = get_summary_stats(demo_user_id)
        assert stats["transaction_count"] == 8
        assert stats["total_spent"] == pytest.approx(5149.50)
        assert len(get_recent_transactions(demo_user_id)) == 8
        assert len(get_category_breakdown(demo_user_id)) == 7

    def test_helpers_wide_range_equals_unfiltered(self, demo_user_id):
        assert get_summary_stats(demo_user_id, "2000-01-01", "2100-01-01") == get_summary_stats(demo_user_id)
        assert get_category_breakdown(demo_user_id, "2000-01-01", "2100-01-01") == get_category_breakdown(demo_user_id)

    def test_helpers_do_not_leak_other_users_expenses(self, fixed_user, demo_user_id):
        stats = get_summary_stats(fixed_user, "2000-01-01", "2100-01-01")
        assert stats["transaction_count"] == 4

    def test_sql_injection_in_dates_is_harmless(self, fixed_user):
        before = snapshot_expenses()
        payload = "2024-01-01' OR '1'='1"
        get_summary_stats(fixed_user, payload, "2024-12-31")
        get_recent_transactions(fixed_user, date_from=payload, date_to="2024-12-31")
        get_category_breakdown(fixed_user, payload, "2024-12-31")
        assert snapshot_expenses() == before


# ------------------------------------------------------------------ #
# Route: unfiltered behaviour
# ------------------------------------------------------------------ #

class TestProfileUnfiltered:
    def test_no_params_shows_all_expenses(self, client, login, demo_user_id):
        login(demo_user_id)
        resp = client.get("/profile")
        assert resp.status_code == 200
        assert "₹5,149.50".encode() in resp.data, "Unfiltered total expected"

    def test_only_date_from_falls_back_to_unfiltered(self, client, login, spread_user):
        login(spread_user)
        resp = client.get("/profile?date_from=" + _iso(1))
        assert resp.status_code == 200
        for d in ("ZZ-today", "ZZ-60d", "ZZ-150d", "ZZ-400d"):
            assert d.encode() in resp.data, f"{d} should show when only one bound given"

    def test_only_date_to_falls_back_to_unfiltered(self, client, login, spread_user):
        login(spread_user)
        resp = client.get("/profile?date_to=" + _iso(100))
        assert resp.status_code == 200
        assert b"ZZ-today" in resp.data and b"ZZ-400d" in resp.data

    def test_empty_param_values_fall_back_to_unfiltered(self, client, login, spread_user):
        login(spread_user)
        resp = client.get("/profile?date_from=&date_to=")
        assert resp.status_code == 200
        assert "₹1,500.00".encode() in resp.data


# ------------------------------------------------------------------ #
# Route: custom ranges
# ------------------------------------------------------------------ #

class TestProfileCustomRange:
    def test_valid_range_filters_transactions(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=2024-01-15&date_to=2024-02-28")
        assert resp.status_code == 200
        assert b"FX-jan20" in resp.data and b"FX-feb15" in resp.data
        assert b"FX-jan10" not in resp.data
        assert b"FX-mar05" not in resp.data

    def test_valid_range_filters_summary_total(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=2024-01-15&date_to=2024-02-28")
        assert "₹500.00".encode() in resp.data, "200 + 300 expected"
        assert "₹1,000.00".encode() not in resp.data

    def test_valid_range_filters_category_breakdown(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=2024-03-01&date_to=2024-03-31")
        assert b"Health" in resp.data
        assert b"Bills" not in resp.data
        assert b"Food" not in resp.data

    def test_same_day_range_is_inclusive(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=2024-02-15&date_to=2024-02-15")
        assert b"FX-feb15" in resp.data
        assert b"FX-jan20" not in resp.data

    def test_range_with_no_expenses_shows_zero_state(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=1999-01-01&date_to=1999-12-31")
        assert resp.status_code == 200
        assert "₹0.00".encode() in resp.data
        assert "—".encode() in resp.data, "Empty top category renders as dash"
        assert b"FX-" not in resp.data

    def test_user_with_no_expenses_and_filter_does_not_error(self, client, login, empty_user_id):
        login(empty_user_id)
        resp = client.get("/profile?date_from=2024-01-01&date_to=2024-12-31")
        assert resp.status_code == 200
        assert "₹0.00".encode() in resp.data

    def test_rupee_symbol_present_with_active_filter(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        assert "₹".encode() in resp.data

    def test_filter_does_not_show_other_users_data(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=2000-01-01&date_to=2100-01-01")
        assert b"Bills" in resp.data
        assert "₹5,149.50".encode() not in resp.data

    def test_custom_range_reflected_in_date_inputs(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=2024-01-15&date_to=2024-02-28")
        assert b'type="date"' in resp.data
        assert b"2024-01-15" in resp.data
        assert b"2024-02-28" in resp.data


# ------------------------------------------------------------------ #
# Route: invalid input
# ------------------------------------------------------------------ #

class TestProfileInvalidInput:
    @pytest.mark.parametrize(
        "qs",
        [
            "date_from=not-a-date&date_to=2024-12-31",
            "date_from=2024-01-01&date_to=garbage",
            "date_from=not-a-date&date_to=also-bad",
            "date_from=2024-13-45&date_to=2024-12-31",
            "date_from=01/02/2024&date_to=12/31/2024",
            "date_from=2024-02-30&date_to=2024-12-31",
            "date_from=%27%3B+DROP+TABLE+expenses%3B--&date_to=2024-12-31",
            "date_from=" + "9" * 500 + "&date_to=2024-12-31",
        ],
    )
    def test_malformed_dates_fall_back_to_unfiltered_without_crash(
        self, client, login, fixed_user, qs
    ):
        login(fixed_user)
        resp = client.get("/profile?" + qs)
        assert resp.status_code == 200, "Malformed dates must not crash"
        for d in (b"FX-jan10", b"FX-jan20", b"FX-feb15", b"FX-mar05"):
            assert d in resp.data, "Unfiltered view expected"
        assert "₹1,000.00".encode() in resp.data

    def test_malformed_dates_do_not_modify_data(self, client, login, fixed_user):
        login(fixed_user)
        before = snapshot_expenses()
        client.get("/profile?date_from=%27%3B+DROP+TABLE+expenses%3B--&date_to=2024-12-31")
        assert snapshot_expenses() == before

    def test_start_after_end_shows_flash_error(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get(
            "/profile?date_from=2024-03-01&date_to=2024-01-01", follow_redirects=True
        )
        assert resp.status_code == 200
        assert b"Start date must be before end date." in resp.data

    def test_start_after_end_falls_back_to_unfiltered(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get(
            "/profile?date_from=2024-03-01&date_to=2024-01-01", follow_redirects=True
        )
        for d in (b"FX-jan10", b"FX-jan20", b"FX-feb15", b"FX-mar05"):
            assert d in resp.data
        assert "₹1,000.00".encode() in resp.data

    def test_valid_range_shows_no_flash_error(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=2024-01-01&date_to=2024-03-01")
        assert b"Start date must be before end date." not in resp.data

    def test_unfiltered_shows_no_flash_error(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile")
        assert b"Start date must be before end date." not in resp.data

    def test_malformed_date_alone_shows_no_ordering_error(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=not-a-date&date_to=2024-01-01")
        assert b"Start date must be before end date." not in resp.data


# ------------------------------------------------------------------ #
# Presets
# ------------------------------------------------------------------ #

class TestPresets:
    def test_filter_bar_has_four_preset_labels(self, client, login, demo_user_id):
        login(demo_user_id)
        resp = client.get("/profile")
        for label in (b"This Month", b"Last 3 Months", b"Last 6 Months", b"All Time"):
            assert label in resp.data, f"Missing preset {label!r}"

    def test_filter_bar_has_apply_button(self, client, login, demo_user_id):
        login(demo_user_id)
        resp = client.get("/profile")
        assert b"Apply" in resp.data
        assert b'name="date_from"' in resp.data
        assert b'name="date_to"' in resp.data

    def test_all_time_preset_is_clean_profile_url(self, client, login, demo_user_id):
        login(demo_user_id)
        resp = client.get("/profile")
        assert b'href="/profile"' in resp.data, "All Time must link to bare /profile"

    def test_this_month_link_uses_first_of_month_to_today(self, client, login, demo_user_id):
        login(demo_user_id)
        resp = client.get("/profile")
        first = TODAY.replace(day=1).isoformat()
        assert f"date_from={first}".encode() in resp.data
        assert f"date_to={TODAY.isoformat()}".encode() in resp.data

    def test_this_month_filters_to_current_month(self, client, login, spread_user):
        login(spread_user)
        first = TODAY.replace(day=1).isoformat()
        resp = client.get(f"/profile?date_from={first}&date_to={TODAY.isoformat()}")
        assert b"ZZ-today" in resp.data
        for d in (b"ZZ-60d", b"ZZ-150d", b"ZZ-400d"):
            assert d not in resp.data

    def test_last_3_months_window(self, client, login, spread_user):
        login(spread_user)
        resp = client.get(
            f"/profile?date_from={_iso(89)}&date_to={TODAY.isoformat()}"
        )
        assert b"ZZ-today" in resp.data and b"ZZ-60d" in resp.data
        assert b"ZZ-150d" not in resp.data and b"ZZ-400d" not in resp.data

    def test_last_6_months_window(self, client, login, spread_user):
        login(spread_user)
        resp = client.get(
            f"/profile?date_from={_iso(180)}&date_to={TODAY.isoformat()}"
        )
        for d in (b"ZZ-today", b"ZZ-60d", b"ZZ-150d"):
            assert d in resp.data
        assert b"ZZ-400d" not in resp.data

    def test_rendered_preset_links_filter_correctly_end_to_end(self, client, login, spread_user):
        """Follow the actual preset links rendered on the page."""
        import re
        login(spread_user)
        page = client.get("/profile").get_data(as_text=True)
        hrefs = [
            h.replace("&amp;", "&")
            for h in re.findall(r'href="(/profile\?[^"]*date_from=[^"]*)"', page)
        ]
        assert len(hrefs) >= 3, "Expected three dated preset links"
        for href in hrefs:
            resp = client.get(href)
            assert resp.status_code == 200
            assert b"ZZ-today" in resp.data, "Today's expense is in every preset"
            assert b"ZZ-400d" not in resp.data, "400-day-old expense is in no preset"

    def test_all_time_shows_everything(self, client, login, spread_user):
        login(spread_user)
        resp = client.get("/profile")
        for d in (b"ZZ-today", b"ZZ-60d", b"ZZ-150d", b"ZZ-400d"):
            assert d in resp.data
        assert "₹1,500.00".encode() in resp.data

    def test_seed_data_this_month_matches_dynamic_expectation(self, client, login, demo_user_id):
        """Seed rows are in the current month; some may be after today."""
        login(demo_user_id)
        first = TODAY.replace(day=1).isoformat()
        stats = get_summary_stats(demo_user_id, first, TODAY.isoformat())
        seed_days = {1: 450.00, 3: 200.00, 5: 1850.50, 8: 320.00,
                     12: 600.00, 15: 1299.00, 20: 280.00, 25: 150.00}
        expected = sum(a for d, a in seed_days.items() if d <= TODAY.day)
        assert stats["total_spent"] == pytest.approx(expected)
        resp = client.get(f"/profile?date_from={first}&date_to={TODAY.isoformat()}")
        assert resp.status_code == 200
        assert "₹".encode() in resp.data


# ------------------------------------------------------------------ #
# Active state
# ------------------------------------------------------------------ #

class TestActiveState:
    def _active_markup(self, html):
        return html.count("active")

    def test_active_marker_differs_between_filtered_and_all_time(
        self, client, login, demo_user_id
    ):
        login(demo_user_id)
        all_time = client.get("/profile").get_data(as_text=True)
        first = TODAY.replace(day=1).isoformat()
        this_month = client.get(
            f"/profile?date_from={first}&date_to={TODAY.isoformat()}"
        ).get_data(as_text=True)
        assert "active" in all_time, "All Time should be highlighted by default"
        assert all_time != this_month, "Active state must change with filter"

    def test_custom_range_has_no_error_and_renders_bar(self, client, login, fixed_user):
        login(fixed_user)
        resp = client.get("/profile?date_from=2024-01-01&date_to=2024-01-31")
        assert resp.status_code == 200
        assert b"Apply" in resp.data


# ------------------------------------------------------------------ #
# Read-only guarantee
# ------------------------------------------------------------------ #

class TestFilteringDoesNotModifyData:
    @pytest.mark.parametrize(
        "qs",
        [
            "",
            "?date_from=2024-01-01&date_to=2024-01-31",
            "?date_from=2024-03-01&date_to=2024-01-01",
            "?date_from=bad&date_to=worse",
        ],
    )
    def test_get_profile_leaves_expenses_unchanged(self, client, login, fixed_user, qs):
        login(fixed_user)
        before = snapshot_expenses()
        client.get("/profile" + qs, follow_redirects=True)
        assert snapshot_expenses() == before, "Filtering must be read-only"

    def test_query_helpers_leave_expenses_unchanged(self, demo_user_id):
        before = snapshot_expenses()
        get_summary_stats(demo_user_id, "2000-01-01", "2100-01-01")
        get_recent_transactions(demo_user_id, date_from="2000-01-01", date_to="2100-01-01")
        get_category_breakdown(demo_user_id, "2000-01-01", "2100-01-01")
        assert snapshot_expenses() == before
