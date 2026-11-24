"""
The account jobs worker (BUILD_PLAN T-038).

Against a real database. The whole design rests on what Postgres permits —
`audit_log` refuses UPDATE, so the queue is a difference between two sets of
rows — and a mock of that is a mock of the only thing worth testing.

**The tests that matter here are the ones about running twice.** T-038's
criterion 4 is that "an external call that times out is indistinguishable from
one that failed", so every step has to be safe to re-attempt and a step that
already succeeded must not be re-attempted at all. A worker that works on a
clean run and sends two confirmation emails on a retry has failed at the only
thing a worker has to get right.

Nothing here opens a socket: `identity_admin`'s two functions are replaced.
What is exercised is the queue, the ordering, and what gets recorded.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from nidan.infra.db.actor import AuthenticatedUser, ServiceActor
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.audit import (
    COMPLETION_ACTIONS,
    MAX_ATTEMPTS,
    REQUEST_ACTIONS,
    STEPS,
)
from nidan.jobs import runner
from tests.app_config import TRUNCATE_SESSION_TABLES

ADDRESS = "learner@example.test"
TYPED = "Has the pain been worse since Tuesday?"


@pytest.fixture
def account(live_db):
    """A profile with one completed session, three text events and feedback."""
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                  {"id": user_id})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, country, timezone) "
            "VALUES (:id, 'Test Learner', 'IN', 'UTC')"), {"id": user_id})
        version = c.execute(sa.text(
            "SELECT id FROM case_versions ORDER BY created_at LIMIT 1")
        ).scalar_one()
        c.execute(sa.text("""
            INSERT INTO sessions (id, user_id, case_version_id,
                                  sequence_index, status, ended_at)
            VALUES (:id, :uid, :vid, 1, 'completed', now())
        """), {"id": session_id, "uid": user_id, "vid": version})
        for seq, (etype, payload) in enumerate([
            ("question",      {"text": TYPED, "char_count": len(TYPED)}),
            ("patient_reply", {"text": "Worse since Tuesday."}),
            ("diagnosis",     {"text": "acute coronary syndrome"}),
        ], start=1):
            c.execute(sa.text("""
                INSERT INTO session_events (session_id, seq, type, payload)
                VALUES (:s, :q, CAST(:t AS event_type), CAST(:p AS jsonb))
            """), {"s": session_id, "q": seq, "t": etype,
                   "p": json.dumps(payload)})
        c.execute(sa.text("""
            INSERT INTO feedback_texts (session_id, lines, generator)
            VALUES (:s, ARRAY['You asked 6 of 8 about one cause.'], 'llm')
        """), {"s": session_id})

    yield user_id, session_id

    with live_db.begin() as c:
        c.exec_driver_sql(TRUNCATE_SESSION_TABLES)
        c.exec_driver_sql("TRUNCATE audit_log")
        c.execute(sa.text("DELETE FROM profiles WHERE id = :i"), {"i": user_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :i"), {"i": user_id})


@pytest.fixture
def outbox(tmp_path):
    """Messages land in a tmpdir, never the real `logs/outbox`."""
    with patch.object(runner.settings, "EMAIL_OUTBOX_DIR", str(tmp_path)):
        yield tmp_path


@pytest.fixture
def supabase():
    """The admin API, replaced. Nothing here opens a socket."""
    with patch.object(runner.identity_admin, "fetch_email",
                      return_value=ADDRESS) as fetch, \
         patch.object(runner.identity_admin, "delete_credential") as delete:
        delete.return_value = runner.identity_admin.Deletion(
            status=200, already_absent=False)
        yield fetch, delete


def request_job(user_id, action):
    """Record a request the way the route does — as the user."""
    with repo_scope(AuthenticatedUser(user_id=user_id)) as db:
        db.audit.record(action=action, entity_type="profile",
                        entity_id=user_id, reason="test")


def erasure_request(user_id, **counts):
    with repo_scope(AuthenticatedUser(user_id=user_id)) as db:
        db.audit.record(action="profile.erased", entity_type="profile",
                        entity_id=user_id, reason="test",
                        metadata={"events_redacted": counts.get("events", 3),
                                  "feedback_redacted": counts.get("feedback", 1),
                                  "subscriptions_cancelled": 0})


def actions_for(user_id):
    with repo_scope(ServiceActor(reason="reading back what the worker wrote")) as db:
        return [r["action"] for r in db.audit.for_entity("profile", user_id, 50)]


# ── the export job ──────────────────────────────────────────────────────

class TestExport:

    def test_it_builds_and_emails_and_records_both(self, account, outbox, supabase):
        user_id, _ = account
        request_job(user_id, "profile.export_requested")

        report = runner.run()

        assert report.ok, report.failed
        assert set(actions_for(user_id)) >= {"export.built", "export.emailed"}
        folders = list(outbox.iterdir())
        assert len(folders) == 1
        assert (folders[0] / "nidan-export.json").exists()

    def test_the_export_carries_every_event_the_learner_wrote(
            self, account, outbox, supabase):
        """
        Counted, not merely present.

        The first version keyed the transcript lookup by `UUID` while
        `_jsonable` had already turned each session's id into a `str`, so
        every lookup missed and every transcript came back empty. Nothing
        raised: an empty list is a valid transcript and the file serialised.
        A test asserting the key exists would have passed.
        """
        user_id, _ = account
        request_job(user_id, "profile.export_requested")
        runner.run()

        blob = json.loads(
            (next(outbox.iterdir()) / "nidan-export.json").read_text())
        events = [e for s in blob["sessions"] for e in s["transcript"]]
        assert len(events) == 3, f"3 events written, {len(events)} exported"
        assert any(e["payload"].get("text") == TYPED for e in events)
        assert blob["sessions"][0]["feedback"]["lines"]

    def test_the_export_never_carries_the_research_pseudonym(
            self, account, outbox, supabase):
        """
        `research_pid` links an erased account to retained results. A copy in
        a file the learner keeps hands whoever later reads that file the one
        value that re-identifies the anonymised dataset.
        """
        user_id, _ = account
        request_job(user_id, "profile.export_requested")
        runner.run()
        text = (next(outbox.iterdir()) / "nidan-export.json").read_text()
        assert "research_pid" not in text

    def test_the_export_never_carries_detector_internals(
            self, account, outbox, supabase):
        """
        CT-5 applied to a file. `session_results` has `bias_detail`,
        `anchoring_detected` and six more; the export does not read those
        columns at all, which is a stronger property than filtering them.
        """
        from nidan.api.v1.reasoning import BANNED_VOCABULARY
        user_id, _ = account
        request_job(user_id, "profile.export_requested")
        runner.run()
        text = (next(outbox.iterdir()) / "nidan-export.json").read_text().lower()
        assert not [w for w in BANNED_VOCABULARY if w in text]
        assert "bias_detail" not in text


# ── the erasure job ─────────────────────────────────────────────────────

class TestErasure:

    def test_all_three_steps_run_and_are_recorded(self, account, outbox, supabase):
        user_id, _ = account
        erasure_request(user_id)

        report = runner.run()

        assert report.ok, report.failed
        assert set(actions_for(user_id)) >= set(STEPS["profile.erased"])

    def test_the_email_is_sent_before_the_credential_is_deleted(
            self, account, outbox, supabase):
        """
        `UX_SPEC` S-20: "sent to the old address before it is removed".

        Not a preference — the address lives in `auth.users`, so after the
        deletion there is nothing left to fetch. Asserted by call order
        rather than by reading the step list, because the step list is what
        would be edited by someone changing this.
        """
        fetch, delete = supabase
        order = []
        fetch.side_effect = lambda _: (order.append("fetch"), ADDRESS)[1]
        delete.side_effect = lambda _: (
            order.append("delete"),
            runner.identity_admin.Deletion(status=200, already_absent=False))[1]

        user_id, _ = account
        erasure_request(user_id)
        runner.run()

        assert order == ["fetch", "delete"], (
            "the confirmation must be sent while the address still exists")

    def test_the_confirmation_carries_the_counts_from_the_audit_row(
            self, account, outbox, supabase):
        """
        Read back from `profile.erased`, not recomputed. By now the redaction
        has happened, so recomputing would give zero.
        """
        user_id, _ = account
        erasure_request(user_id, events=51, feedback=2)
        runner.run()

        body = next(
            f / "body.txt" for f in outbox.iterdir()
            if (f / "body.txt").read_text().startswith("Your Nidan account")
        ).read_text()
        assert "51 entries redacted" in body

    def test_the_billing_step_records_that_there_is_no_provider(
            self, account, outbox, supabase):
        """
        Stripe is T-041, so there is nothing to cancel. The row says
        `no_provider_configured` rather than claiming a cancellation —
        `audit_log` survives the erasure and must not contain a false
        statement about it.
        """
        user_id, _ = account
        erasure_request(user_id)
        runner.run()

        with repo_scope(ServiceActor(reason="reading the billing step back")) as db:
            rows = db.audit.for_entity("profile", user_id, 50)
        row = next(r for r in rows
                   if r["action"] == "erasure.billing_cancelled")
        assert row["metadata"]["outcome"] == "no_provider_configured"

    def test_a_step_the_worker_ran_has_no_human_actor(
            self, account, outbox, supabase):
        """
        `actor_id` is NULL. Attributing `erasure.credential_deleted` to the
        user would say they deleted their own Supabase credential, which they
        did not and could not.
        """
        user_id, _ = account
        erasure_request(user_id)
        runner.run()

        with repo_scope(ServiceActor(reason="checking the worker's rows")) as db:
            rows = db.audit.for_entity("profile", user_id, 50)
        for row in rows:
            if row["action"] in COMPLETION_ACTIONS:
                assert row["actor_id"] is None, row["action"]
            if row["action"] in REQUEST_ACTIONS:
                assert row["actor_id"] == user_id


# ── running twice: criterion 4 ──────────────────────────────────────────

class TestRunningItAgain:

    def test_a_second_run_does_nothing(self, account, outbox, supabase):
        user_id, _ = account
        erasure_request(user_id)
        first = runner.run()
        second = runner.run()

        assert len(first.completed) == 3
        assert second.completed == []
        assert second.failed == []

    def test_a_second_run_does_not_send_a_second_email(
            self, account, outbox, supabase):
        """
        The failure mode that matters. A duplicate confirmation to a deleted
        account is both alarming and impossible to answer.
        """
        user_id, _ = account
        erasure_request(user_id)
        runner.run()
        before = len(list(outbox.iterdir()))
        runner.run()
        assert len(list(outbox.iterdir())) == before

    def test_a_failure_part_way_through_keeps_what_succeeded(
            self, account, outbox, supabase):
        """
        The step is the unit of work, not the run. One transaction per run
        would roll back user A's recorded email because user B's failed — and
        then send A's again on the next run.
        """
        fetch, delete = supabase
        delete.side_effect = runner.identity_admin.CredentialDeletionFailed("down")

        user_id, _ = account
        erasure_request(user_id)
        report = runner.run()

        assert not report.ok
        done = set(actions_for(user_id))
        assert "erasure.email_sent" in done
        assert "erasure.billing_cancelled" in done
        assert "erasure.credential_deleted" not in done

        # Recovery: the remaining step alone, and no second email.
        delete.side_effect = None
        delete.return_value = runner.identity_admin.Deletion(
            status=200, already_absent=False)
        emails = len(list(outbox.iterdir()))
        again = runner.run()
        assert again.ok, again.failed
        assert again.completed == [
            f"erasure.credential_deleted for {user_id}"]
        assert len(list(outbox.iterdir())) == emails

    def test_a_later_step_does_not_run_after_an_earlier_one_failed(
            self, account, outbox, supabase):
        """
        Deleting the credential after a failed confirmation email would leave
        the user with no account and no notice. The worker stops the job at
        the first failure for that reason.
        """
        fetch, delete = supabase
        fetch.side_effect = runner.identity_admin.CredentialDeletionFailed("no")

        user_id, _ = account
        erasure_request(user_id)
        runner.run()

        assert delete.call_count == 0
        assert "erasure.credential_deleted" not in set(actions_for(user_id))

    def test_a_timed_out_delete_that_actually_worked_completes(
            self, account, outbox, supabase):
        """
        Supabase answers 404 for a user already gone, and `delete_credential`
        reports that as `already_absent`. Which is how the indistinguishable
        case from criterion 4 resolves itself.
        """
        fetch, delete = supabase
        delete.return_value = runner.identity_admin.Deletion(
            status=404, already_absent=True)

        user_id, _ = account
        erasure_request(user_id)
        report = runner.run()

        assert report.ok
        with repo_scope(ServiceActor(reason="reading the delete step back")) as db:
            rows = db.audit.for_entity("profile", user_id, 50)
        row = next(r for r in rows
                   if r["action"] == "erasure.credential_deleted")
        assert row["metadata"]["already_absent"] is True


# ── giving up: criterion 5 ──────────────────────────────────────────────

class TestGivingUp:

    def test_a_step_stops_being_retried_after_max_attempts(
            self, account, outbox, supabase):
        """
        A permanently stuck job must not be retried for ever, and must not
        make every scheduled run report failure — that is how a monitor gets
        switched off. It becomes `skipped`, which the CLI prints as `stuck`.
        """
        fetch, delete = supabase
        delete.side_effect = runner.identity_admin.CredentialDeletionFailed("down")

        user_id, _ = account
        erasure_request(user_id)
        for _ in range(MAX_ATTEMPTS):
            runner.run()

        final = runner.run()
        assert final.failed == []
        assert final.skipped == [f"erasure.credential_deleted for {user_id}"]
        assert final.ok, "a stuck step must not keep the exit code non-zero"

    def test_each_failure_keeps_its_own_reason(self, account, outbox, supabase):
        """
        Rows, not a counter column — because there is no column to increment,
        and the rows are better: "it has been failing the same way since
        Tuesday" is answerable.
        """
        fetch, delete = supabase
        delete.side_effect = runner.identity_admin.CredentialDeletionFailed(
            "supabase answered 503")

        user_id, _ = account
        erasure_request(user_id)
        runner.run()

        with repo_scope(ServiceActor(reason="reading the failure rows")) as db:
            rows = db.audit.for_entity("profile", user_id, 50)
        failures = [r for r in rows if r["action"] == "job.step_failed"]
        assert len(failures) == 1
        assert "503" in failures[0]["reason"]
        assert failures[0]["metadata"]["step"] == "erasure.credential_deleted"
        assert failures[0]["metadata"]["retryable"] is True

    def test_an_absent_service_key_is_recorded_as_not_retryable(
            self, account, outbox):
        """
        `StepImpossible`, not `StepFailed`. Retrying a missing key five times
        and then giving up looks identical in a log to a flaky network, and
        the two need different responses from whoever reads it.
        """
        user_id, _ = account
        erasure_request(user_id)
        with patch.object(runner.identity_admin.settings,
                          "SUPABASE_SERVICE_ROLE_KEY", ""):
            report = runner.run()

        assert not report.ok
        with repo_scope(ServiceActor(reason="reading the failure row")) as db:
            rows = db.audit.for_entity("profile", user_id, 50)
        failure = next(r for r in rows if r["action"] == "job.step_failed")
        assert failure["metadata"]["retryable"] is False


# ── the queue itself ────────────────────────────────────────────────────

class TestTheQueue:

    def test_a_request_with_no_steps_done_is_pending(self, account):
        user_id, _ = account
        request_job(user_id, "profile.export_requested")
        with repo_scope(ServiceActor(reason="reading the queue")) as db:
            assert any(r["entity_id"] == user_id for r in db.audit.pending())

    def test_a_duplicate_completion_row_does_not_finish_a_job(self, account):
        """
        `count(DISTINCT action)`, not `count(*)`. Two workers racing — which
        nothing here prevents, because `audit_log` rows cannot be claimed —
        would otherwise mark a three-step job done after two steps.
        """
        user_id, _ = account
        erasure_request(user_id)
        service = ServiceActor(reason="simulating a double run")
        with repo_scope(service) as db:
            for _ in range(3):
                db.audit.record_system_step("erasure.email_sent",
                                            entity_id=user_id)
        with repo_scope(service) as db:
            assert any(r["entity_id"] == user_id for r in db.audit.pending())

    def test_the_queue_cannot_be_written_by_a_request_scoped_actor(self, account):
        """
        `record_system_step` writes `actor_id = NULL`, which is exactly what
        `record()`'s docstring exists to prevent a route from doing.
        """
        user_id, _ = account
        with repo_scope(AuthenticatedUser(user_id=user_id)) as db:
            with pytest.raises(PermissionError):
                db.audit.record_system_step("export.built", entity_id=user_id)

    def test_a_request_action_is_not_accepted_as_a_completion(self, account):
        user_id, _ = account
        with repo_scope(ServiceActor(reason="checking the action guard")) as db:
            with pytest.raises(ValueError):
                db.audit.record_system_step("profile.erased", entity_id=user_id)

    def test_every_step_the_vocabulary_declares_has_an_implementation(self):
        """
        Static, and it is the guard against the most likely future mistake:
        adding a step to `STEPS` and not to `runner._perform`. The queue is
        self-healing, so an unimplemented step would make every past request
        pending for ever and fail on each run.
        """
        for action, steps in STEPS.items():
            assert action in REQUEST_ACTIONS
            for step in steps:
                assert step in COMPLETION_ACTIONS
                try:
                    runner._perform(step, uuid.uuid4())
                except runner.StepImpossible as e:
                    assert "no implementation" not in str(e), step
                except Exception:
                    pass   # any other failure means it is implemented


# ── the export is built by the worker, not a request ────────────────────

def test_a_request_scoped_actor_cannot_assemble_an_export(account):
    """
    One caller, one guarantee. The worker runs with RLS off and relies on an
    explicit `WHERE user_id = :uid`; a second, request-scoped path would have
    different protection for the same payload.
    """
    user_id, _ = account
    with repo_scope(AuthenticatedUser(user_id=user_id)) as db:
        with pytest.raises(PermissionError):
            db.export.gather(user_id)
