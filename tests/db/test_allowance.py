"""
Case selection and the monthly allowance, end to end (BUILD_PLAN T-017).

`tests/domain/test_selection.py` checks the arithmetic. This file checks what a
request actually does with it: which case comes back, which status code a
blocked learner gets, and that the payload tells them nothing about the case
they are about to reason through.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from nidan.domain.content.cases import get_case
from nidan.infra.db.actor import AuthenticatedUser
from nidan.infra.db.repositories import repo_scope

USER_ID = uuid.UUID("3f7c1b6e-2a4d-4c8f-9b1e-5d6a7c8e9f01")


@pytest.fixture
def client(app_db, authority, fake_llm):
    return create_app({"TESTING": True, "SECRET_KEY": "t017"}).test_client()


@pytest.fixture
def account(app_db):
    def _make(user_id: uuid.UUID = USER_ID, *, tier: str = "free",
              timezone_name: str = "UTC") -> uuid.UUID:
        with app_db.begin() as c:
            c.execute(sa.text(
                "INSERT INTO auth.users (id) VALUES (:id) ON CONFLICT DO NOTHING"),
                {"id": user_id})
        with repo_scope(AuthenticatedUser(user_id)) as db:
            db.profiles.ensure(timezone=timezone_name)
        with app_db.begin() as c:
            c.execute(sa.text(
                "UPDATE profiles SET subscription_tier = CAST(:t AS subscription_tier) "
                "WHERE id = :id"), {"t": tier, "id": user_id})
        return user_id
    return _make


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _start(client, authority, **body):
    return client.post("/v1/sessions", headers=_auth(authority.token()), json=body)


# ── selection ────────────────────────────────────────────────────────

def test_a_published_case_is_selected(client, authority, account, published_case):
    account()
    published_case(slug="selectable")
    r = _start(client, authority)
    assert r.status_code == 201
    assert r.get_json()["is_repeat"] is False


def test_no_published_cases_is_a_friendly_503_not_a_crash(client, authority,
                                                          account):
    """
    FR-3's edge case. Expected in the current database: migration 019 seeded
    all five cases as DRAFTS on purpose, and they stay drafts until a clinician
    approves them (T-023). Selection filters on `status = 'published'`, so it
    correctly finds nothing.
    """
    account()
    r = _start(client, authority)
    assert r.status_code == 503
    assert r.get_json()["error"]["code"] == "no_cases_available"


def test_a_case_already_attempted_is_not_offered_while_others_remain(
        client, authority, account, published_case, app_db):
    """
    Criterion 1, and FR-3's promise that you meet the others first.

    A Pro account, so the monthly limit does not end the loop at three, and the
    session is abandoned between attempts rather than truncated — truncating
    would take `user_case_history` with it, which is the history the test is
    about. (It did, on the first run.)
    """
    user_id = account(tier="pro")
    seen_cv = published_case(slug="already-seen")
    published_case(slug="not-yet-seen")

    with repo_scope(AuthenticatedUser(user_id)) as db:
        case_id = db.selection.case_id_for_version(seen_cv)
        db.selection.record_attempt(case_id, "correct")

    for _ in range(8):
        r = _start(client, authority)
        assert r.status_code == 201
        with app_db.connect() as c:
            slug = c.execute(sa.text("""
                SELECT cs.slug FROM sessions s
                JOIN case_versions cv ON cv.id = s.case_version_id
                JOIN cases cs ON cs.id = cv.case_id
                WHERE s.id = :id"""), {"id": r.get_json()["id"]}).scalar()
        assert slug == "not-yet-seen"
        with app_db.begin() as c:
            c.exec_driver_sql("UPDATE sessions SET status = 'abandoned', "
                              "ended_at = now() WHERE status = 'active'")


def test_when_every_case_is_seen_the_least_recent_comes_back_marked(
        client, authority, account, published_case, app_db):
    """FR-3.2 — and the marking is what stops recall being mistaken for reasoning."""
    user_id = account()
    older = published_case(slug="seen-long-ago")
    newer = published_case(slug="seen-recently")

    with repo_scope(AuthenticatedUser(user_id)) as db:
        for cv in (older, newer):
            db.selection.record_attempt(db.selection.case_id_for_version(cv), "correct")
    with app_db.begin() as c:
        c.execute(sa.text("""
            UPDATE user_case_history SET last_attempt = now() - interval '40 days'
            WHERE case_id = (SELECT case_id FROM case_versions WHERE id = :id)"""),
            {"id": older})

    r = _start(client, authority)
    assert r.status_code == 201
    assert r.get_json()["is_repeat"] is True

    with app_db.connect() as c:
        slug = c.execute(sa.text("""
            SELECT cs.slug FROM sessions s
            JOIN case_versions cv ON cv.id = s.case_version_id
            JOIN cases cs ON cs.id = cv.case_id WHERE s.id = :id"""),
            {"id": r.get_json()["id"]}).scalar()
    assert slug == "seen-long-ago"


def test_the_payload_never_leaks_what_is_being_tested(client, authority,
                                                      account, published_case):
    """
    FR-3.4: the case's true diagnosis, trap and key tests must appear in no
    pre-consultation payload. Checked mechanically, because the day someone
    adds a convenient field is the day this stops being true by inspection.
    """
    account()
    published_case(slug="no-leaks")
    body = _start(client, authority).get_data(as_text=True).lower()

    case = get_case("case_1")
    forbidden = [case["correct_diagnosis"], case["anchor_topic"]]
    forbidden += list(case["accepted_diagnoses"])
    forbidden += [v["label"] for v in case["investigations"].values()
                  if v.get("category") == "key"]

    leaked = [term for term in forbidden if term and term.lower() in body]
    assert not leaked, f"the session payload leaks: {leaked}"


# ── the allowance ────────────────────────────────────────────────────

def test_a_free_learner_is_blocked_at_the_limit_with_a_reset_date(
        client, authority, account, published_case, app_db):
    """
    Criterion 3. The date is in `details` because a block with no date is a
    dead end and a client cannot compute one.
    """
    account(tier="free")
    published_case(slug="limited")

    for _ in range(3):
        assert _start(client, authority).status_code == 201
        with app_db.begin() as c:
            c.exec_driver_sql("UPDATE sessions SET status = 'abandoned', "
                              "ended_at = now() WHERE status = 'active'")

    r = _start(client, authority)
    assert r.status_code == 403
    body = r.get_json()["error"]
    assert body["code"] == "monthly_limit_reached"
    assert body["details"]["resets_at"]
    assert body["details"]["used"] == 3


def test_abandoned_sessions_still_count(client, authority, account,
                                        published_case, app_db):
    """
    `PRD` FR-3's edge cases are explicit. Without this a free learner could
    start, abandon and restart without limit, and the cap would mean nothing.
    """
    account(tier="free")
    published_case(slug="abandon-me")

    assert _start(client, authority).status_code == 201
    with app_db.begin() as c:
        c.exec_driver_sql("UPDATE sessions SET status = 'abandoned', "
                          "ended_at = now()")

    r = client.get("/v1/me", headers=_auth(authority.token()))
    assert r.get_json()["sessions_remaining_this_month"] == 2


def test_a_pro_learner_is_not_capped(client, authority, account,
                                     published_case, app_db):
    account(tier="pro")
    published_case(slug="unlimited")

    for _ in range(5):
        assert _start(client, authority).status_code == 201
        with app_db.begin() as c:
            c.exec_driver_sql("UPDATE sessions SET status = 'abandoned', "
                              "ended_at = now() WHERE status = 'active'")

    r = client.get("/v1/me", headers=_auth(authority.token()))
    assert r.get_json()["sessions_remaining_this_month"] is None


def test_a_session_from_last_month_does_not_count(client, authority, account,
                                                  published_case, app_db):
    account(tier="free")
    published_case(slug="last-month")

    _start(client, authority)
    with app_db.begin() as c:
        c.exec_driver_sql(
            "UPDATE sessions SET started_at = now() - interval '2 months', "
            "status = 'abandoned', ended_at = now()")

    r = client.get("/v1/me", headers=_auth(authority.token()))
    assert r.get_json()["sessions_remaining_this_month"] == 3


def test_the_allowance_is_on_the_profile_and_in_no_session_payload(
        client, authority, account, published_case):
    """
    `PRD` FR-10.2 and P2: remaining allowance belongs on the dashboard, BEFORE
    starting — never during a consultation. A visible counter teaches the
    counter.
    """
    account()
    published_case(slug="no-counter")

    profile = client.get("/v1/me", headers=_auth(authority.token())).get_json()
    assert "sessions_remaining_this_month" in profile

    session_body = _start(client, authority).get_json()
    for leaked in ("sessions_remaining_this_month", "remaining", "limit",
                   "used", "allowance"):
        assert leaked not in session_body


# ── reservation ──────────────────────────────────────────────────────

def test_a_started_case_is_reserved_and_does_not_reroll(
        client, authority, account, published_case):
    """
    Criterion 4 / FR-3.5. The session row IS the reservation: it pins a
    case_version_id, so a refresh cannot roll a different case. A second start
    reports the conflict rather than resolving it — FR-3's edge case wants the
    client to offer resume-or-abandon.
    """
    account()
    published_case(slug="reserved")

    first = _start(client, authority)
    assert first.status_code == 201

    second = _start(client, authority)
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "session_already_active"
    assert second.get_json()["error"]["details"]["session_id"] == first.get_json()["id"]


def test_an_invalid_confidence_is_refused(client, authority, account,
                                          published_case):
    account()
    published_case(slug="confidence")
    assert _start(client, authority, confidence_pre=9).status_code == 422


def test_starting_without_a_profile_says_what_to_do(client, authority, app_db):
    with app_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id) "
                          "ON CONFLICT DO NOTHING"), {"id": USER_ID})
    r = _start(client, authority)
    assert r.status_code == 404


def test_starting_requires_authentication(client, published_case):
    published_case(slug="needs-auth")
    assert client.post("/v1/sessions", json={}).status_code == 401


# ── history ──────────────────────────────────────────────────────────

def test_attempts_accumulate_and_keep_the_best_verdict(app_db, account,
                                                       published_case):
    """
    `user_case_history` had no writer before T-017, which made criterion 1
    unanswerable. `best_verdict` must improve and never regress.
    """
    user_id = account()
    cv = published_case(slug="history")

    with repo_scope(AuthenticatedUser(user_id)) as db:
        case_id = db.selection.case_id_for_version(cv)
        db.selection.record_attempt(case_id, "anchored")
        db.selection.record_attempt(case_id, "correct")
        db.selection.record_attempt(case_id, "other")

    with app_db.connect() as c:
        row = c.execute(sa.text(
            "SELECT times_attempted, best_verdict FROM user_case_history"
        )).mappings().one()
    assert row["times_attempted"] == 3
    assert row["best_verdict"] == "correct", "a later worse attempt overwrote the best"


def test_one_learners_history_does_not_affect_anothers_selection(
        app_db, account, published_case):
    """
    `own_case_history` (migration 021) scopes it. The repository query carries
    no owner clause, so this fails if the policy is inert.
    """
    other_id = uuid.UUID("9a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d")
    account(USER_ID)
    account(other_id)
    cv = published_case(slug="mine-only")

    with repo_scope(AuthenticatedUser(USER_ID)) as db:
        db.selection.record_attempt(db.selection.case_id_for_version(cv), "correct")

    with repo_scope(AuthenticatedUser(other_id)) as db:
        candidates = db.selection.candidates()
    assert all(c["last_attempt"] is None for c in candidates), (
        "another learner's history is visible in this one's candidates")
