"""
T-043 · the AI operations page (`UX_SPEC` A-08), against a real `llm_calls`.

Seeds a small, hand-computable month and checks every headline figure, so a
query that silently changes meaning fails here rather than on a dashboard
nobody re-derives:

    session A  patient ok ×3 ($0.001 each, 1 s / 2 s / 3 s)  feedback ok ($0.004, 4 s)
    session B  patient ok ($0.002, 5 s)  patient failed ($0)  feedback fallback ($0)
    40 days ago, outside every window: patient ok ($1.00)

    per completed session = ($0.007 + $0.002) / 2 = $0.0045
    error rate            = 1 failed / 7 calls  = 14.3 %
    fallback rate         = 1 / 2 feedback rows = 50.0 %
    leakage rate          = 1 flag / 4 answered replies = 25.0 %
    p95 patient latency   = percentile_cont(0.95) over 1,2,3,5 s = 4.7 s
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from nidan.config import settings
from nidan.infra import budget
from nidan.infra.db.actor import AuthenticatedUser
from nidan.infra.db.repositories import repo_scope
from tests.app_config import TEST_SECRET

ADMIN_ID = uuid.UUID("0000d0d0-0000-4000-8000-00000000ad01")
LEARNER_ID = uuid.UUID("0000d0d0-0000-4000-8000-00000000be02")


@pytest.fixture
def client(app_db):
    return create_app({"TESTING": True, "SECRET_KEY": TEST_SECRET}).test_client()


@pytest.fixture(autouse=True)
def _fresh_budget(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MONTHLY_BUDGET_USD", None)
    budget.reset_cache()
    yield
    budget.reset_cache()


def _profile(app_db, user_id, role="user"):
    with app_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id) "
                          "ON CONFLICT DO NOTHING"), {"id": user_id})
    with repo_scope(AuthenticatedUser(user_id=user_id)) as db:
        db.profiles.ensure(timezone="Europe/London")
    with app_db.begin() as c:
        c.execute(sa.text("UPDATE profiles SET platform_role = CAST(:r AS platform_role) "
                          "WHERE id = :id"), {"r": role, "id": user_id})


@pytest.fixture
def admin(app_db, authority):
    _profile(app_db, ADMIN_ID, "admin")
    return {"Authorization": f"Bearer {authority.token(sub=str(ADMIN_ID))}"}


@pytest.fixture
def month(app_db, published_case):
    _profile(app_db, LEARNER_ID)
    vid = published_case()
    with repo_scope(AuthenticatedUser(user_id=LEARNER_ID)) as db:
        a = db.sessions.create(case_version_id=vid)["id"]
        b = db.sessions.create(case_version_id=vid)["id"]
        db.leakage.record(a, event_seq=2, topics=["radiation"], severity="high")
    rows = [
        (a, "patient", "0.001", 1000, "ok", "0"), (a, "patient", "0.001", 2000, "ok", "0"),
        (a, "patient", "0.001", 3000, "ok", "0"), (a, "feedback", "0.004", 4000, "ok", "0"),
        (b, "patient", "0.002", 5000, "ok", "0"), (b, "patient", "0", 100, "failed", "0"),
        (b, "feedback", "0", 0, "fallback", "0"),
        (None, "patient", "1.00", 900, "ok", "40"),
    ]
    with app_db.begin() as c:
        for sid, purpose, cost, ms, status, age in rows:
            c.execute(sa.text("""
                INSERT INTO llm_calls (session_id, purpose, provider, model,
                    prompt_tokens, output_tokens, cost_usd, latency_ms, status,
                    created_at)
                VALUES (:sid, :p, 'groq', 'openai/gpt-oss-120b', 100, 10, :c,
                        :ms, :st, now() - make_interval(days => :age))
            """), {"sid": sid, "p": purpose, "c": cost, "ms": ms, "st": status,
                   "age": int(age)})


def _page(client, admin, query=""):
    r = client.get(f"/admin/ai{query}", headers=admin)
    assert r.status_code == 200
    return " ".join(r.get_data(as_text=True).split())


class TestRefusalsAndRoutes:

    def test_a_learner_gets_the_console_404(self, client, app_db, authority):
        _profile(app_db, LEARNER_ID)
        learner = {"Authorization": f"Bearer {authority.token(sub=str(LEARNER_ID))}"}
        assert client.get("/admin/ai", headers=learner).data == client.get("/admin/ai").data
        assert client.get("/admin/ai").status_code == 404

    def test_the_old_ops_address_redirects(self, client, admin):
        r = client.get("/admin/ops", headers=admin)
        assert r.status_code == 301 and r.headers["Location"].endswith("/admin/ai")


class TestCriterion1_SpendAndCostPerSession:

    def test_cost_per_completed_session_is_every_call_of_each_completed_one(
            self, client, admin, month):
        page = _page(client, admin)
        assert "$0.0045" in page and "2 completed" in page

    def test_the_window_excludes_older_spend(self, client, admin, month):
        assert "$0.0090 spend" not in _page(client, admin)      # 0.009 is per-session sum
        today = _page(client, admin, "?window=today")
        assert "$0.0090" in today and "$1.0" not in today
        assert "7 calls" in today

    def test_nothing_completed_reads_as_a_dash_not_free(self, client, admin):
        page = _page(client, admin)
        assert "— <" in page or "—</div>" in page.replace(" ", "")
        assert "0 completed" in page

    def test_without_a_budget_it_says_how_to_set_one(self, client, admin, month):
        assert "LLM_MONTHLY_BUDGET_USD" in _page(client, admin)


class TestCriterion2_RatesAndLatencyByModel:

    def test_headline_rates(self, client, admin, month):
        page = _page(client, admin)
        assert "14.3%" in page, "error rate: 1 failed of 7 calls"
        assert "50.0%" in page, "feedback fallback: 1 of 2"
        assert "25.0%" in page, "leakage: 1 flag in 4 answered replies"
        assert "4.7s" in page, "p95 over answered patient turns only"

    def test_the_table_breaks_it_down_by_purpose_and_model(self, client, admin, month):
        page = _page(client, admin)
        assert "openai/gpt-oss-120b" in page
        assert "500 / 50" in page, "tokens in/out for today's 5 patient rows"

    def test_alert_lines_colour_only_what_crossed_them(self, client, admin, month):
        page = _page(client, admin)
        # 50 % fallback > 5 % and 25 % leakage > 2 %: both amber.
        assert page.count('style="color: #fbbf24;">50.0%') == 1
        assert page.count('style="color: #fbbf24;">25.0%') == 1


class TestCriterion3_BudgetAlertAndDegradation:

    def test_eighty_percent_shows_the_alert(self, client, admin, month, monkeypatch):
        monkeypatch.setattr(settings, "LLM_MONTHLY_BUDGET_USD", 0.0112)  # 0.009 → 80.4 %
        page = _page(client, admin)
        assert "80% of this month's budget is spent" in page
        assert "gateway is degraded" not in page
        assert budget.exhausted() is False

    def test_one_hundred_percent_degrades_and_says_so(self, client, admin, month,
                                                      monkeypatch):
        monkeypatch.setattr(settings, "LLM_MONTHLY_BUDGET_USD", 0.009)
        page = _page(client, admin)
        assert "Monthly budget spent: the gateway is degraded" in page
        assert "openai/gpt-oss-20b" in page
        budget.reset_cache()
        assert budget.exhausted() is True, "the gateway's check agrees with the page"

    def test_spend_from_last_month_does_not_count(self, client, admin, month,
                                                  monkeypatch):
        monkeypatch.setattr(settings, "LLM_MONTHLY_BUDGET_USD", 0.5)
        budget.reset_cache()
        assert budget.current().spent == Decimal("0.009")
        assert budget.exhausted() is False, "the $1.00 row is 40 days old"
