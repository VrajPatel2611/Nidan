"""
`DATA_MODEL` §11.7 — the de-identified research export (T-040 criterion 3).

Criterion 3 reads "confirmed leaks excluded from the research export", and
until this task there was no export, so the criterion could be met on paper by
a query in a document. These tests are what make it a fact.

§11.7 calls its own query "three protections in one": consent is required,
leakage-confirmed sessions are excluded, and `research_pid` is selected rather
than any identifier. One test per protection, plus the two ways the exclusion
could be wrong in the learner's favour.

`session_results` rows are inserted through the admin engine rather than
through `ResultRepository`. Building an `AssessmentResult` would put the
engine's shape between these tests and the thing they are about, which is the
WHERE clause.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.infra.db.actor import AdminUser, AuthenticatedUser, ServiceActor
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.research import COLUMNS, EXPORT_SQL

SERVICE = ServiceActor(reason="research export tests")


@pytest.fixture
def engine_version(app_db):
    """An engine version to attribute results to."""
    with app_db.begin() as c:
        existing = c.execute(sa.text(
            "SELECT id FROM engine_versions ORDER BY created_at LIMIT 1"
        )).scalar()
        if existing is not None:
            return existing
        vid = uuid.uuid4()
        c.execute(sa.text("""
            INSERT INTO engine_versions (id, version, thresholds)
            VALUES (:id, 'test-1', '{}'::jsonb)
        """), {"id": vid})
        return vid


@pytest.fixture
def completed(app_db, make_account, published_case, engine_version):
    """
    A consented learner with one completed, assessed session.

    Returns `(user_id, session_id)`.
    """
    def _make(*, consent: bool = True):
        uid = make_account()
        vid = published_case()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.profiles.ensure(timezone="Europe/London")
            row = db.sessions.create(case_version_id=vid)
            sid = row["id"]
        with app_db.begin() as c:
            # `consent_recorded_together` requires the version and the
            # timestamp alongside the flag -- consent with no record of what
            # was consented to, or when, is not consent.
            c.execute(sa.text("""
                UPDATE profiles
                   SET consent_research = :consent,
                       consent_version = CASE WHEN :consent THEN 'v1' END,
                       consent_at = CASE WHEN :consent THEN now() END
                 WHERE id = :id
            """), {"consent": consent, "id": uid})
            c.execute(sa.text(
                "UPDATE sessions SET status = 'completed', ended_at = now(), "
                "diagnosis_submitted_at = now() WHERE id = :id"), {"id": sid})
            c.execute(sa.text("""
                INSERT INTO session_results (
                    session_id, question_count, examination_count,
                    investigation_count, coverage_pct, topics_hit,
                    topics_missed, diagnosis_submitted, diagnosis_verdict,
                    anchoring_detected, anchoring_score,
                    premature_closure_detected, premature_closure_score,
                    confirmation_bias_detected, confirmation_bias_score,
                    bias_detail, exam_scorecard, investigation_scorecard,
                    key_investigations_done, key_investigations_total,
                    engine_version_id)
                VALUES (:sid, 9, 2, 3, 75.00, ARRAY['radiation'],
                        ARRAY['medications'], 'GERD', 'correct',
                        false, 0.100, true, 0.800, false, 0.200,
                        '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, 2, 4, :ev)
            """), {"sid": sid, "ev": engine_version})
        return uid, sid
    return _make


@pytest.fixture
def flag(app_db, make_account):
    """
    Write a flag against a session and optionally resolve it, as the console
    would. `nidan_service` has no grant on `auth.users` -- Supabase owns that
    table -- so the administrator is created through the admin engine, which
    is what `app_db` is for.
    """
    def _flag(user_id, session_id, *, confirmed: bool | None):
        with repo_scope(AuthenticatedUser(user_id=user_id)) as db:
            db.leakage.record(session_id, event_seq=2, topics=["radiation"],
                              severity="high")
        if confirmed is None:
            return
        admin = make_account()
        with repo_scope(AuthenticatedUser(user_id=admin)) as db:
            db.profiles.ensure(timezone="Europe/London")
        with app_db.begin() as c:
            c.execute(sa.text(
                "UPDATE profiles SET platform_role = 'admin' WHERE id = :id"),
                {"id": admin})
        with repo_scope(AdminUser(user_id=admin)) as db:
            flag_id = db.leakage.queue()[0]["id"]
            db.leakage.review(flag_id, confirmed=confirmed)
    return _flag


class TestTheThreeProtections:

    def test_consent_is_required(self, completed):
        completed(consent=False)
        with repo_scope(SERVICE) as db:
            assert db.research.rows() == []

    def test_a_consented_completed_session_is_exported(self, completed):
        completed(consent=True)
        with repo_scope(SERVICE) as db:
            rows = db.research.rows()
        assert len(rows) == 1
        assert rows[0]["coverage_pct"] is not None

    def test_a_confirmed_leak_excludes_the_session(self, completed, flag):
        """
        T-040 criterion 3, and the only thing that makes confirming a flag
        mean anything.
        """
        uid, sid = completed()
        flag(uid, sid, confirmed=True)
        with repo_scope(SERVICE) as db:
            assert db.research.rows() == []
            assert db.research.excluded_session_count() == 1

    def test_no_identifier_reaches_the_file(self, completed):
        """
        `DATA_MODEL`: "No email column appears — that is deliberate and should
        be preserved in any variation." `research_pid` is the only identifier,
        and the columns are listed one by one so a future migration cannot
        widen the export by adding a column.
        """
        completed()
        with repo_scope(SERVICE) as db:
            rows = db.research.rows()
        keys = set(rows[0].keys())
        assert keys == set(COLUMNS)
        for forbidden in ("email", "user_id", "display_name", "anonymous_id",
                          "diagnosis_submitted", "bias_detail"):
            assert forbidden not in keys
        assert "research_pid" in keys


class TestTheWaysTheExclusionCouldBeWrong:

    def test_an_unreviewed_flag_does_not_exclude(self, completed, flag):
        """
        A detector that could discard its own inconvenient sessions would be
        marking (`ADR-0005`). Only a person's confirmation removes one.
        """
        uid, sid = completed()
        flag(uid, sid, confirmed=None)
        with repo_scope(SERVICE) as db:
            assert len(db.research.rows()) == 1
            assert db.research.excluded_session_count() == 0

    def test_a_dismissed_flag_does_not_exclude(self, completed, flag):
        uid, sid = completed()
        flag(uid, sid, confirmed=False)
        with repo_scope(SERVICE) as db:
            assert len(db.research.rows()) == 1
            assert db.research.excluded_session_count() == 0

    def test_a_high_severity_flag_alone_does_not_exclude(self, completed, flag):
        """
        `severity` is triage, not a verdict. The queue sorts on it; the export
        does not read it at all.
        """
        uid, sid = completed()
        flag(uid, sid, confirmed=None)
        assert "severity" not in EXPORT_SQL
        with repo_scope(SERVICE) as db:
            assert len(db.research.rows()) == 1

    def test_an_incomplete_session_is_not_exported_however_it_is_flagged(
            self, completed, app_db):
        uid, sid = completed()
        with app_db.begin() as c:
            c.execute(sa.text(
                "UPDATE sessions SET status = 'active' WHERE id = :id"),
                {"id": sid})
        with repo_scope(SERVICE) as db:
            assert db.research.rows() == []


class TestWhoMayRunIt:

    def test_a_learner_cannot(self, completed):
        """
        Not because RLS would leak — a learner would see their own row — but
        because a *partial* export is the dangerous one. It looks like the
        dataset and is one learner's slice of it, and nothing in the file
        would say so.
        """
        uid, _ = completed()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            with pytest.raises(PermissionError, match="ServiceActor"):
                db.research.rows()

    def test_an_admin_cannot_either(self, completed):
        uid, _ = completed()
        with repo_scope(ServiceActor(reason="test admin setup")) as db:
            db.conn.execute(sa.text(
                "UPDATE profiles SET platform_role = 'admin' WHERE id = :id"),
                {"id": uid})
        with repo_scope(AdminUser(user_id=uid)) as db:
            with pytest.raises(PermissionError, match="ServiceActor"):
                db.research.rows()

    def test_the_count_is_scoped_the_same_way(self, completed):
        uid, _ = completed()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            with pytest.raises(PermissionError, match="ServiceActor"):
                db.research.excluded_session_count()
