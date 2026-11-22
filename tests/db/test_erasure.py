"""
Account erasure — API-9, settled 22 Nov 2026 (`DATA_MODEL` §10.2, `ADR-0018`).

Two tests here matter more than the rest, and neither is about the erasure
working.

The first is `TestWhatTheTriggerStillRefuses`. Migration 033 replaced an
unconditional append-only trigger with one that permits a single state
transition, and the value of the decision rests entirely on how narrow that
exception is. A trigger that let a little more through than intended would
still pass every test that only checks the erasure succeeds — so the refusals
are enumerated, one per shape of mutation somebody might plausibly write.

The second is `test_a_patch_cannot_put_the_name_back`. The erasure anonymises
the profile but the user's Supabase token stays valid until the worker deletes
the credential, so for up to 24 hours an erased account can still make
authenticated requests. That window is the part of this design most likely to
be wrong, and the first version of it was: `PATCH /me` wrote the display name
back onto the erased row and then answered 404, so the refusal looked correct
while the data was restored.

Against a real database throughout. Every claim here is about what Postgres
permits, and a mock would be asserting the mock.
"""

from __future__ import annotations

import json
import pathlib
import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from nidan.infra.db.repositories.erasure import REDACTED
from tests.app_config import TEST_SECRET, TRUNCATE_SESSION_TABLES

TYPED = "Has the pain been worse since Tuesday?"


@pytest.fixture
def app(live_db):
    return create_app({"TESTING": True, "SECRET_KEY": TEST_SECRET})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def account(live_db, authority):
    user_id = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                  {"id": user_id})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, country, timezone) "
            "VALUES (:id, 'Test Learner', 'IN', 'UTC')"), {"id": user_id})

    yield user_id, {"Authorization": f"Bearer {authority.token(sub=str(user_id))}"}

    # TRUNCATE before the profile delete: `session_events` refuses DELETE —
    # migration 033 changed what it permits on UPDATE and nothing at all about
    # DELETE — so a cascade into it aborts the whole transaction.
    with live_db.begin() as c:
        c.exec_driver_sql(TRUNCATE_SESSION_TABLES)
        # TRUNCATE, not DELETE: `audit_log` still carries migration 002's
        # unconditional `forbid_mutation`, which is the point of
        # `test_the_audit_log_keeps_the_unconditional_trigger` — so the
        # teardown for a test about erasure is itself refused a DELETE. And
        # before the profile, because `audit_log.actor_id` references it with
        # no ON DELETE.
        c.exec_driver_sql("TRUNCATE audit_log")
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": user_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": user_id})


@pytest.fixture
def consultation(live_db, account):
    """
    A session with one event of every text-bearing type, plus two that carry
    none.

    The two without text are the control: if the redaction's predicate were
    ever widened from `payload ? 'text'`, an examination's `finding` or an
    `input_blocked` reason would start disappearing too, and nothing else here
    would notice.
    """
    user_id, _ = account
    session_id = uuid.uuid4()
    with live_db.begin() as c:
        version = c.execute(sa.text(
            "SELECT id FROM case_versions ORDER BY created_at LIMIT 1")).scalar_one()
        # `ended_at` is not optional: migration 009's `ended_when_terminal`
        # requires it for any status that is not active.
        c.execute(sa.text("""
            INSERT INTO sessions (id, user_id, case_version_id,
                                  sequence_index, status, ended_at)
            VALUES (:id, :uid, :vid, 1, 'completed', now())
        """), {"id": session_id, "uid": user_id, "vid": version})

        rows = [
            ("question",        {"text": TYPED, "char_count": len(TYPED)}),
            ("patient_reply",   {"text": "It has been worse since Tuesday."}),
            ("early_diagnosis", {"text": "stable angina"}),
            ("diagnosis",       {"text": "acute coronary syndrome"}),
            ("examination",     {"key": "cardio", "label": "Cardiovascular",
                                 "finding": "normal heart sounds"}),
            ("input_blocked",   {"reason": "identifier"}),
        ]
        for seq, (etype, payload) in enumerate(rows, start=1):
            c.execute(sa.text("""
                INSERT INTO session_events (session_id, seq, type, payload)
                VALUES (:sid, :seq, CAST(:t AS event_type), CAST(:p AS jsonb))
            """), {"sid": session_id, "seq": seq, "t": etype,
                   "p": json.dumps(payload)})

        c.execute(sa.text("""
            INSERT INTO feedback_texts (session_id, lines, generator)
            VALUES (:sid, :lines, 'llm')
        """), {"sid": session_id,
               # Feedback cites the learner's own words by design (`PRD` P3),
               # which is exactly why §10.2 missing this table mattered.
               "lines": [f'You asked "{TYPED}" and then stopped.']})

    return session_id


def _payloads(live_db, session_id):
    with live_db.begin() as c:
        return {r["type"]: r["payload"] for r in c.execute(sa.text(
            "SELECT type, payload FROM session_events WHERE session_id = :s"),
            {"s": session_id}).mappings().all()}


# ── What the trigger still refuses ───────────────────────────────────

class TestWhatTheTriggerStillRefuses:
    """
    Migration 033's exception, enumerated from the outside.

    Each case is a mutation somebody could reasonably write while "doing an
    erasure", and each must still raise. This is the whole safety argument for
    choosing option (b) over retaining the text: the exception is one fully
    specified transition, not a relaxation.
    """

    @pytest.fixture
    def event_id(self, live_db, consultation):
        with live_db.begin() as c:
            return c.execute(sa.text(
                "SELECT id FROM session_events WHERE session_id = :s "
                "AND type = 'question'"), {"s": consultation}).scalar_one()

    def _refused(self, live_db, statement, params=None):
        with live_db.connect() as c:
            with pytest.raises(sa.exc.ProgrammingError, match="append-only"):
                with c.begin():
                    c.execute(sa.text(statement), params or {})

    def test_delete_has_no_permitted_form_at_all(self, live_db, event_id):
        """
        The redaction exception is for UPDATE only. A missing `seq` is
        indistinguishable from a bug in the writer, and `ADR-0003` makes the
        log the source of truth — a replay with a hole in it is not a replay.
        """
        self._refused(live_db, "DELETE FROM session_events WHERE id = :id",
                      {"id": event_id})

    def test_redacting_to_a_different_value_is_refused(self, live_db, event_id):
        """
        The literal is part of the predicate. Anything else — an empty string,
        '***', a shortened copy of the original — is an edit, and an edit is
        what this table exists not to permit.
        """
        self._refused(live_db, """
            UPDATE session_events
               SET payload = jsonb_set(payload, '{text}', '"gone"')
             WHERE id = :id
        """, {"id": event_id})

    def test_smuggling_a_second_change_into_the_redaction_is_refused(
            self, live_db, event_id):
        """
        The one that would matter most if the predicate were loose. A trigger
        checking only "did text become [redacted]" would wave this through,
        and the row would carry whatever else the statement added.
        """
        self._refused(live_db, """
            UPDATE session_events
               SET payload = jsonb_set(payload, '{text}', '"[redacted]"')
                             || '{"verdict": "correct"}'::jsonb
             WHERE id = :id
        """, {"id": event_id})

    def test_changing_the_sequence_while_redacting_is_refused(
            self, live_db, event_id):
        self._refused(live_db, """
            UPDATE session_events
               SET payload = jsonb_set(payload, '{text}', '"[redacted]"'),
                   seq = seq + 100
             WHERE id = :id
        """, {"id": event_id})

    def test_changing_the_timestamp_while_redacting_is_refused(
            self, live_db, event_id):
        """
        `created_at` is what `DATA_MODEL` §9.3's timing analysis reads. An
        erasure that could move it could rewrite a research result.
        """
        self._refused(live_db, """
            UPDATE session_events
               SET payload = jsonb_set(payload, '{text}', '"[redacted]"'),
                   created_at = now()
             WHERE id = :id
        """, {"id": event_id})

    def test_removing_the_text_key_instead_of_redacting_it_is_refused(
            self, live_db, event_id):
        """
        Dropping the key would be tidier and is not permitted, deliberately.
        `"[redacted]"` announces that text was removed; an absent key is
        indistinguishable from an event that never had one.
        """
        self._refused(live_db, """
            UPDATE session_events SET payload = payload - 'text'
             WHERE id = :id
        """, {"id": event_id})

    def test_an_event_with_no_text_key_cannot_be_given_one(
            self, live_db, consultation):
        """
        `jsonb_set` on a missing key inserts it. Without `OLD.payload ? 'text'`
        in the predicate, an erasure would quietly add a `text` key to every
        examination and `input_blocked` row it passed over.
        """
        self._refused(live_db, """
            UPDATE session_events
               SET payload = jsonb_set(payload, '{text}', '"[redacted]"')
             WHERE session_id = :s AND type = 'examination'
        """, {"s": consultation})

    def test_the_audit_log_keeps_the_unconditional_trigger(self, live_db):
        """
        `audit_log` records that an erasure happened. Granting it the same
        exception would let the record of an erasure be edited by the thing
        performing one, which is the only way an append-only audit log fails
        usefully.
        """
        with live_db.begin() as c:
            fn = c.execute(sa.text("""
                SELECT p.proname FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid
                 WHERE NOT t.tgisinternal AND t.tgrelid = 'audit_log'::regclass
            """)).scalar_one()
        assert fn == "forbid_mutation", (
            "audit_log's trigger changed; migration 033 was supposed to touch "
            "session_events only")

    def test_the_redaction_literal_matches_the_migration(self):
        """
        The trigger compares `NEW.payload` against this exact string. If the
        two ever disagree, every erasure raises "append-only" — API-9's
        original symptom returning under a completely different cause, which
        would send the next person back to a decision that is already made.
        """
        source = (pathlib.Path(__file__).resolve().parents[2]
                  / "migrations" / "versions" / "033_erasure.py")
        assert f'REDACTED = "{REDACTED}"' in source.read_text()


# ── The erasure itself ───────────────────────────────────────────────

def test_the_endpoint_erases_and_returns_202(client, account, consultation,
                                             live_db):
    """
    202, not 204. §4 said 204 and `UX_SPEC` S-20 said "within 24 h"; the three
    remaining steps are outbound calls we do not own, so the screen was right
    and the contract was the thing out of step.
    """
    _, headers = account
    r = client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)
    assert r.status_code == 202, r.get_json()
    body = r.get_json()
    assert body["status"] == "erased"
    # S-20's "what we keep, and why" travels with the response, not only on
    # the screen that preceded it.
    assert body["retained"]


def test_every_word_the_learner_typed_is_gone(client, account, consultation,
                                              live_db):
    """
    Read back out of Postgres rather than inferred from the response, and
    across every payload in the session rather than the ones expected to
    change — the same approach as T-035's guard test, for the same reason.
    """
    _, headers = account
    client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)

    everything = str(_payloads(live_db, consultation))
    assert TYPED not in everything
    assert "Tuesday" not in everything, (
        "a fragment survived; patient_reply echoes the question it answered, "
        "which is why ADR-0018 redacts it too")

    with live_db.begin() as c:
        lines = c.execute(sa.text(
            "SELECT lines FROM feedback_texts WHERE session_id = :s"),
            {"s": consultation}).scalar_one()
    assert lines == [REDACTED], (
        "feedback prose cites the learner's own questions (PRD P3), so §10.2 "
        "missing this table left their words verbatim in it")


def test_the_structure_survives_the_text(client, account, consultation,
                                         live_db):
    """
    §10.3: "Redacted, structure kept". The assessment is recomputable for
    everything except topic extraction, and `session_results` already holds
    the computed answer — which is why `DATA_MODEL` §11.7's export, reading
    results only, costs nothing here.
    """
    _, headers = account
    client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)

    payloads = _payloads(live_db, consultation)
    assert payloads["question"]["char_count"] == len(TYPED)
    assert payloads["examination"]["finding"] == "normal heart sounds"
    assert payloads["input_blocked"]["reason"] == "identifier"
    assert len(payloads) == 6, "an event disappeared; redaction is not deletion"


def test_the_profile_is_anonymised_but_the_pseudonym_survives(
        client, account, live_db):
    """
    The `research_pid` retention is the ethical crux of S-20: it is what the
    screen promises to keep, in the same breath as telling the user why.
    """
    user_id, headers = account
    client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)

    with live_db.begin() as c:
        row = c.execute(sa.text("""
            SELECT display_name, country, consent_research, deleted_at,
                   research_pid
              FROM profiles WHERE id = :id
        """), {"id": user_id}).mappings().one()

    assert row["display_name"] is None
    assert row["country"] is None
    assert row["consent_research"] is False
    assert row["deleted_at"] is not None
    assert row["research_pid"] is not None


def test_it_is_recorded_in_the_audit_log_without_the_content(
        client, account, consultation, live_db):
    """
    The only record that survives an erasure, so it has to be both present and
    empty of what it attests to — counts, never content, the same rule as
    `domain/guard.py`.
    """
    user_id, headers = account
    client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)

    with live_db.begin() as c:
        row = c.execute(sa.text("""
            SELECT action, metadata FROM audit_log
             WHERE actor_id = :id ORDER BY id DESC LIMIT 1
        """), {"id": user_id}).mappings().one()

    assert row["action"] == "profile.erased"
    assert row["metadata"]["events_redacted"] == 4, (
        "question, patient_reply, early_diagnosis, diagnosis — and §10.2 "
        "originally listed only two of them")
    assert row["metadata"]["feedback_redacted"] == 1
    assert TYPED not in str(row["metadata"])
    # The worker's remaining job, legible from the record itself.
    assert "auth.users" in row["metadata"]["pending"]


def test_running_it_twice_is_safe(client, account, consultation, live_db):
    """
    The worker may retry after an external call fails, so the database half
    must tolerate a second pass. Migration 033's predicate permits redacting
    an already-redacted row, and `deleted_at` is COALESCEd so the first
    erasure keeps its date.
    """
    _, headers = account
    first = client.delete("/v1/me", json={"confirmation": "DELETE"},
                          headers=headers)
    assert first.status_code == 202
    # The profile is hidden now, so the endpoint answers 404 rather than
    # erasing again — §2.7's 404, which does not confirm the account existed.
    second = client.delete("/v1/me", json={"confirmation": "DELETE"},
                           headers=headers)
    assert second.status_code == 404

    # The statement a worker retry would issue, run again on already-redacted
    # rows. It must not raise: this is the half of idempotency that lives in
    # migration 033's predicate rather than in the repository.
    with live_db.begin() as c:
        again = c.execute(sa.text("""
            UPDATE session_events
               SET payload = jsonb_set(payload, '{text}', '"[redacted]"')
             WHERE session_id = :s AND payload ? 'text'
        """), {"s": consultation})
    assert again.rowcount == 4


# ── The 24-hour window, and what it must not allow ───────────────────

def test_a_patch_cannot_put_the_name_back(client, account, live_db):
    """
    **The window this design is most likely to get wrong.**

    `ADR-0002` means we do not own `auth.users`, so the token stays valid
    until the worker deletes the credential. The first implementation scoped
    `get()` to live profiles but not `update()` — so a PATCH wrote the display
    name back onto the erased row and *then* returned 404, because the row it
    had just written was hidden from the read. The refusal looked right while
    the erasure was being undone.
    """
    user_id, headers = account
    client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)

    r = client.patch("/v1/me", json={"display_name": "Back Again"},
                     headers=headers)
    assert r.status_code == 404

    with live_db.begin() as c:
        name = c.execute(sa.text(
            "SELECT display_name FROM profiles WHERE id = :id"),
            {"id": user_id}).scalar_one()
    assert name is None, "PATCH restored a name onto an erased profile"


def test_an_erased_account_cannot_be_recreated(client, account):
    """
    `POST /me` is idempotent by `ON CONFLICT DO NOTHING`, which against a
    soft-deleted row does nothing at all. 409 `account_deleted` rather than a
    silent success: an erasure a retried sign-up could undo is not an erasure.
    """
    _, headers = account
    client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)

    r = client.post("/v1/me", json={}, headers=headers)
    assert r.status_code == 409, r.get_json()
    assert r.get_json()["error"]["code"] == "account_deleted"


def test_an_erased_account_sees_the_ordinary_404_everywhere(client, account):
    """
    The same 404 as a profile that was never created. §2.7 prefers that to a
    status distinguishing "erased" from "absent", and one filter in
    `ProfileRepository.get()` is what makes every route agree.
    """
    _, headers = account
    client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)

    for method, path in (("get", "/v1/me"), ("get", "/v1/progress"),
                         ("post", "/v1/me/export")):
        r = getattr(client, method)(path, headers=headers)
        assert r.status_code == 404, f"{method.upper()} {path} → {r.status_code}"


# ── The confirmation ─────────────────────────────────────────────────

@pytest.mark.parametrize("body", [
    {}, {"confirmation": "delete"}, {"confirmation": "DELETE "},
    {"confirmation": True},
])
def test_the_confirmation_must_be_exact(client, account, body, live_db):
    """
    §4 requires `{"confirmation": "DELETE"}` and S-20 disables the button
    until it is typed exactly. Checked server-side as well, because a
    destructive endpoint should not rely on a client having implemented the
    guard — and `"delete"` lower-case is the shape a careless client sends.
    """
    user_id, headers = account
    r = client.delete("/v1/me", json=body, headers=headers)
    assert r.status_code == 422, r.get_json()
    assert r.get_json()["error"]["code"] == "confirmation_required"

    with live_db.begin() as c:
        deleted = c.execute(sa.text(
            "SELECT deleted_at FROM profiles WHERE id = :id"),
            {"id": user_id}).scalar_one()
    assert deleted is None, "a refused confirmation still erased the account"


def test_a_stranger_gets_the_same_404_not_someone_elses_erasure(
        client, live_db, authority):
    """
    A token for a user with no profile must not erase anything, and must not
    say whether a profile exists. The erasure is scoped by the actor's own id
    twice over — explicitly and by RLS — so there is nothing for it to reach.
    """
    stranger = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                  {"id": stranger})

    headers = {"Authorization": f"Bearer {authority.token(sub=str(stranger))}"}
    r = client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "not_found"

    with live_db.begin() as c:
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"),
                  {"id": stranger})
