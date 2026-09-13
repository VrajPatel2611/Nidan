"""
T-012 acceptance criterion 3: the anonymous path is isolated, and separately
tested.

These tests matter more than their length suggests. Everywhere else in Nidan a
forgotten filter is caught by Row-Level Security; here RLS is deliberately
bypassed (`DATA_MODEL` §10.1), so a forgotten filter is a breach. The database
will not help, which means these assertions are the help.

`tests/test_db_access.py::test_every_anonymous_query_filters_on_anonymous_id`
is the other half: this file proves the filters work, that one proves nobody
has written a query without one.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from nidan.infra.db.actor import AnonymousVisitor
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.anonymous import anonymous_scope


def test_the_trial_path_runs_with_rls_bypassed(app_db, published_case):
    """
    Stated as a test because it is a deliberate exception, not an accident.
    Someone reading `own_sessions` and assuming it covers every session would
    be wrong, and this is where they find that out.
    """
    with anonymous_scope("visitor-a") as db:
        row = db.conn.execute(sa.text("""
            SELECT current_user AS role, r.rolbypassrls
            FROM pg_roles r WHERE r.rolname = current_user
        """)).mappings().one()
    assert row["role"] == "nidan_service"
    assert row["rolbypassrls"] is True


def test_a_second_visitor_cannot_see_the_first_session(app_db, published_case):
    """
    The assertion the whole module exists for. Nothing in the database is
    enforcing this -- only `_scoped()`.
    """
    cv = published_case()
    with anonymous_scope("visitor-a") as db:
        sid = db.sessions.create(cv)["id"]

    with anonymous_scope("visitor-b") as db:
        assert db.sessions.get(sid) is None     # by id: b knows what to ask for
        assert db.sessions.active() is None

    with anonymous_scope("visitor-a") as db:
        assert db.sessions.get(sid)["id"] == sid


def test_a_second_visitor_cannot_touch_the_first_session(app_db, published_case):
    cv = published_case()
    with anonymous_scope("visitor-a") as db:
        sid = db.sessions.create(cv)["id"]
        before = db.sessions.get(sid)["last_activity_at"]

    with anonymous_scope("visitor-b") as db:
        db.sessions.touch(sid)

    with anonymous_scope("visitor-a") as db:
        assert db.sessions.get(sid)["last_activity_at"] == before


def test_a_trial_session_has_no_user_and_a_learners_has_no_anonymous_id(
        app_db, published_case):
    """
    `owner_is_exclusive` (migration 009) requires exactly one owner. A row with
    both set could be claimed twice at signup (T-015); a row with neither is
    unreachable from either path.
    """
    cv = published_case()
    with anonymous_scope("visitor-a") as db:
        row = db.sessions.create(cv)
    assert row["anonymous_id"] == "visitor-a"
    assert "user_id" not in row          # the trial repository never selects it

    with anonymous_scope("visitor-a") as db:
        stored = db.conn.execute(sa.text(
            "SELECT user_id, anonymous_id FROM sessions WHERE id = :id"),
            {"id": row["id"]}).mappings().one()
    assert stored["user_id"] is None
    assert stored["anonymous_id"] == "visitor-a"


def test_the_trial_scope_reaches_nothing_but_its_own_consultation(app_db):
    """
    Isolation as a property of the object, not of the reviewer's attention. A
    visitor has no profile, no subscription and no progress, so there is
    nothing for a mistake in a request handler to reach.

    `results` joined the list in T-016 — a trial is a complete case including
    feedback (`PRD` FR-2.2), so it is assessed like any other consultation, and
    the assessment is scoped to the visitor exactly as their events are. It is
    listed here as a decision rather than arriving with a refactor.
    """
    with anonymous_scope("visitor-a") as db:
        assert not hasattr(db, "profiles")
        assert not hasattr(db, "subscriptions")
        assert not hasattr(db, "progress")
        # An allow-list, not a snapshot. It failed when T-013 added `events`,
        # which is the point: anything new a trial visitor can reach should be
        # a decision someone made, not something that arrived with a refactor.
        assert sorted(k for k in vars(db) if not k.startswith("_")) == [
            "actor", "cases", "conn", "engines", "events", "feedback",
            "results", "sessions"]


def test_a_visitor_cannot_open_the_general_repositories(app_db):
    """
    The complement of the test above: closing the other door. Were this
    allowed, every query anyone writes from here on would have to remember the
    filter, and the four-method argument would collapse.
    """
    with pytest.raises(PermissionError, match="anonymous_scope"):
        with repo_scope(AnonymousVisitor("visitor-a")):
            pass


def test_a_visitor_sees_published_cases_but_not_drafts(app_db, published_case):
    """
    The service role bypasses `read_published_cases`, so the only thing keeping
    an unreviewed draft away from a trial visitor is the explicit filter in
    CaseRepository. Trial visitors are the audience least able to report seeing
    something they should not.
    """
    draft = published_case(slug="trial-draft", status="draft")
    published_case(slug="trial-published")

    with anonymous_scope("visitor-a") as db:
        slugs = {row["slug"] for row in db.cases.published()}
        assert "trial-published" in slugs
        assert "trial-draft" not in slugs
        assert db.cases.by_slug("trial-draft") is None
        assert db.cases.content(draft) is None


def test_an_empty_anonymous_id_is_refused(app_db):
    """
    `anonymous_id = ''` matches no row today. It would match every row written
    by a later bug that defaulted the column to an empty string -- and that row
    would then be visible to every visitor at once.
    """
    for bad in ("", "   "):
        with pytest.raises(ValueError, match="non-empty"):
            with anonymous_scope(bad):
                pass


def test_an_exception_rolls_the_trial_scope_back(app_db, published_case):
    cv = published_case()
    with pytest.raises(RuntimeError):
        with anonymous_scope("visitor-a") as db:
            db.sessions.create(cv)
            raise RuntimeError("failed after the insert")

    with anonymous_scope("visitor-a") as db:
        assert db.sessions.active() is None
