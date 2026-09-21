"""
Admin access and the audit log (BUILD_PLAN T-020, backend half).

`UX_SPEC` §12.1 gates the admin console on a platform role and requires that
every admin action writes to `audit_log`. Neither existed: `profiles` had no
privilege column at all, and nothing wrote the table.

The rule these tests defend hardest is the one that looks like a bug:
**every refusal is a 404, never a 403** — and the refusals are indistinguishable
from each other. A 403 tells someone probing that an admin console exists.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from flask import jsonify

from nidan.api.auth import require_admin, require_reviewer
from nidan.app import create_app
from nidan.infra.db.actor import AuthenticatedUser
from nidan.infra.db.repositories import repo_scope

USER_ID = uuid.UUID("3f7c1b6e-2a4d-4c8f-9b1e-5d6a7c8e9f01")
OTHER_ID = uuid.UUID("9a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d")


@pytest.fixture
def account(app_db):
    def _make(user_id: uuid.UUID = USER_ID, *, role: str = "user") -> uuid.UUID:
        with app_db.begin() as c:
            c.execute(sa.text(
                "INSERT INTO auth.users (id) VALUES (:id) ON CONFLICT DO NOTHING"),
                {"id": user_id})
        with repo_scope(AuthenticatedUser(user_id)) as db:
            db.profiles.ensure()
        with app_db.begin() as c:
            c.execute(sa.text(
                "UPDATE profiles SET platform_role = CAST(:r AS platform_role) "
                "WHERE id = :id"), {"r": role, "id": user_id})
        return user_id
    return _make


@pytest.fixture
def client(app_db, authority):
    app = create_app({"TESTING": True, "SECRET_KEY": "t020"})

    @app.get("/admin/ping")
    @require_admin
    def admin_ping():
        return jsonify({"ok": True})

    @app.get("/admin/review")
    @require_reviewer
    def reviewer_ping():
        return jsonify({"ok": True})

    return app.test_client()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── the schema ───────────────────────────────────────────────────────

def test_every_profile_starts_unprivileged(app_db, account):
    """
    NOT NULL DEFAULT 'user'. Privilege is never absent-or-unknown: a NULL here
    would make every access check answer three ways instead of two.
    """
    account()
    with app_db.connect() as c:
        assert c.execute(sa.text("SELECT platform_role FROM profiles")).scalar() == "user"
        assert c.execute(sa.text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name='profiles' AND column_name='platform_role' "
            "AND is_nullable='NO'")).scalar() == 1


def test_the_role_is_an_enum_with_three_values(app_db):
    """
    An enum, not a boolean, because `clinical_reviews.reviewer_id` already
    implies a second privileged kind — T-023 has reviewers opening cases in
    Playtest. A boolean could not express it.
    """
    with app_db.connect() as c:
        values = set(c.execute(sa.text(
            "SELECT unnest(enum_range(NULL::platform_role))::text")).scalars())
    assert values == {"user", "reviewer", "admin"}


def test_an_unknown_role_is_refused_by_the_database(app_db, account):
    account()
    with pytest.raises(sa.exc.DataError):
        with app_db.begin() as c:
            c.execute(sa.text("UPDATE profiles SET platform_role = "
                              "CAST('superuser' AS platform_role)"))


# ── the access rule ──────────────────────────────────────────────────

def test_an_admin_is_served(client, authority, account):
    account(role="admin")
    assert client.get("/admin/ping", headers=_auth(authority.token())).status_code == 200


@pytest.mark.parametrize("role", ["user", "reviewer"])
def test_a_non_admin_gets_404_not_403(client, authority, account, role):
    """
    `UX_SPEC` §12.1 and `API_CONTRACT` §2.7. A 403 says "this exists and you may
    not have it", which tells someone probing that there is a console to
    attack. Do not "fix" this to a 403 because it reads as more correct.
    """
    account(role=role)
    r = client.get("/admin/ping", headers=_auth(authority.token()))
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "not_found"


def test_an_anonymous_visitor_gets_404(client):
    assert client.get("/admin/ping").status_code == 404


def test_every_refusal_is_indistinguishable(client, authority, account):
    """
    The subtler half of the rule. If "not signed in" and "signed in without
    privilege" returned different bodies or codes, the difference would confirm
    the console exists to anyone holding any account — the same leak, quieter.
    """
    account(role="user")
    anonymous = client.get("/admin/ping")
    signed_in = client.get("/admin/ping", headers=_auth(authority.token()))
    expired = client.get("/admin/ping",
                         headers=_auth(authority.token(expires_in=-60)))

    bodies = {r.get_data(as_text=True) for r in (anonymous, signed_in, expired)}
    codes = {r.status_code for r in (anonymous, signed_in, expired)}
    assert codes == {404}
    assert len(bodies) == 1, f"refusals differ and therefore leak: {bodies}"


def test_a_reviewer_reaches_reviewer_routes_and_an_admin_reaches_both(
        client, authority, account):
    account(role="reviewer")
    assert client.get("/admin/review", headers=_auth(authority.token())).status_code == 200

    account(OTHER_ID, role="admin")
    admin = _auth(authority.token(sub=str(OTHER_ID)))
    assert client.get("/admin/review", headers=admin).status_code == 200
    assert client.get("/admin/ping", headers=admin).status_code == 200


def test_the_role_is_read_from_the_profile_not_the_token(
        client, authority, account, app_db):
    """
    Revoking an admin must take effect now, not when their hour-old JWT
    expires. Revocation that waits for a token to expire is not revocation.
    """
    account(role="admin")
    token = authority.token()
    assert client.get("/admin/ping", headers=_auth(token)).status_code == 200

    with app_db.begin() as c:
        c.execute(sa.text("UPDATE profiles SET platform_role = 'user'"))

    assert client.get("/admin/ping", headers=_auth(token)).status_code == 404


def test_a_user_cannot_promote_themselves_through_the_api(
        client, authority, account):
    """
    `POST /me` builds its column list from the caller's keywords against an
    allow-list. `platform_role` is not on it, and must never be.
    """
    account(role="user")
    r = client.post("/v1/me", headers=_auth(authority.token()),
                    json={"platform_role": "admin"})
    assert r.status_code == 422


def test_the_profile_response_never_reveals_the_platform_role(
        client, authority, account):
    """
    The console's existence is not advertised, so neither is membership of it.
    `_profile_json` is built field by field, which is what makes this hold.
    """
    account(role="admin")
    body = client.get("/v1/me", headers=_auth(authority.token())).get_json()
    assert "platform_role" not in body


# ── the audit log ────────────────────────────────────────────────────

def test_an_admin_action_is_recorded(app_db, account):
    user_id = account(role="admin")
    entity = uuid.uuid4()

    with repo_scope(AuthenticatedUser(user_id)) as db:
        db.audit.record("case_version.published", entity_type="case_version",
                        entity_id=entity, reason="clinician approved",
                        metadata={"version": 1})

    with app_db.connect() as c:
        row = c.execute(sa.text("SELECT * FROM audit_log")).mappings().one()
    assert row["actor_id"] == user_id
    assert row["action"] == "case_version.published"
    assert row["reason"] == "clinician approved"
    assert row["metadata"] == {"version": 1}


def test_the_actor_comes_from_the_scope_not_an_argument(app_db, account):
    """
    A caller that could name the actor could attribute an action to someone
    else. An audit log that can be made to lie about who acted is worse than
    none — it is evidence supporting the wrong conclusion.
    """
    import inspect

    from nidan.infra.db.repositories.audit import AuditRepository
    signature = inspect.signature(AuditRepository.record)
    assert "actor_id" not in signature.parameters
    assert "actor" not in signature.parameters


def test_an_audit_row_cannot_be_altered_or_deleted(app_db, account):
    """`forbid_mutation` (migration 015). A revisable audit log is not one."""
    user_id = account(role="admin")
    with repo_scope(AuthenticatedUser(user_id)) as db:
        db.audit.record("profile.viewed", entity_type="profile")

    for statement in ("UPDATE audit_log SET action = 'tampered'",
                      "DELETE FROM audit_log"):
        with pytest.raises(sa.exc.DatabaseError):
            with app_db.begin() as c:
                c.execute(sa.text(statement))


def test_a_malformed_action_is_refused(app_db, account):
    """
    Dotted `entity.verb`, so the log stays sortable and greppable as the set
    of actions grows with every admin screen.
    """
    user_id = account(role="admin")
    with repo_scope(AuthenticatedUser(user_id)) as db:
        for bad in ("published", "", "no_dot_here"):
            with pytest.raises(ValueError, match="dotted"):
                db.audit.record(bad, entity_type="case")
        with pytest.raises(ValueError, match="entity type"):
            db.audit.record("case.published", entity_type="")


def test_history_for_one_entity_comes_back_newest_first(app_db, account):
    user_id = account(role="admin")
    entity = uuid.uuid4()
    with repo_scope(AuthenticatedUser(user_id)) as db:
        for action in ("case.created", "case.edited", "case.published"):
            db.audit.record(action, entity_type="case", entity_id=entity)
        db.audit.record("other.thing", entity_type="other",
                        entity_id=uuid.uuid4())
        rows = db.audit.for_entity("case", entity)

    assert [r["action"] for r in rows] == ["case.published", "case.edited",
                                           "case.created"]
