"""
The authenticated API, end to end (BUILD_PLAN T-014).

`tests/test_auth.py` checks that a token is verified correctly. This file
checks what the API does with the answer: which status, which stable error
code, and — the part T-012 built and nothing had yet used — that an
authenticated request opens a repository scope as that user, so Row-Level
Security applies to real traffic rather than only to tests.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from flask import Flask, jsonify

from nidan.api.auth import current_user_id, require_auth, require_tier
from nidan.app import create_app

USER_ID = "3f7c1b6e-2a4d-4c8f-9b1e-5d6a7c8e9f01"


@pytest.fixture
def account(app_db):
    """
    An `auth.users` row, which Supabase Auth owns in production.

    Created directly because no repository may write it — the application's
    role has no grant on `auth.users`, deliberately (migration 020).
    """
    def _make(user_id: str = USER_ID) -> str:
        with app_db.begin() as c:
            c.execute(sa.text(
                "INSERT INTO auth.users (id) VALUES (:id) ON CONFLICT DO NOTHING"),
                {"id": uuid.UUID(user_id)})
        return user_id
    return _make


@pytest.fixture
def client(app_db, authority):
    return create_app({"TESTING": True, "SECRET_KEY": "t014"}).test_client()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── who may in ───────────────────────────────────────────────────────

def test_no_token_is_unauthenticated(client):
    r = client.get("/v1/me")
    assert r.status_code == 401
    assert r.get_json()["error"]["code"] == "unauthenticated"


def test_an_expired_token_says_so_specifically(client, authority, account):
    """
    Criterion 3. The code matters more than the status: `API_CONTRACT` §3.3
    makes `token_expired` the instruction to refresh and retry once, where a
    plain `unauthenticated` logs the learner out mid-consultation.
    """
    account()
    r = client.get("/v1/me", headers=_auth(authority.token(expires_in=-60)))
    assert r.status_code == 401
    assert r.get_json()["error"]["code"] == "token_expired"


def test_a_token_from_another_project_is_rejected_without_explaining_why(
        client, authority):
    """
    401, and a message that does not say which check failed. "Wrong audience"
    tells someone probing exactly which field to change next.
    """
    r = client.get("/v1/me", headers=_auth(authority.token(audience="someone-else")))
    assert r.status_code == 401
    body = r.get_json()
    assert body["error"]["code"] == "unauthenticated"
    assert "audience" not in body["error"]["message"].lower()


def test_a_malformed_authorization_header_is_rejected(client, authority):
    r = client.get("/v1/me", headers={"Authorization": authority.token()})
    assert r.status_code == 401


def test_the_token_may_arrive_in_the_cookie(client, authority, account):
    """
    `SECURITY_SPEC` L2 keeps tokens in httpOnly cookies; `API_CONTRACT` §2.2
    specifies the header. Both are real — the Next.js server holds the cookie
    and forwards the header — so both are accepted.
    """
    account()
    client.post("/v1/me", headers=_auth(authority.token()), json={})
    client.set_cookie("sb-access-token", authority.token())
    assert client.get("/v1/me").status_code == 200


def test_an_unreachable_key_server_is_503_not_401(client, authority, monkeypatch):
    """
    A 401 would tell every client its credentials are bad and send it into a
    refresh loop against an outage. The credentials may be fine; we cannot
    check them.
    """
    from nidan.infra.auth import jwks
    monkeypatch.setattr(jwks.KeyCache, "_fetch",
                        lambda self: (_ for _ in ()).throw(
                            jwks.JWKSUnavailable("key server down")))
    jwks.cache.clear()

    r = client.get("/v1/me", headers=_auth(authority.token()))
    assert r.status_code == 503
    assert r.get_json()["error"]["code"] == "service_unavailable"


# ── the profile lifecycle ────────────────────────────────────────────

def test_creating_a_profile_is_idempotent(client, authority, account, app_db):
    """Criterion 4. Clients retry and Supabase replays webhooks."""
    account()
    token = authority.token()

    first = client.post("/v1/me", headers=_auth(token),
                        json={"display_name": "Vraj", "timezone": "Asia/Kolkata"})
    assert first.status_code == 201
    assert first.get_json()["display_name"] == "Vraj"

    second = client.post("/v1/me", headers=_auth(token),
                         json={"display_name": "ignored on the second call"})
    assert second.status_code == 200
    assert second.get_json()["display_name"] == "Vraj"

    with app_db.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM profiles")).scalar() == 1


def test_a_profile_is_readable_only_by_its_owner(client, authority, account):
    """
    The first real use of the T-012 machinery: an authenticated request opens
    a scope as that user, so `own_profile` decides what comes back. Two users,
    two profiles, and neither request carries a `WHERE id = ...`.
    """
    other_id = "9a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d"
    account(USER_ID)
    account(other_id)

    client.post("/v1/me", headers=_auth(authority.token(sub=USER_ID)),
                json={"display_name": "First"})
    client.post("/v1/me", headers=_auth(authority.token(sub=other_id)),
                json={"display_name": "Second"})

    a = client.get("/v1/me", headers=_auth(authority.token(sub=USER_ID))).get_json()
    b = client.get("/v1/me", headers=_auth(authority.token(sub=other_id))).get_json()

    assert a["display_name"] == "First"
    assert b["display_name"] == "Second"
    assert a["id"] != b["id"]


def test_reading_before_creating_says_what_to_do(client, authority, account):
    account()
    r = client.get("/v1/me", headers=_auth(authority.token()))
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "not_found"


def test_the_response_never_carries_the_research_pseudonym(
        client, authority, account):
    """
    `research_pid` appears in every analytics and research export and must
    never travel alongside identifying data (`DATA_MODEL` §4.1). A `SELECT *`
    reaching the client is exactly how that happens, which is why the response
    is built field by field.
    """
    account()
    body = client.post("/v1/me", headers=_auth(authority.token()),
                       json={"display_name": "Vraj"}).get_json()
    assert "research_pid" not in body
    assert "email" not in body


def test_an_unknown_field_is_refused(client, authority, account):
    account()
    r = client.post("/v1/me", headers=_auth(authority.token()),
                    json={"subscription_tier": "pro"})
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "validation_failed"


def test_an_unknown_anonymous_id_does_not_block_signup(client, authority, account):
    """
    T-014 refused this outright; T-015 implements claiming, and an identifier
    we have never seen is not a reason to refuse an account. A client that
    always sends its cookie must not be blocked from signing up because the
    cookie is stale — the claim tests live in test_trial.py.
    """
    account()
    r = client.post("/v1/me", headers=_auth(authority.token()),
                    json={"anonymous_id": "never-seen-this-one"})
    assert r.status_code == 201
    assert "claimed_session_ids" not in r.get_json()


# ── tier gating ──────────────────────────────────────────────────────

@pytest.fixture
def tier_client(app_db, authority):
    """
    A throwaway app with one pro-only route.

    Built here rather than added to the product: nothing is pro-gated yet
    (T-017 onwards owns that), and inventing a route to test a decorator would
    leave a route nobody wanted.
    """
    app = create_app({"TESTING": True, "SECRET_KEY": "t014"})

    @app.get("/pro-only")
    @require_tier("pro")
    def pro_only():
        return jsonify({"user": str(current_user_id())})

    return app.test_client()


def test_a_free_user_is_refused_a_pro_route(tier_client, authority, account):
    account()
    tier_client.post("/v1/me", headers=_auth(authority.token()), json={})
    r = tier_client.get("/pro-only", headers=_auth(authority.token()))
    assert r.status_code == 403
    assert r.get_json()["error"]["code"] == "pro_required"


def test_a_pro_user_is_allowed(tier_client, authority, account, app_db):
    """
    The tier is read from the profile, not the token. This test upgrades the
    subscription in the database without reissuing the JWT — which is what
    happens when someone pays mid-session, and what a claims-based check would
    get wrong for an hour.
    """
    account()
    tier_client.post("/v1/me", headers=_auth(authority.token()), json={})
    with app_db.begin() as c:
        c.execute(sa.text("UPDATE profiles SET subscription_tier = 'pro'"))

    r = tier_client.get("/pro-only", headers=_auth(authority.token()))
    assert r.status_code == 200
    assert r.get_json()["user"] == USER_ID


def test_a_user_without_a_profile_is_not_reported_as_a_payment_problem(
        tier_client, authority, account):
    """
    Authenticated, but never called POST /me. Telling them to subscribe would
    send them to a payment page to fix a missing row.
    """
    account()
    r = tier_client.get("/pro-only", headers=_auth(authority.token()))
    assert r.status_code == 404


def test_current_user_id_outside_an_authenticated_route_is_a_bug(app_db):
    """
    A handler that forgets @require_auth must fail loudly here rather than
    quietly treating "no user" as a valid state.
    """
    app = Flask(__name__)
    # Propagate rather than render a 500: the point is that the mistake is
    # loud. Note the client is NOT used as a context manager — that defers the
    # request teardown to the `with` exit, so the exception escapes the
    # pytest.raises block and the test fails while the behaviour is correct.
    app.testing = True

    @app.get("/oops")
    def oops():
        return jsonify({"user": str(current_user_id())})

    with pytest.raises(RuntimeError, match="missing @require_auth"):
        app.test_client().get("/oops")


def test_require_tier_rejects_an_unknown_tier():
    with pytest.raises(ValueError, match="unknown tier"):
        require_tier("enterprise")


def test_require_auth_passes_the_user_through(app_db, authority, account):
    app = create_app({"TESTING": True, "SECRET_KEY": "t014"})

    @app.get("/whoami")
    @require_auth
    def whoami():
        return jsonify({"user": str(current_user_id())})

    account()
    r = app.test_client().get("/whoami", headers=_auth(authority.token()))
    assert r.get_json()["user"] == USER_ID
