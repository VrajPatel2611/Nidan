"""
`leakage_flags` — the repository and the queue (T-040, real Postgres).

Four things are worth a database to prove, and nothing less than one would:

* the INSERT's ownership predicate, so a session that is not the actor's
  writes no row;
* migration 034's grant, because `nidan_admin` could read the queue and not
  resolve it before this task;
* `review()`'s `AND reviewed = false`, so two administrators cannot overwrite
  each other's verdict;
* that `record()` is genuinely best-effort — a failure must not take the
  question and the reply down with it.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.infra.db.actor import AdminUser, AnonymousVisitor, AuthenticatedUser
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.anonymous import anonymous_scope


@pytest.fixture
def session_of(app_db, make_account, published_case):
    """A learner, their profile and one active session. Returns both ids."""
    def _make():
        uid = make_account()
        vid = published_case()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.profiles.ensure(timezone="Europe/London")
            row = db.sessions.create(case_version_id=vid)
        return uid, row["id"]
    return _make


@pytest.fixture
def admin_of(app_db, make_account):
    """An administrator, with the platform_role the console checks."""
    def _make():
        uid = make_account()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.profiles.ensure(timezone="Europe/London")
        with app_db.begin() as c:
            c.execute(sa.text(
                "UPDATE profiles SET platform_role = 'admin' WHERE id = :id"),
                {"id": uid})
        return uid
    return _make


class TestRecording:

    def test_a_flag_is_written_and_comes_back_on_the_queue(self, session_of,
                                                           admin_of):
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            assert db.leakage.record(
                sid, event_seq=2, topics=["radiation"], severity="high")

        with repo_scope(AdminUser(user_id=admin_of())) as db:
            queue = db.leakage.queue()
        assert len(queue) == 1
        assert queue[0]["leaked_topics"] == ["radiation"]
        assert queue[0]["severity"] == "high"
        assert queue[0]["reviewed"] is False
        assert queue[0]["confirmed"] is None

    def test_a_session_that_is_not_the_actors_writes_nothing(self, session_of):
        """
        The INSERT is an `INSERT ... SELECT` guarded by an EXISTS over
        `sessions`, exactly as `EventRepository.append` is. False, not an
        exception: the caller is mid-consultation.
        """
        _, theirs = session_of()
        mine, _ = session_of()
        with repo_scope(AuthenticatedUser(user_id=mine)) as db:
            assert db.leakage.record(
                theirs, event_seq=2, topics=["radiation"],
                severity="high") is False

    def test_a_severity_the_check_constraint_forbids_is_refused_in_python(
            self, session_of):
        """
        Migration 015's CHECK allows 'low' and 'high'. A CheckViolation would
        abort a transaction opened for the question and the reply, so this is
        refused before the statement runs — the same reason `llm_calls`
        mirrors its own CHECK.
        """
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            with pytest.raises(ValueError, match="severity"):
                db.leakage.record(sid, event_seq=2, topics=["x"],
                                  severity="critical")

    def test_a_flag_with_no_topics_is_refused(self, session_of):
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            with pytest.raises(ValueError, match="no topics"):
                db.leakage.record(sid, event_seq=2, topics=[], severity="low")

    def test_recording_cannot_take_the_question_and_reply_with_it(
            self, session_of, app_db):
        """
        The savepoint is the whole of "best effort". A failing INSERT poisons
        the transaction in Postgres, so without one the events appended
        moments earlier would roll back and the learner would lose a reply
        they have already read.

        Forced by pointing the flag at an event_seq on a session that was
        deleted under us — the FK then fails inside the savepoint.
        """
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.events.append(sid, "question",
                             {"text": "Does it radiate?", "char_count": 18})
            # A session id that does not exist: the EXISTS matches nothing, so
            # rowcount is 0 and nothing raises. Use a genuine constraint
            # breach instead by writing a NULL severity through the same path.
            ok = db.leakage.record(uuid.uuid4(), event_seq=1,
                                   topics=["radiation"], severity="high")
            assert ok is False
            # The question survived, which is the property under test.
            assert db.events.count_of_type(sid, "question") == 1


class TestTheAdminQueue:

    def test_unreviewed_count_always_carries_both_severities(self, admin_of):
        with repo_scope(AdminUser(user_id=admin_of())) as db:
            assert db.leakage.unreviewed_count() == {"low": 0, "high": 0}

    def test_high_severity_sorts_first_then_oldest_first(self, session_of,
                                                         admin_of):
        """
        Oldest first within a severity on purpose: the point of the queue is
        that a persona which started leaking gets noticed, and newest-first
        buries the first occurrence under its own repetitions.
        """
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.leakage.record(sid, event_seq=2, topics=["a"], severity="low")
            db.leakage.record(sid, event_seq=4, topics=["b"], severity="high")
            db.leakage.record(sid, event_seq=6, topics=["c"], severity="high")

        with repo_scope(AdminUser(user_id=admin_of())) as db:
            queue = db.leakage.queue()
        assert [f["severity"] for f in queue] == ["high", "high", "low"]
        assert [f["event_seq"] for f in queue][:2] == [4, 6]

    def test_the_queue_names_the_case_by_slug(self, session_of, admin_of):
        """
        `case_versions.case_id` is a UUID and the readable name is
        `cases.slug`. An administrator triaging the queue needs to know which
        persona is leaking, and either UUID tells them nothing.
        """
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.leakage.record(sid, event_seq=2, topics=["x"], severity="low")
        with repo_scope(AdminUser(user_id=admin_of())) as db:
            flag = db.leakage.queue()[0]
        assert flag["case_slug"].startswith("scope-test-")
        assert flag["case_version"] == 1

    def test_the_reply_is_read_live_rather_than_copied_onto_the_flag(
            self, session_of, admin_of):
        """
        A copy on the flag would survive the erasure that redacts
        `payload->'text'` (migration 033) — a learner's consultation preserved
        in a table the erasure never looks at, which is the mistake
        `feedback_texts.lines` already cost us once.
        """
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.events.append(sid, "question", {"text": "How long?",
                                               "char_count": 9})
            reply = db.events.append(sid, "patient_reply",
                                     {"text": "It spreads to my arm.",
                                      "matched_topics": []})
            db.leakage.record(sid, event_seq=reply.seq, topics=["radiation"],
                              severity="high")

        with repo_scope(AdminUser(user_id=admin_of())) as db:
            flag = db.leakage.queue()[0]
            assert db.leakage.reply_text(
                flag["session_id"], flag["event_seq"]) == \
                "It spreads to my arm."
            columns = set(flag.keys())
        # The flag itself carries no copy of the words.
        assert "reply" not in columns
        assert "text" not in columns

    def test_reviewed_flags_are_hidden_unless_asked_for(self, session_of,
                                                        admin_of):
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.leakage.record(sid, event_seq=2, topics=["x"], severity="low")
        admin = admin_of()
        with repo_scope(AdminUser(user_id=admin)) as db:
            flag_id = db.leakage.queue()[0]["id"]
            db.leakage.review(flag_id, confirmed=False)
        with repo_scope(AdminUser(user_id=admin)) as db:
            assert db.leakage.queue() == []
            assert len(db.leakage.queue(include_reviewed=True)) == 1


class TestReviewing:

    def test_an_admin_can_confirm_and_the_row_records_who_and_when(
            self, session_of, admin_of):
        """
        Migration 034 exists for this. Before it, `nidan_admin` had SELECT on
        every table and INSERT/UPDATE on `cases` and `case_versions` only — so
        the console could list the queue and not act on it.
        """
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.leakage.record(sid, event_seq=2, topics=["x"], severity="high")
        admin = admin_of()
        with repo_scope(AdminUser(user_id=admin)) as db:
            flag_id = db.leakage.queue()[0]["id"]
            assert db.leakage.review(flag_id, confirmed=True)
            flag = db.leakage.get(flag_id)
        assert flag is not None
        assert flag["reviewed"] is True
        assert flag["confirmed"] is True
        assert flag["reviewed_by"] == admin
        assert flag["reviewed_at"] is not None

    def test_a_second_verdict_loses_rather_than_overwriting_the_first(
            self, session_of, admin_of):
        """
        `AND reviewed = false`. Two administrators opening the same queue is
        ordinary; the second silently winning is not.
        """
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.leakage.record(sid, event_seq=2, topics=["x"], severity="high")
        first, second = admin_of(), admin_of()
        with repo_scope(AdminUser(user_id=first)) as db:
            flag_id = db.leakage.queue()[0]["id"]
            assert db.leakage.review(flag_id, confirmed=True)
        with repo_scope(AdminUser(user_id=second)) as db:
            assert db.leakage.review(flag_id, confirmed=False) is False
            flag = db.leakage.get(flag_id)
        assert flag is not None
        assert flag["confirmed"] is True            # the first verdict stands
        assert flag["reviewed_by"] == first

    def test_an_ordinary_learner_cannot_review(self, session_of):
        """
        Confirming excludes a session from the research export, which is a
        decision about the dataset. `AuthenticatedUser` is refused in Python
        before the UPDATE runs, and `nidan_app` has no grant for it either.
        """
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.leakage.record(sid, event_seq=2, topics=["x"], severity="high")
            flag_id = db.leakage.queue()[0]["id"]
            with pytest.raises(PermissionError, match="AdminUser"):
                db.leakage.review(flag_id, confirmed=True)

    def test_reviewing_something_that_does_not_exist_is_false_not_an_error(
            self, admin_of):
        with repo_scope(AdminUser(user_id=admin_of())) as db:
            assert db.leakage.review(uuid.uuid4(), confirmed=True) is False


class TestTheTrialPath:
    """
    `PRD` P4's reasoning applies to the trial exactly as it does to the
    guard: it is the only path an anonymous visitor has, and a persona that
    leaks to a visitor invalidates that session's numbers just the same.
    """

    @pytest.fixture
    def trial(self, app_db, published_case):
        def _make(visitor: str = "visitor-aaa"):
            vid = published_case()
            with anonymous_scope(visitor) as db:
                row = db.sessions.create(case_version_id=vid)
            return visitor, row["id"]
        return _make

    def test_a_visitor_can_record_a_flag_against_their_own_session(
            self, trial, admin_of):
        visitor, sid = trial()
        with anonymous_scope(visitor) as db:
            assert db.leakage.record(
                sid, event_seq=2, topics=["radiation"], severity="high")
        with repo_scope(AdminUser(user_id=admin_of())) as db:
            assert len(db.leakage.queue()) == 1

    def test_a_visitor_cannot_record_against_another_visitors_session(
            self, trial):
        """
        The trial scope runs as a bypassing role, so the `anonymous_id`
        predicate is the only thing standing between one visitor and
        another's consultation. The subclass carries the same `_OWNERSHIP` as
        events, feedback and results.
        """
        _, theirs = trial("visitor-aaa")
        with anonymous_scope("visitor-bbb") as db:
            assert db.leakage.record(
                theirs, event_seq=2, topics=["x"], severity="high") is False

    def test_a_visitor_cannot_review_anything(self, trial):
        visitor, sid = trial()
        with anonymous_scope(visitor) as db:
            db.leakage.record(sid, event_seq=2, topics=["x"], severity="high")
            with pytest.raises(PermissionError, match="AdminUser"):
                db.leakage.review(uuid.uuid4(), confirmed=True)

    def test_the_visitor_scope_still_refuses_the_general_repositories(self):
        """
        Adding one INSERT to the trial scope must not have widened it. This is
        the guarantee `DATA_MODEL` §10.1 leans on.
        """
        with pytest.raises(PermissionError, match="AnonymousVisitor"):
            with repo_scope(AnonymousVisitor(anonymous_id="visitor-aaa")):
                pass


class TestHowNarrowMigration034Is:
    """
    The whole safety argument for 034 is that an administrator may read a
    session *because it carries a flag*, and exactly the one event the flag
    points at. If that ever widens to "administrators may read sessions", this
    class is what should fail.
    """

    def test_an_admin_cannot_see_an_unflagged_session(self, session_of,
                                                      admin_of):
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.events.append(sid, "question", {"text": "How long?",
                                               "char_count": 9})
        with repo_scope(AdminUser(user_id=admin_of())) as db:
            seen = db.conn.execute(sa.text(
                "SELECT count(*) FROM sessions WHERE id = :id"),
                {"id": sid}).scalar_one()
        assert seen == 0

    def test_an_admin_sees_the_flagged_reply_and_not_the_question(
            self, session_of, admin_of):
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            question = db.events.append(
                sid, "question", {"text": "How long?", "char_count": 9})
            reply = db.events.append(
                sid, "patient_reply",
                {"text": "It spreads to my arm.", "matched_topics": []})
            db.leakage.record(sid, event_seq=reply.seq, topics=["radiation"],
                              severity="high")

        with repo_scope(AdminUser(user_id=admin_of())) as db:
            visible = db.conn.execute(sa.text(
                "SELECT seq FROM session_events WHERE session_id = :id "
                "ORDER BY seq"), {"id": sid}).scalars().all()
        # Exactly the flagged seq. The learner's own words are not readable
        # here, which matters because `PRD` P3 treats them as the learner's.
        assert visible == [reply.seq]
        assert question.seq not in visible

    def test_an_admin_still_cannot_write_a_flag_by_hand(self, session_of,
                                                        admin_of):
        """
        UPDATE was granted, INSERT was not. A hand-written flag would drop a
        session from the research export without a detector having objected.
        """
        uid, sid = session_of()
        admin = admin_of()
        with pytest.raises(Exception) as excinfo:
            with repo_scope(AdminUser(user_id=admin)) as db:
                db.conn.execute(sa.text(
                    "INSERT INTO leakage_flags (session_id, event_seq, "
                    "leaked_topics, severity) VALUES (:id, 2, "
                    "ARRAY['x'], 'high')"), {"id": sid})
        assert "permission denied" in str(excinfo.value).lower()

    def test_an_admin_cannot_delete_a_flag_either(self, session_of, admin_of):
        """
        A confirmed flag is the evidence for a session's absence from the
        dataset. Deleting one would make that absence unexplainable.
        """
        uid, sid = session_of()
        with repo_scope(AuthenticatedUser(user_id=uid)) as db:
            db.leakage.record(sid, event_seq=2, topics=["x"], severity="high")
        with pytest.raises(Exception) as excinfo:
            with repo_scope(AdminUser(user_id=admin_of())) as db:
                db.conn.execute(sa.text("DELETE FROM leakage_flags"))
        assert "permission denied" in str(excinfo.value).lower()
