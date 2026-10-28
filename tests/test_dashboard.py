"""Dashboard: the pure computation in vault_ledger.dashboard, the /dashboard
page and /api/dashboard route, and sign-in landing on /dashboard."""

from datetime import datetime, timedelta, timezone

import pytest

from vault_ledger import auth, dashboard
from vault_ledger.userdata import use_user_dir
from vault_ledger.webapp import app as app_mod, security

from tests.helpers import PASSWORD, make_user_client, new_client

# Mid-month, mid-afternoon in the machine's local zone (reports.py's months
# are machine-local too).
NOW = datetime(2026, 9, 18, 15, 0).astimezone()


def _iso(moment):
    return moment.isoformat(timespec="seconds")


def _entry(at, amount, account="Utilities Expense", corrected=False, vendor="Acme"):
    return {
        "confirmed_at": _iso(at), "filename": "a.png", "vendor": vendor, "description": "stuff",
        "date": "2026-09-01", "amount": str(amount), "account": account, "confidence": "0.9",
        "was_corrected": str(corrected),
    }


def _pending(item_id, at, amount="10.0", confidence="0.9", needs_review="False", rejection="", vendor="Shop"):
    return {
        "id": item_id, "queued_at": _iso(at), "filename": f"{item_id}.png", "vendor": vendor,
        "description": "d", "date": "09/01/2026", "amount": amount, "paid": "True",
        "predicted_account": "Office Supplies Expense", "confidence": confidence,
        "needs_review": needs_review, "rejection_reason": rejection, "entry_json": "{}",
    }


# ---- pure functions -----------------------------------------------------------

def test_empty_data_reads_as_zeros_not_placeholders():
    data = dashboard.build([], [], "this", NOW)
    assert data["review"] == {"pending": 0, "flagged": 0}
    assert data["posted"]["count"] == 0 and data["posted"]["total"] == 0
    assert data["posted"]["comparison"]["available"] is False
    assert data["open_value"] == {"total": 0, "count": 0, "unreadable": 0}
    assert data["acceptance"]["rate"] is None and data["acceptance"]["total"] == 0
    assert data["needs_review"] == [] and data["activity"] == [] and data["mix"] == []
    assert data["readiness"] == {"posted": 0, "pending": 0, "pct": None}
    assert data["month_label"] == data["current_month_label"] == "September 2026"
    assert data["has_ledger"] is False


@pytest.mark.parametrize("hour,word", [(5, "morning"), (11, "morning"), (12, "afternoon"),
                                       (17, "afternoon"), (18, "evening"), (0, "evening"), (4, "evening")])
def test_greeting_follows_the_hour(hour, word):
    head = dashboard.header("carol", NOW.replace(hour=hour))
    assert head["greeting"] == f"Good {word}, carol"
    assert head["today"] == "Friday 18 September 2026"


def test_month_boundaries_for_posted_rate_and_readiness():
    first_of_month = datetime(2026, 9, 1, 0, 0, 1).astimezone()
    last_of_prior = datetime(2026, 8, 31, 23, 59, 59).astimezone()
    entries = [
        _entry(first_of_month, 100, corrected=True),
        _entry(NOW - timedelta(hours=1), 50),
        _entry(last_of_prior, 999, "Rent Expense"),
    ]
    pending = [_pending("p1", NOW - timedelta(days=40))]  # queued last month, still open

    this = dashboard.build(entries, pending, "this", NOW)
    assert this["posted"]["count"] == 2 and this["posted"]["total"] == 150.0
    assert this["acceptance"]["rate"] == 0.5
    assert (this["acceptance"]["accepted"], this["acceptance"]["corrected"]) == (1, 1)
    assert this["acceptance"]["meaningful"] is False
    assert this["readiness"] == {"posted": 2, "pending": 1, "pct": 67}

    last = dashboard.build(entries, pending, "last", NOW)
    assert last["month_label"] == "August 2026" and last["current_month_label"] == "September 2026"
    assert last["posted"]["count"] == 1 and last["posted"]["total"] == 999.0
    assert last["acceptance"]["rate"] == 1.0
    assert [m["account"] for m in last["mix"]] == ["Rent Expense"]
    # readiness is always about the current month, whatever the toggle says
    assert last["readiness"] == this["readiness"]


def test_year_boundary_last_month_is_december():
    january = datetime(2027, 1, 3, 9, 0).astimezone()
    entries = [_entry(datetime(2026, 12, 30, 12, 0).astimezone(), 40)]
    data = dashboard.build(entries, [], "last", january)
    assert data["month_label"] == "December 2026" and data["posted"]["total"] == 40.0


def test_comparison_comes_from_period_summary():
    entries = [_entry(NOW - timedelta(hours=2), 150), _entry(datetime(2026, 8, 10, 12).astimezone(), 100)]
    comparison = dashboard.build(entries, [], "this", NOW)["posted"]["comparison"]
    assert comparison == {"available": True, "direction": "up", "pct": 50, "label": "last month"}


def test_review_table_flagged_first_then_lowest_confidence():
    base = NOW - timedelta(hours=5)
    pending = [
        _pending("calm-high", base, confidence="0.95"),
        _pending("calm-low", base, confidence="0.40"),
        _pending("flag-high", base, confidence="0.90", needs_review="True"),
        _pending("rejected", base, confidence="0.99", rejection="R2: not an expense account"),
        _pending("flag-low", base, confidence="0.20", needs_review="True"),
        _pending("calm-mid", base, confidence="0.70"),
        _pending("broken", base, confidence="not a number"),
    ]
    rows = dashboard.needs_review(pending)
    assert [r["id"] for r in rows] == ["flag-low", "flag-high", "rejected", "broken", "calm-low"]
    assert rows[0]["flagged"] is True and rows[-1]["flagged"] is False
    assert rows[3]["confidence"] is None
    assert dashboard.review_summary(pending) == {"pending": 7, "flagged": 3}


def test_open_value_skips_unreadable_amounts_instead_of_guessing():
    pending = [_pending("a", NOW, "12.50"), _pending("b", NOW, "7.25"), _pending("c", NOW, ""),
               _pending("d", NOW, "inf")]
    assert dashboard.open_value(pending) == {"total": 19.75, "count": 2, "unreadable": 2}


def test_activity_merges_newest_first_with_relative_times():
    entries = [
        _entry(NOW - timedelta(minutes=30), 20, "Rent Expense", vendor="Landlord"),
        _entry(NOW - timedelta(days=3), 30, "Travel & Transport Expense", corrected=True, vendor="Taxi"),
        {**_entry(NOW, 1), "confirmed_at": "garbage"},
    ]
    pending = [_pending("p1", NOW - timedelta(seconds=10), vendor="Fresh"),
               _pending("p2", NOW - timedelta(hours=3), vendor="Older")]
    events = dashboard.activity(entries, pending, NOW)
    assert [e["vendor"] for e in events] == ["Fresh", "Landlord", "Older", "Taxi"]
    assert [e["when"] for e in events] == ["just now", "30 min ago", "3 h ago", "3 days ago"]
    assert events[0]["text"] == "added to review queue" and events[0]["kind"] == "queued"
    assert events[1]["text"] == "posted to Rent Expense"
    assert events[3]["text"] == "corrected to Travel & Transport Expense" and events[3]["kind"] == "corrected"


def test_activity_is_capped_at_eight():
    entries = [_entry(NOW - timedelta(minutes=i + 1), i + 1) for i in range(12)]
    events = dashboard.activity(entries, [], NOW)
    assert len(events) == 8 and events[0]["amount"] == 1.0


def test_relative_time_older_than_a_week_shows_the_date():
    assert dashboard.relative_time(NOW - timedelta(days=1, hours=1), NOW) == "yesterday"
    assert dashboard.relative_time(NOW - timedelta(days=20), NOW) == "29 Aug 2026"
    assert dashboard.relative_time(datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc), NOW) != ""


def test_expense_mix_sorted_desc_with_shares():
    entries = [_entry(NOW - timedelta(hours=1), 300, "Rent Expense"),
               _entry(NOW - timedelta(hours=2), 75, "Utilities Expense"),
               _entry(NOW - timedelta(hours=3), 25, "Utilities Expense")]
    mix = dashboard.build(entries, [], "this", NOW)["mix"]
    assert mix == [
        {"account": "Rent Expense", "amount": 300.0, "share": 75.0},
        {"account": "Utilities Expense", "amount": 100.0, "share": 25.0},
    ]


# ---- routes ---------------------------------------------------------------------

def _enqueue(client, vendor, amount, needs_review=False):
    with use_user_dir(client.user_dir):
        return app_mod.enqueue(
            filename=f"{vendor}.png", vendor=vendor, description="d", date="03/14/2026", amount=amount,
            paid=True, predicted_account="Office Supplies Expense", confidence=0.9,
            needs_review=needs_review, rejection_reason=None, entry_json="{}",
        )


def test_dashboard_requires_login():
    anon = new_client(app_mod.app)
    res = anon.get("/dashboard")
    assert res.status_code == 302 and res.headers["Location"] == "/login?next=/dashboard"
    res = anon.get("/api/dashboard")
    assert res.status_code == 401 and res.get_json() == {"error": "authentication required"}


def test_new_user_dashboard_page_and_empty_api():
    client = make_user_client(app_mod.app, "newbie")
    page = client.get("/dashboard")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert ", newbie</h1>" in html and "Add documents" in html and "dashboard.js" in html
    assert 'href="/dashboard" class="active"' in html
    data = client.get("/api/dashboard").get_json()
    assert data["review"]["pending"] == 0 and data["posted"]["count"] == 0 and data["activity"] == []


def test_username_is_escaped_on_the_page(monkeypatch):
    # usernames are validated by auth, so render the template directly with a hostile one
    with app_mod.app.test_request_context("/dashboard"):
        from flask import g, render_template
        g.user = None
        html = render_template("dashboard.html", active_page="dashboard",
                               header=dashboard.header("<script>x</script>", NOW))
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html


def test_api_dashboard_counts_this_users_data_only():
    a = make_user_client(app_mod.app, "alice")
    b = make_user_client(app_mod.app, "bobby")
    posted = _enqueue(a, "AAA-POSTED", 111.0)
    _enqueue(a, "AAA-FLAGGED", 5.0, needs_review=True)
    assert a.post("/api/confirm", json={"id": posted}).status_code == 200
    _enqueue(b, "BBB-PENDING", 222.0)

    da = a.get("/api/dashboard").get_json()
    assert da["review"] == {"pending": 1, "flagged": 1}
    assert da["posted"]["count"] == 1 and da["posted"]["total"] == 111.0
    assert da["open_value"]["total"] == 5.0
    assert da["acceptance"]["rate"] == 1.0
    assert [r["vendor"] for r in da["needs_review"]] == ["AAA-FLAGGED"]
    assert {e["vendor"] for e in da["activity"]} == {"AAA-POSTED", "AAA-FLAGGED"}
    text_a = a.get("/api/dashboard").get_data(as_text=True) + a.get("/api/dashboard?period=last").get_data(as_text=True)
    assert "BBB" not in text_a and "222" not in text_a

    db = b.get("/api/dashboard").get_json()
    assert db["review"]["pending"] == 1 and db["posted"]["count"] == 0
    assert "AAA" not in b.get("/api/dashboard").get_data(as_text=True)


def test_api_dashboard_period_param_is_whitelisted():
    client = make_user_client(app_mod.app, "carol")
    assert client.get("/api/dashboard?period=last").get_json()["period"] == "last"
    assert client.get("/api/dashboard?period=../../etc").get_json()["period"] == "this"


# ---- landing after sign-in --------------------------------------------------------

def test_password_login_lands_on_dashboard():
    auth.create_user("carol", PASSWORD)
    anon = new_client(app_mod.app)
    token = anon.page_token("/login")
    res = anon.post("/login", data={"username": "carol", "password": PASSWORD, "csrf_token": token})
    assert res.status_code == 302 and res.headers["Location"] == "/dashboard"


def test_opening_the_root_signs_in_to_dashboard_but_deep_links_are_kept():
    anon = new_client(app_mod.app)
    assert anon.get("/").headers["Location"] == "/login?next=/dashboard"
    assert anon.get("/ledger").headers["Location"] == "/login?next=/ledger"


def test_signup_lands_on_dashboard(monkeypatch):
    monkeypatch.setenv("VAULT_ALLOW_SIGNUP", "1")
    anon = new_client(app_mod.app)
    token = anon.page_token("/signup")
    res = anon.post("/signup", data={"username": "newuser", "password": PASSWORD, "password2": PASSWORD,
                                     "csrf_token": token})
    assert res.status_code == 302 and res.headers["Location"] == "/dashboard"


def test_continue_without_signing_in_lands_on_dashboard(monkeypatch):
    """The desktop flow: the window opens "/", is sent to the sign-in page, and
    the "Continue without signing in" form carries the landing page along."""
    monkeypatch.setenv("VAULT_SKIP_LOGIN", "1")
    client = new_client(app_mod.app)
    login_url = client.get("/").headers["Location"]
    html = client.get(login_url).get_data(as_text=True)
    assert 'name="next" value="/dashboard"' in html
    token = client.page_token(login_url)
    res = client.post("/login/skip", data={"csrf_token": token, "next": "/dashboard"})
    assert res.status_code == 302 and res.headers["Location"] == "/dashboard"
    # and with no next at all (a stale form), it still lands there
    other = new_client(app_mod.app)
    res = other.post("/login/skip", data={"csrf_token": other.page_token("/login")})
    assert res.headers["Location"] == "/dashboard"
    assert client.get("/dashboard").status_code == 200
    assert security.SKIP_LOGIN_USERNAME in client.get("/dashboard").get_data(as_text=True)
