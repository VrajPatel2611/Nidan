"""
T-012 acceptance criterion 2: the policies deny the application, not just a
hand-written psql session.

`test_rls.py` (T-010) proved the policies are correctly written, using a
purpose-built `rls_tester` role. It could not prove anything about the
application, which did not exist yet. These tests go through `repo_scope` --
the real engine, the real pool, the real `SET LOCAL ROLE` -- because the failure
this guards against is not a wrong policy. It is a correct policy that never
applies, which looks exactly like a working system until two users share it.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.infra.db.actor import AuthenticatedUser, ServiceActor
from nidan.infra.db.engine import get_engine
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.anonymous import anonymous_scope


def _user(app_db, make_account) -> uuid.UUID:
    """An account with a profile, created through the repository under test."""
    uid = make_account()
    with repo_scope(AuthenticatedUser(uid)) as db:
        db.profiles.ensure(display_name="Test")
    return uid


# ── the role is the precondition for everything else ─────────────────

def test_the_scope_runs_as_nidan_app_which_cannot_bypass_rls(app_db, make_account):
    """
    Postgres exempts superusers and the table owner from every policy. The
    container's login user is the owner, so without `SET LOCAL ROLE` each test
    below would pass while proving the opposite of what it claims.
    """
    uid = _user(app_db, make_account)
    with repo_scope(AuthenticatedUser(uid)) as db:
        row = db.conn.execute(sa.text("""
            SELECT current_user AS role, r.rolsuper, r.rolbypassrls
            FROM pg_roles r WHERE r.rolname = current_user
        """)).mappings().one()

    assert row["role"] == "nidan_app"
    assert row["rolsuper"] is False
    assert row["rolbypassrls"] is False


def test_auth_uid_matches_the_actor(app_db, make_account):
    """Every policy is written in terms of auth.uid(). If it is NULL they all deny."""
    uid = _user(app_db, make_account)
    with repo_scope(AuthenticatedUser(uid)) as db:
        assert db.conn.execute(sa.text("SELECT auth.uid()")).scalar() == uid


# ── criterion 2: a second user's rows are invisible ──────────────────

def test_a_second_users_session_is_invisible(app_db, make_account, published_case):
    alice, bob = _user(app_db, make_account), _user(app_db, make_account)
    cv = published_case()

    with repo_scope(AuthenticatedUser(alice)) as db:
        session_id = db.sessions.create(cv)["id"]

    with repo_scope(AuthenticatedUser(bob)) as db:
        # By id, which is the strongest form: Bob knows exactly what to ask for.
        assert db.sessions.get(session_id) is None
        assert db.sessions.recent() == []
        assert db.sessions.active() is None


def test_a_second_users_profile_is_invisible(app_db, make_account):
    """
    Asserted against `profiles` directly, not through `db.profiles.get()`.

    `get()` names `WHERE id = :me` since migration 024 made privileged
    profiles mutually visible, so going through it would pass whether or not
    `own_profile` does anything at all. The policy is a property of the
    database and this is the test that says it still bites.
    """
    import sqlalchemy as sa
    alice, bob = _user(app_db, make_account), _user(app_db, make_account)

    for who in (alice, bob):
        with repo_scope(AuthenticatedUser(who)) as db:
            visible = [r[0] for r in db.conn.execute(
                sa.text("SELECT id FROM profiles"))]
            assert visible == [who]
            assert db.profiles.get()["id"] == who


def test_an_admin_reading_its_own_profile_does_not_get_another_admins(
        app_db, make_account):
    """
    The bug this guards was visible on every screen of the console: the
    header greeted whoever signed in by the name of a different
    administrator, because migration 024's
    `privileged_profiles_are_mutually_visible` is OR'd with `own_profile`
    and `.first()` took an arbitrary row.

    Two admins and a reviewer, because the policy covers both roles and a
    test with one of each would pass on an implementation that filtered by
    `platform_role` instead of by id.
    """
    import sqlalchemy as sa

    from nidan.infra.db.actor import AdminUser, ReviewerUser

    one, two = _user(app_db, make_account), _user(app_db, make_account)
    three = _user(app_db, make_account)
    with app_db.begin() as conn:
        for uid, role in ((one, "admin"), (two, "admin"), (three, "reviewer")):
            conn.execute(sa.text(
                "UPDATE profiles SET platform_role = :r, display_name = :n "
                "WHERE id = :id"),
                {"r": role, "n": f"{role}-{uid}", "id": uid})

    for uid, actor in ((one, AdminUser(one)), (two, AdminUser(two)),
                       (three, ReviewerUser(three))):
        with repo_scope(actor) as db:
            # The policy really is wide -- this is what `get()` had to be
            # protected from, not a hypothetical.
            assert len(db.conn.execute(
                sa.text("SELECT id FROM profiles")).all()) == 3
            assert db.profiles.get()["id"] == uid


def test_a_second_user_cannot_touch_someone_elses_session(
        app_db, make_account, published_case):
    """
    Invisible is not the same as unwritable, and the policies must give both --
    `own_sessions` is FOR ALL, so an UPDATE matches no row rather than silently
    editing Alice's.
    """
    alice, bob = _user(app_db, make_account), _user(app_db, make_account)
    cv = published_case()
    with repo_scope(AuthenticatedUser(alice)) as db:
        sid = db.sessions.create(cv)["id"]
        before = db.sessions.get(sid)["last_activity_at"]

    with repo_scope(AuthenticatedUser(bob)) as db:
        db.sessions.touch(sid)          # no error, and no effect

    with repo_scope(AuthenticatedUser(alice)) as db:
        assert db.sessions.get(sid)["last_activity_at"] == before


# ── the pooled-connection case, which is where the real bug lives ────

def test_a_connection_returns_to_the_pool_carrying_no_identity(
        app_db, make_account, published_case):
    """
    The reason `base.assume` uses `SET LOCAL ROLE` and `set_config(..., true)`
    rather than the plain forms.

    Plain `SET` is transactional but not transaction-*scoped*: once the
    transaction commits, the role and the claim persist for the life of the
    connection -- and a pooled connection is handed to whichever request asks
    next. SQLAlchemy's pool resets it with ROLLBACK, which does not undo a
    committed SET.

    Today nothing exploits that, because every scope calls `assume` and
    overwrites the stale values before running a query. That is a thin
    guarantee to rest tenant isolation on: it holds only while no code ever
    touches a pooled connection outside a scope, and it fails silently, in
    production, under load, the first time one does. So the property tested
    here is the durable one -- **a connection carries nothing about its last
    user when it is returned** -- rather than the one that happens to be
    unobservable at this moment.

    This test was written the other way round first, asserting that a second
    scope could not see the first's rows. It passed against plain `SET` too,
    for the reason above, and so proved nothing.
    """
    alice = _user(app_db, make_account)
    cv = published_case()

    with repo_scope(AuthenticatedUser(alice)) as db:
        raw_in_scope = id(db.conn.connection.dbapi_connection)
        db.sessions.create(cv)

    # The same physical connection, now back in the pool and handed out raw.
    # Going through the engine rather than a fresh one is the point: a new
    # connection would answer correctly for the wrong reason.
    with get_engine().connect() as conn:
        raw_after = id(conn.connection.dbapi_connection)
        role = conn.execute(sa.text("SELECT current_user")).scalar()
        claim = conn.execute(sa.text(
            "SELECT current_setting('request.jwt.claim.sub', true)")).scalar()

    assert raw_in_scope == raw_after, (
        "the pool handed out a different connection, so this test proved "
        "nothing about reuse -- check pool settings before trusting it")
    assert role != "nidan_app", (
        "SET ROLE outlived the transaction: the next borrower of this "
        "connection inherits the previous request's role")
    assert not claim, (
        f"auth.uid() still resolves to {claim!r} on a pooled connection: the "
        f"next request to borrow it inherits the previous user's identity")


def test_a_second_scope_is_not_contaminated_by_the_first(
        app_db, make_account, published_case):
    """
    The end-to-end statement of the same property. Weaker than the test above
    -- it cannot fail while `assume` runs first -- but it is the sentence the
    acceptance criterion is written in, so it is worth being able to point at.
    """
    alice, bob = _user(app_db, make_account), _user(app_db, make_account)
    cv = published_case()

    with repo_scope(AuthenticatedUser(alice)) as db:
        sid = db.sessions.create(cv)["id"]

    with repo_scope(AuthenticatedUser(bob)) as db:
        assert db.conn.execute(sa.text("SELECT auth.uid()")).scalar() == bob
        assert db.sessions.get(sid) is None


# ── the service role: the other half of the pair ─────────────────────

def test_a_service_actor_bypasses_rls(app_db, make_account, published_case):
    """
    The mirror of the first test. If `nidan_service` did not bypass, the
    anonymous path would silently return nothing and T-015 would debug the
    wrong layer; if `nidan_app` bypassed too, every test above would be vacuous.
    Asserting both halves is what makes either meaningful.
    """
    alice = _user(app_db, make_account)
    cv = published_case()
    with repo_scope(AuthenticatedUser(alice)) as db:
        sid = db.sessions.create(cv)["id"]

    with repo_scope(ServiceActor("verifying the service role in tests")) as db:
        assert db.conn.execute(sa.text("SELECT current_user")).scalar() == "nidan_service"
        assert db.sessions.get(sid) is not None


def test_a_service_actor_cannot_write_a_row_it_cannot_own(app_db):
    """
    A background job writing a session with a NULL owner produces a row that is
    invisible to RLS forever and belongs to nobody. Better to refuse at the
    boundary than to create it.
    """
    with repo_scope(ServiceActor("checking the ownerless-write guard")) as db:
        with pytest.raises(PermissionError, match="needs an owner"):
            db.sessions.create(uuid.uuid4())


# ── content: read-only, published-only, both belt and braces ─────────

def test_draft_cases_are_invisible_even_to_a_service_actor(app_db, published_case):
    """
    `read_published_cases` does not apply to a bypassing role, and the
    anonymous-trial path runs as exactly that role. The explicit
    `status = 'published'` filter in CaseRepository is what holds here.
    """
    draft = published_case(status="draft")
    with repo_scope(ServiceActor("checking the draft filter without RLS")) as db:
        assert db.cases.content(draft) is None
        assert all(row["id"] != draft for row in db.cases.published())


def test_the_app_role_cannot_write_clinical_content(app_db, make_account,
                                                    published_case):
    """
    Grant-level, not policy-level: migration 020 gives the application SELECT on
    `case_versions` and nothing more, so a bug in a request handler cannot
    rewrite a reviewed case even if it gets as far as issuing the UPDATE.
    """
    uid = _user(app_db, make_account)
    cv = published_case()
    with repo_scope(AuthenticatedUser(uid)) as db:
        with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
            db.conn.execute(sa.text("UPDATE case_versions SET title = 'x' WHERE id = :id"),
                            {"id": cv})


def test_a_published_case_is_readable_by_slug(app_db, make_account, published_case):
    uid = _user(app_db, make_account)
    published_case(slug="scope-test-readable")
    with repo_scope(AuthenticatedUser(uid)) as db:
        assert db.cases.by_slug("scope-test-readable")["title"] == "Scope test case"
        assert db.cases.by_slug("no-such-case") is None


# ── the transaction boundary ─────────────────────────────────────────

def test_an_exception_rolls_the_whole_scope_back(app_db, make_account, published_case):
    """A scope is a unit of work: a later failure must undo the earlier write."""
    uid = _user(app_db, make_account)
    cv = published_case()
    with pytest.raises(RuntimeError):
        with repo_scope(AuthenticatedUser(uid)) as db:
            db.sessions.create(cv)
            raise RuntimeError("something failed after the insert")

    with repo_scope(AuthenticatedUser(uid)) as db:
        assert db.sessions.recent() == []


def test_ensure_profile_is_idempotent(app_db, make_account):
    uid = make_account()
    with repo_scope(AuthenticatedUser(uid)) as db:
        first = db.profiles.ensure(display_name="Vraj")
    with repo_scope(AuthenticatedUser(uid)) as db:
        second = db.profiles.ensure(display_name="ignored on the second call")

    assert first["id"] == second["id"] == uid
    assert second["display_name"] == "Vraj"


# ── schema drift ─────────────────────────────────────────────────────

def test_every_repository_query_still_matches_the_schema(
        app_db, make_account, published_case):
    """
    The drift check `models.py` has been waiting for since T-010, in the form
    the code actually takes.

    That module reserved the right to define SQLAlchemy `Table` objects here
    and diff them against the migrated database. The repositories turned out to
    use textual SQL, so those objects would be used by nothing and would exist
    only to be compared -- a second copy of the schema, which is precisely what
    `models.py` argues against. Executing every query instead tests the same
    property against the thing that ships: a renamed or dropped column fails
    here rather than in whichever request first happens to touch it.

    Every public repository method must appear below. Adding one without a
    caller here means it is never executed against a real schema until
    production runs it.
    """
    uid = _user(app_db, make_account)
    cv = published_case(slug="drift-check")

    with repo_scope(AuthenticatedUser(uid)) as db:
        db.profiles.get()
        db.profiles.ensure(display_name="D", country="IN", timezone="Asia/Kolkata",
                           professional_role="medical_student", year_of_training=4,
                           consent_research=True, consent_version="v1")
        db.profiles.touch_last_active()

        db.cases.published()
        db.cases.by_slug("drift-check")
        db.cases.content(cv)

        session = db.sessions.create(cv, confidence_pre=3)
        db.sessions.get(session["id"])
        db.sessions.recent(limit=5)
        db.sessions.active()
        db.sessions.touch(session["id"])

    with anonymous_scope("drift-visitor") as db:
        trial = db.sessions.create(cv, confidence_pre=2)
        db.sessions.get(trial["id"])
        db.sessions.active()
        db.sessions.touch(trial["id"])


def test_an_unknown_profile_column_is_refused_before_it_reaches_sql(
        app_db, make_account):
    """
    `ensure(**fields)` builds its column list from the caller's keywords. The
    allow-list is what stops a typo becoming a SQL error at runtime -- and what
    stops the keyword argument being an injection point at all.
    """
    uid = make_account()
    with repo_scope(AuthenticatedUser(uid)) as db:
        with pytest.raises(ValueError, match="not a profile column"):
            db.profiles.ensure(is_admin=True)


def test_recent_refuses_an_unbounded_limit(app_db, make_account):
    uid = _user(app_db, make_account)
    with repo_scope(AuthenticatedUser(uid)) as db:
        for bad in (0, 101, -1):
            with pytest.raises(ValueError, match="between 1 and 100"):
                db.sessions.recent(limit=bad)


def test_consent_without_a_version_is_refused(app_db, make_account):
    """
    `consent_recorded_together` (migration 004) would catch this too, as a
    CheckViolation halfway through a request. Refusing it here says what is
    actually wrong: consent to an unnamed document is not consent.
    """
    uid = make_account()
    with repo_scope(AuthenticatedUser(uid)) as db:
        with pytest.raises(ValueError, match="consent_version"):
            db.profiles.ensure(consent_research=True)
