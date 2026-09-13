"""
The anonymous trial, and claiming it (BUILD_PLAN T-015, `PRD` FR-2).

Two database constraints do the real work here, and both of them only start
applying at the moment a trial becomes somebody's:

* `owner_is_exclusive` — exactly one of `user_id` / `anonymous_id`, so the
  transfer must happen in one statement.
* `user_sequence_unique` — a PARTIAL index, `WHERE user_id IS NOT NULL`, so it
  does not constrain a trial session at all until it is claimed.

Each has a test that fails if the claim is written the obvious way.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.api.trial import COOKIE_NAME
from nidan.app import create_app
from nidan.infra.db.actor import AnonymousVisitor, AuthenticatedUser, ServiceActor
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.anonymous import anonymous_scope
from nidan.infra.db.repositories.trial import CLAIM_WINDOW_DAYS, TrialRepository

USER_ID = "3f7c1b6e-2a4d-4c8f-9b1e-5d6a7c8e9f01"


@pytest.fixture
def client(app_db, authority, fake_llm):
    return create_app({"TESTING": True, "SECRET_KEY": "t015"}).test_client()


@pytest.fixture
def account(app_db):
    def _make(user_id: str = USER_ID) -> str:
        with app_db.begin() as c:
            c.execute(sa.text(
                "INSERT INTO auth.users (id) VALUES (:id) ON CONFLICT DO NOTHING"),
                {"id": uuid.UUID(user_id)})
        return user_id
    return _make


@pytest.fixture
def trials(app_db):
    """A TrialRepository in a service scope, for tests that act directly."""
    from contextlib import contextmanager

    @contextmanager
    def _open():
        with repo_scope(ServiceActor("trial tests act as the claim path does")) as db:
            yield TrialRepository(db.conn, db.actor)
    return _open


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_trial(anonymous_id: str, case_version_id) -> uuid.UUID:
    with anonymous_scope(anonymous_id) as db:
        return db.sessions.create(case_version_id)["id"]


# ── criterion 1: starting a trial ────────────────────────────────────

def test_starting_a_trial_creates_a_session_and_sets_an_httponly_cookie(
        client, app_db):
    r = client.post("/v1/trial/sessions", json={})
    assert r.status_code == 201

    body = r.get_json()
    assert body["status"] == "active"
    assert body["patient"]["opening_line"]
    # No assessment state, ever, during a consultation (PRD P2, CT-1).
    for forbidden in ("coverage", "question_count", "topics", "score", "readiness"):
        assert forbidden not in body

    cookie = next(c for c in r.headers.getlist("Set-Cookie")
                  if c.startswith(f"{COOKIE_NAME}="))
    assert "HttpOnly" in cookie, "PRD FR-2.3 requires httpOnly"
    assert "SameSite=Lax" in cookie

    with app_db.connect() as c:
        row = c.execute(sa.text(
            "SELECT user_id, anonymous_id, status FROM sessions")).mappings().one()
    assert row["user_id"] is None
    assert row["anonymous_id"]


def test_the_trial_needs_no_authentication(client):
    """The endpoint a stranger hits. A 401 here would defeat the entire point."""
    assert client.post("/v1/trial/sessions", json={}).status_code == 201


def test_an_unknown_case_is_refused(client):
    r = client.post("/v1/trial/sessions", json={"case_id": "case_999"})
    assert r.status_code == 404


# ── criterion 2: one trial per browser ───────────────────────────────

def test_a_second_trial_from_the_same_browser_is_refused(client):
    assert client.post("/v1/trial/sessions", json={}).status_code == 201

    r = client.post("/v1/trial/sessions", json={})
    assert r.status_code == 409
    assert r.get_json()["error"]["code"] == "trial_already_used"


def test_a_different_browser_gets_its_own_trial(client, app_db, authority,
                                                fake_llm):
    """The limit is per identifier, which is per browser — `PRD` FR-2.5."""
    client.post("/v1/trial/sessions", json={})
    other = create_app({"TESTING": True, "SECRET_KEY": "t015"}).test_client()
    assert other.post("/v1/trial/sessions", json={}).status_code == 201

    with app_db.connect() as c:
        assert c.execute(sa.text(
            "SELECT count(DISTINCT anonymous_id) FROM sessions")).scalar() == 2


def test_the_prototype_is_not_limited(client, published_case):
    """
    Decision recorded in the T-015 build log: the one-trial rule is enforced on
    `/v1/trial/sessions`, the contract a real client uses, and not on the
    server-rendered prototype — a development surface with a deletion date
    (T-030). The limit protects revenue, not data, and it is cookie-based, so
    applying it here would cost a cookie-clear per case while authoring content
    and buy nothing.
    """
    assert client.post("/pre_case/case_1", data={
        "participant_id": "P", "year_of_study": "year_3", "confidence": "3"}).status_code == 200
    assert client.post("/pre_case/case_2", data={
        "participant_id": "P", "year_of_study": "year_3", "confidence": "3"}).status_code == 200


# ── criteria 3 and 4: claiming ───────────────────────────────────────

def test_signing_up_claims_the_trial(client, authority, account, app_db):
    """The whole point of FR-2: the work a stranger did becomes theirs."""
    client.post("/v1/trial/sessions", json={})
    account()

    r = client.post("/v1/me", headers=_auth(authority.token()),
                    json={"display_name": "Vraj"})
    assert r.status_code == 201
    assert len(r.get_json()["claimed_session_ids"]) == 1

    with app_db.connect() as c:
        row = c.execute(sa.text(
            "SELECT user_id, anonymous_id FROM sessions")).mappings().one()
    assert str(row["user_id"]) == USER_ID
    assert row["anonymous_id"] is None, "owner_is_exclusive: only one owner"


def test_the_cookie_is_cleared_once_the_trial_is_claimed(client, authority,
                                                         account):
    """
    Otherwise the browser still looks mid-trial, and the next
    POST /trial/sessions answers 409 to somebody who has already signed up.
    """
    client.post("/v1/trial/sessions", json={})
    account()
    r = client.post("/v1/me", headers=_auth(authority.token()), json={})

    cleared = [c for c in r.headers.getlist("Set-Cookie")
               if c.startswith(f"{COOKIE_NAME}=")]
    assert cleared and ("Max-Age=0" in cleared[0] or "01 Jan 1970" in cleared[0])


def test_a_trial_older_than_the_window_is_refused_with_its_own_code(
        client, authority, account, app_db, published_case):
    """
    Criterion 3. `trial_expired` was already in the frozen error enum, unused —
    so a client can say "that trial has expired" rather than "something was
    wrong with your request".
    """
    cv = published_case()
    session_id = _make_trial("stale-visitor", cv)
    with app_db.begin() as c:
        c.execute(sa.text(
            "UPDATE sessions SET started_at = now() - make_interval(days => :d) "
            "WHERE id = :id"), {"d": CLAIM_WINDOW_DAYS + 1, "id": session_id})

    account()
    r = client.post("/v1/me", headers=_auth(authority.token()),
                    json={"anonymous_id": "stale-visitor"})
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "trial_expired"

    with app_db.connect() as c:
        assert c.execute(sa.text(
            "SELECT count(*) FROM profiles")).scalar() == 0, (
            "the profile must not be created when the claim is refused")


def test_a_trial_just_inside_the_window_is_claimed(
        client, authority, account, app_db, published_case):
    cv = published_case()
    session_id = _make_trial("recent-visitor", cv)
    with app_db.begin() as c:
        c.execute(sa.text(
            "UPDATE sessions SET started_at = now() - make_interval(days => :d) "
            "WHERE id = :id"), {"d": CLAIM_WINDOW_DAYS - 1, "id": session_id})

    account()
    r = client.post("/v1/me", headers=_auth(authority.token()),
                    json={"anonymous_id": "recent-visitor"})
    assert r.status_code == 201
    assert r.get_json()["claimed_session_ids"] == [str(session_id)]


# ── the two constraints, directly ────────────────────────────────────

def test_claiming_renumbers_so_the_partial_unique_index_holds(
        trials, account, published_case, app_db):
    """
    The trap `user_sequence_unique` sets.

    It is a PARTIAL index — `WHERE user_id IS NOT NULL` — so it does not
    constrain a trial session at all. It begins applying at the instant of
    claiming. Trial sessions are all created with `sequence_index = 1`, so
    claiming one into an account that already has a session numbered 1 would
    violate it. Without renumbering in the same statement, this raises.
    """
    cv = published_case()
    user_id = uuid.UUID(account())

    with repo_scope(AuthenticatedUser(user_id)) as db:
        db.profiles.ensure()
        existing = db.sessions.create(cv)
    assert existing["sequence_index"] == 1

    _make_trial("visitor-with-a-clash", cv)

    with trials() as trial_repo:
        claimed = trial_repo.claim("visitor-with-a-clash", user_id)
    assert len(claimed) == 1

    with app_db.connect() as c:
        numbers = c.execute(sa.text(
            "SELECT sequence_index FROM sessions WHERE user_id = :u "
            "ORDER BY sequence_index"), {"u": user_id}).scalars().all()
    assert numbers == [1, 2], f"expected renumbering, got {numbers}"


def test_several_trials_under_one_identifier_are_numbered_separately(
        trials, account, published_case, app_db):
    """
    The prototype is unlimited, so one identifier can carry several sessions.
    Giving them all `highest + 1` would violate the same index — the renumber
    has to be per row, not per claim.
    """
    cv = published_case()
    user_id = uuid.UUID(account())
    with repo_scope(AuthenticatedUser(user_id)) as db:
        db.profiles.ensure()

    for _ in range(3):
        _make_trial("busy-visitor", cv)

    with trials() as trial_repo:
        claimed = trial_repo.claim("busy-visitor", user_id)
    assert len(claimed) == 3

    with app_db.connect() as c:
        numbers = c.execute(sa.text(
            "SELECT sequence_index FROM sessions WHERE user_id = :u "
            "ORDER BY sequence_index"), {"u": user_id}).scalars().all()
    assert numbers == [1, 2, 3], f"duplicate sequence numbers: {numbers}"


def test_owner_is_exclusive_is_never_violated(trials, account, published_case,
                                              app_db):
    """
    Criterion 4, asserted over the table rather than over one row: no session
    anywhere may end up with both owners or neither.
    """
    cv = published_case()
    user_id = uuid.UUID(account())
    with repo_scope(AuthenticatedUser(user_id)) as db:
        db.profiles.ensure()
    _make_trial("exclusive-visitor", cv)

    with trials() as trial_repo:
        trial_repo.claim("exclusive-visitor", user_id)

    with app_db.connect() as c:
        bad = c.execute(sa.text("""
            SELECT count(*) FROM sessions
            WHERE (user_id IS NOT NULL AND anonymous_id IS NOT NULL)
               OR (user_id IS NULL AND anonymous_id IS NULL)
        """)).scalar()
    assert bad == 0


def test_claiming_twice_is_a_no_op_not_an_error(trials, account,
                                                published_case):
    """
    Two concurrent signups with the same cookie. The second should lose
    quietly: `WHERE user_id IS NULL` matches nothing the second time.
    """
    cv = published_case()
    user_id = uuid.UUID(account())
    with repo_scope(AuthenticatedUser(user_id)) as db:
        db.profiles.ensure()
    _make_trial("double-claim", cv)

    with trials() as trial_repo:
        assert len(trial_repo.claim("double-claim", user_id)) == 1
    with trials() as trial_repo:
        assert trial_repo.claim("double-claim", user_id) == []


def test_one_user_cannot_claim_another_visitors_trial_by_guessing(
        trials, account, published_case):
    """
    The identifier is the only credential on this path, which is why it is a
    uuid4 and why the cookie is httpOnly. A wrong guess claims nothing.
    """
    cv = published_case()
    user_id = uuid.UUID(account())
    with repo_scope(AuthenticatedUser(user_id)) as db:
        db.profiles.ensure()
    _make_trial("the-real-visitor", cv)

    with trials() as trial_repo:
        assert trial_repo.claim("a-guess", user_id) == []
        assert trial_repo.claim("", user_id) == []


def test_a_claimed_session_appears_in_the_users_history(
        client, authority, account, app_db):
    """FR-2.4: *the trial session is claimed and appears in history*."""
    client.post("/v1/trial/sessions", json={})
    account()
    client.post("/v1/me", headers=_auth(authority.token()), json={})

    with repo_scope(AuthenticatedUser(uuid.UUID(USER_ID))) as db:
        history = db.sessions.recent()
    assert len(history) == 1, "the claimed trial is not in the user's history"


def test_the_trial_repository_refuses_a_non_service_actor(app_db):
    """
    Claiming bypasses RLS. The only guard is that the caller had to say so out
    loud, so the type demands it.
    """
    from nidan.infra.db.repositories.base import _transaction

    with _transaction(AnonymousVisitor("someone")) as conn:
        with pytest.raises(PermissionError, match="ServiceActor"):
            TrialRepository(conn, AnonymousVisitor("someone"))


def test_the_repository_refuses_an_expired_trial_on_its_own(
        trials, account, published_case, app_db):
    """
    The claim window is enforced twice: `POST /me` checks it before creating
    the profile, so the user gets `trial_expired` and no side effects, and the
    UPDATE filters on it again.

    That second filter had no test. Deleting it from the SQL broke nothing —
    every window assertion went through the API, which had already refused.
    A guard that cannot fail is indistinguishable from one that is missing, and
    this one is the last line if a future caller reaches the repository
    directly.
    """
    cv = published_case()
    user_id = uuid.UUID(account())
    with repo_scope(AuthenticatedUser(user_id)) as db:
        db.profiles.ensure()

    session_id = _make_trial("long-gone", cv)
    with app_db.begin() as c:
        c.execute(sa.text(
            "UPDATE sessions SET started_at = now() - make_interval(days => :d) "
            "WHERE id = :id"), {"d": CLAIM_WINDOW_DAYS + 1, "id": session_id})

    with trials() as trial_repo:
        assert trial_repo.claim("long-gone", user_id) == []

    with app_db.connect() as c:
        still_anonymous = c.execute(sa.text(
            "SELECT anonymous_id FROM sessions WHERE id = :id"),
            {"id": session_id}).scalar()
    assert still_anonymous == "long-gone"


def test_sessions_for_distinguishes_absent_from_expired(
        trials, published_case, app_db):
    """
    Why `sessions_for` returns rows outside the window rather than filtering
    them out: "there is nothing here" and "there is something, but it is too
    old" are different facts about the user's own work, and they map to
    different answers — carry on, or `trial_expired`.
    """
    cv = published_case()
    session_id = _make_trial("aging-visitor", cv)

    with trials() as trial_repo:
        assert trial_repo.sessions_for("nobody") == []
        assert all(s["claimable"] for s in trial_repo.sessions_for("aging-visitor"))

    with app_db.begin() as c:
        c.execute(sa.text(
            "UPDATE sessions SET started_at = now() - make_interval(days => :d) "
            "WHERE id = :id"), {"d": CLAIM_WINDOW_DAYS + 1, "id": session_id})

    with trials() as trial_repo:
        rows = trial_repo.sessions_for("aging-visitor")
    assert len(rows) == 1 and not rows[0]["claimable"]
