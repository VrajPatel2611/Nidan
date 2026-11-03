"""
T-030 slice 5 · progress and account lifecycle (`API_CONTRACT` §4, §7).

Written with slice 4's lesson in mind: assertions here are about **values**,
not shapes. The `cases.content()` bug survived two merged slices because every
check asked whether a key was present, and a dict of Nones answers that
perfectly well. So the streak test crosses a timezone boundary with a known
answer, the trend test pins a direction, and the empty-state test checks a
figure is `None` rather than `0.0`.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from tests.app_config import TEST_SECRET, TRUNCATE_SESSION_TABLES

# `API_CONTRACT` §11's CT-5 terms, spelled out rather than imported from
# `reasoning.BANNED_VOCABULARY`: a test that asks the code what it should hide
# agrees with the code by construction.
# `anchored` is absent on purpose: it is a `diagnosis_verdict` enum value
# that §7's `verdict_distribution` example carries, and §11's CT-5 does
# not list it. Banning it made the progress payload fail its own contract.
CT5_TERMS = ("anchoring", "premature closure", "premature_closure",
             "confirmation bias", "confirmation_bias")

CT4_IDS = ("diagnostic_focus", "history_completeness", "evidence_exploration")


@pytest.fixture
def app(live_db):
    return create_app({"TESTING": True, "SECRET_KEY": TEST_SECRET})


@pytest.fixture
def client(app):
    return app.test_client()


def _make_account(live_db, authority, *, timezone: str = "UTC"):
    user_id = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": user_id})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, timezone) "
            "VALUES (:id, 'Test Learner', :tz)"), {"id": user_id, "tz": timezone})
    return user_id, {"Authorization": f"Bearer {authority.token(sub=str(user_id))}"}


@pytest.fixture
def account(live_db, authority):
    user_id, headers = _make_account(live_db, authority)

    yield user_id, headers

    with live_db.begin() as c:
        c.exec_driver_sql(TRUNCATE_SESSION_TABLES)
        # TRUNCATE, not DELETE: `audit_log` carries the same append-only
        # trigger as `session_events` (migration 002's `forbid_mutation`
        # applied by 015), so a DELETE is refused. And before the profile,
        # because `audit_log.actor_id` references it with no ON DELETE.
        c.exec_driver_sql("TRUNCATE audit_log")
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": user_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": user_id})


@pytest.fixture
def version_id(live_db):
    """Any case version; progress joins it only through `sessions`."""
    with live_db.connect() as c:
        return c.execute(sa.text(
            "SELECT id FROM case_versions ORDER BY created_at LIMIT 1")).scalar_one()


def _completed(live_db, user_id, version_id, *, rows):
    """
    Completed sessions with results, written directly.

    `rows` is a list of (ended_at_sql, coverage_pct, verdict, flags) where
    `flags` is (anchoring, premature, confirmation). Written as SQL rather
    than driven through the API because a hundred sessions would be a hundred
    LLM calls, and what is under test is the aggregate.
    """
    with live_db.begin() as c:
        for i, (ended_sql, coverage, verdict, flags) in enumerate(rows):
            sid = uuid.uuid4()
            c.execute(sa.text(f"""
                INSERT INTO sessions (id, user_id, case_version_id,
                                      sequence_index, status, started_at,
                                      ended_at, diagnosis_submitted_at)
                VALUES (:id, :uid, :vid, :seq, 'completed', {ended_sql},
                        {ended_sql}, {ended_sql})
            """), {"id": sid, "uid": user_id, "vid": version_id, "seq": i + 1})
            a, p, cb = flags
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
                VALUES (:id, 8, 3, 4, :cov, '{}', '{}', 'x', :verdict,
                        :a, 0.5, :p, 0.5, :cb, 0.5,
                        CAST('{}' AS jsonb), CAST('{}' AS jsonb),
                        CAST('{}' AS jsonb), 2, 4,
                        (SELECT id FROM engine_versions WHERE is_current))
            """), {"id": sid, "cov": coverage, "verdict": verdict,
                   "a": a, "p": p, "cb": cb})


# ── §7 · the empty state ─────────────────────────────────────────────

def test_a_learner_with_no_sessions_gets_nulls_not_zeroes(client, account):
    """
    **SUBSTANCE.** `mean_coverage_last10` must be None, not 0.0.

    A learner who has done nothing has no mean coverage; 0% would render as a
    very bad score for someone who has not been scored. `has_sufficient_data`
    is what drives `UX_SPEC` S-16's empty state.
    """
    _, headers = account
    body = client.get("/v1/progress", headers=headers).get_json()

    assert body["sessions_completed"] == 0
    assert body["mean_coverage_last10"] is None, "0.0 would read as a bad score"
    assert body["has_sufficient_data"] is False
    assert body["coverage_series"] == []
    assert body["current_streak_days"] == 0
    assert body["longest_streak_days"] == 0


def test_two_sessions_is_still_not_enough_data(
        client, account, live_db, version_id):
    """
    `UX_SPEC` S-16 wants three. Two points make a line and a line is not a
    trend — a learner shown a direction after two consultations is reading
    noise.
    """
    user_id, headers = account
    _completed(live_db, user_id, version_id, rows=[
        ("now() - interval '2 days'", 40.0, "other", (True, True, False)),
        ("now() - interval '1 day'", 60.0, "correct", (False, True, False)),
    ])
    body = client.get("/v1/progress", headers=headers).get_json()
    assert body["sessions_completed"] == 2
    assert body["has_sufficient_data"] is False
    # The figures are still true and still returned — the flag says how to
    # present them, not whether to compute them.
    assert body["mean_coverage_last10"] == 50.0


def test_three_sessions_is_enough(client, account, live_db, version_id):
    user_id, headers = account
    _completed(live_db, user_id, version_id, rows=[
        (f"now() - interval '{n} days'", 50.0, "correct", (False, False, False))
        for n in (3, 2, 1)
    ])
    assert client.get("/v1/progress",
                      headers=headers).get_json()["has_sufficient_data"] is True


# ── §7 · the series and the distribution ─────────────────────────────

def test_the_coverage_series_runs_oldest_first(
        client, account, live_db, version_id):
    """
    **SUBSTANCE.** Plotted left to right in time, so the order is part of the
    contract — a reversed series would draw every learner's trend backwards
    and still pass a length check.
    """
    user_id, headers = account
    _completed(live_db, user_id, version_id, rows=[
        ("now() - interval '3 days'", 30.0, "other", (True, True, True)),
        ("now() - interval '2 days'", 60.0, "partial", (False, True, False)),
        ("now() - interval '1 day'", 90.0, "correct", (False, False, False)),
    ])
    series = client.get("/v1/progress",
                        headers=headers).get_json()["coverage_series"]
    assert [p["coverage_pct"] for p in series] == [30.0, 60.0, 90.0]
    assert [p["session_index"] for p in series] == [1, 2, 3]
    assert all(p["at"] for p in series)


def test_the_verdict_distribution_carries_every_verdict_at_zero(
        client, account, live_db, version_id):
    """
    **SUBSTANCE.** All four keys, even the ones at zero.

    A client that has to handle a missing key renders differently for a
    learner who has never been wrong, and that is the one learner you least
    want a layout bug for.
    """
    user_id, headers = account
    _completed(live_db, user_id, version_id, rows=[
        ("now() - interval '1 day'", 80.0, "correct", (False, False, False)),
    ])
    dist = client.get("/v1/progress",
                      headers=headers).get_json()["verdict_distribution"]
    assert dist == {"correct": 1, "partial": 0, "anchored": 0, "other": 0}


# ── §7 · streaks, in the learner's own timezone ──────────────────────

def test_substance_a_streak_is_counted_in_the_learners_timezone(
        live_db, authority, app):
    """
    **SUBSTANCE**, and the reason `profiles.timezone` is read at all.

    Two sessions finished 3 hours apart across local midnight in Kolkata
    (UTC+5:30): 20:00 and 23:00 UTC are 01:30 and 04:30 the NEXT local day.
    In UTC that is one day; in Kolkata it is also one day — but shift one
    earlier and the two calendars disagree.

    So: one session at 17:00 UTC and one at 20:00 UTC on the same UTC day are
    22:30 and 01:30 Kolkata — **two** local days, a 2-day streak. A UTC
    calculation would report 1. This test fails if the timezone is dropped.
    """
    user_id, headers = _make_account(live_db, authority, timezone="Asia/Kolkata")
    with live_db.connect() as c:
        version = c.execute(sa.text(
            "SELECT id FROM case_versions ORDER BY created_at LIMIT 1")).scalar_one()
    try:
        _completed(live_db, user_id, version, rows=[
            ("(CURRENT_DATE - 1 + time '17:00') AT TIME ZONE 'UTC'",
             50.0, "correct", (False, False, False)),
            ("(CURRENT_DATE - 1 + time '20:00') AT TIME ZONE 'UTC'",
             50.0, "correct", (False, False, False)),
        ])
        body = app.test_client().get("/v1/progress", headers=headers).get_json()
        assert body["longest_streak_days"] == 2, (
            "17:00 and 20:00 UTC are 22:30 and 01:30 in Kolkata — two local "
            "days. Got "
            f"{body['longest_streak_days']}, which is the UTC answer.")
    finally:
        with live_db.begin() as c:
            c.exec_driver_sql(TRUNCATE_SESSION_TABLES)
            c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": user_id})
            c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": user_id})


def test_a_streak_that_ended_long_ago_is_not_current(
        client, account, live_db, version_id):
    """
    `longest` remembers; `current` does not. A learner who studied for five
    days in September is not on a five-day streak in November.
    """
    user_id, headers = account
    _completed(live_db, user_id, version_id, rows=[
        (f"now() - interval '{n} days'", 50.0, "correct", (False, False, False))
        for n in (40, 39, 38)
    ])
    body = client.get("/v1/progress", headers=headers).get_json()
    assert body["longest_streak_days"] == 3
    assert body["current_streak_days"] == 0


# ── §7 · trends, CT-4 and CT-5 ───────────────────────────────────────

def test_ct5_the_progress_payload_carries_no_bias_vocabulary(
        client, account, live_db, version_id):
    """
    **CT-5**: "No response body **anywhere**".

    The repository's own columns are `anchoring_last10`,
    `premature_closure_prev10` and so on, so a payload assembled from the
    query result would carry the banned words in its field names. The trends
    go through `reasoning.py` for that reason.
    """
    user_id, headers = account
    _completed(live_db, user_id, version_id, rows=[
        (f"now() - interval '{n} days'", 50.0, "anchored", (True, True, True))
        for n in range(1, 6)
    ])
    raw = client.get("/v1/progress",
                     headers=headers).get_data(as_text=True).lower()
    leaked = [term for term in CT5_TERMS if term in raw]
    assert not leaked, f"bias vocabulary in the progress payload: {leaked}"


def test_ct4_trends_use_the_behavioural_identifiers(
        client, account, live_db, version_id):
    user_id, headers = account
    _completed(live_db, user_id, version_id, rows=[
        ("now() - interval '1 day'", 50.0, "correct", (False, False, False)),
    ])
    trends = client.get("/v1/progress",
                        headers=headers).get_json()["reasoning_trends"]
    assert [t["id"] for t in trends] == list(CT4_IDS)
    assert [t["label"] for t in trends] == [
        "Diagnostic focus", "History completeness", "Evidence exploration"]


def test_substance_direction_is_improving_when_the_flag_fires_less(
        client, account, live_db, version_id):
    """
    **SUBSTANCE**, and the arithmetic that reads backwards: fewer flags is
    better, so a FALLING rate is `improving`.

    Twenty sessions. The older ten (positions 11-20) all flagged diagnostic
    focus; the newer ten did not. So last10 = 0.0, prev10 = 1.0, and the
    learner has improved. A sign error here would tell someone who got better
    that they are getting worse.
    """
    user_id, headers = account
    # Oldest first in the list; `_completed` numbers sequence_index in order,
    # and the repository windows by `ended_at DESC`.
    rows = [(f"now() - interval '{30 - n} days'", 50.0, "anchored", (True, False, False))
            for n in range(10)]                       # the older ten: flagged
    rows += [(f"now() - interval '{10 - n} days'", 50.0, "correct", (False, False, False))
             for n in range(10)]                      # the newer ten: clean
    _completed(live_db, user_id, version_id, rows=rows)

    focus = next(t for t in client.get("/v1/progress", headers=headers)
                 .get_json()["reasoning_trends"] if t["id"] == "diagnostic_focus")
    assert focus["last10_rate"] == 0.0
    assert focus["prev10_rate"] == 1.0
    assert focus["direction"] == "improving", (
        "the rate fell from 1.0 to 0.0 and the direction says "
        f"{focus['direction']!r}; fewer flags is better")


def test_direction_is_none_without_a_previous_ten(
        client, account, live_db, version_id):
    """
    Not "stable". Telling a learner with four sessions that their habits are
    unchanged is a claim about data that does not exist.
    """
    user_id, headers = account
    _completed(live_db, user_id, version_id, rows=[
        (f"now() - interval '{n} days'", 50.0, "correct", (False, False, False))
        for n in (4, 3, 2, 1)
    ])
    trends = client.get("/v1/progress",
                        headers=headers).get_json()["reasoning_trends"]
    assert all(t["prev10_rate"] is None for t in trends)
    assert all(t["direction"] is None for t in trends)


def test_ct9_progress_describes_only_your_own_history(
        client, account, live_db, version_id, authority):
    """
    CT-9's shape for an aggregate: a stranger sees an empty history, not
    someone else's figures. No query in `ProgressRepository` carries a
    `WHERE user_id`; migration 016's policies do the filtering, so a
    forgotten clause returns nothing (`ADR-0016`).
    """
    user_id, _ = account
    _completed(live_db, user_id, version_id, rows=[
        (f"now() - interval '{n} days'", 90.0, "correct", (False, False, False))
        for n in (3, 2, 1)
    ])
    other_id, other_headers = _make_account(live_db, authority)
    try:
        body = client.get("/v1/progress", headers=other_headers).get_json()
        assert body["sessions_completed"] == 0, "one learner saw another's history"
        assert body["mean_coverage_last10"] is None
    finally:
        with live_db.begin() as c:
            c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": other_id})
            c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": other_id})


def test_progress_needs_an_account(client):
    assert client.get("/v1/progress").status_code == 401


# ── §4 · the export request ──────────────────────────────────────────

def test_an_export_request_is_accepted_and_recorded(
        client, account, live_db):
    """
    §4 → 202 with an ETA. 202 means "accepted, not done", so the endpoint's
    job is to record the request durably and say when it should be ready —
    which is what makes a data-subject access request provable.

    What does not exist is the worker that builds the file. API-10.
    """
    user_id, headers = account
    r = client.post("/v1/me/export", headers=headers)
    assert r.status_code == 202, r.get_json()
    assert r.get_json()["status"] == "queued"
    assert r.get_json()["estimated_ready_at"]

    with live_db.connect() as c:
        row = c.execute(sa.text("""
            SELECT action, entity_type, metadata FROM audit_log
            WHERE actor_id = :id ORDER BY id DESC LIMIT 1
        """), {"id": user_id}).mappings().first()
    assert row is not None, "the export request was not recorded"
    assert row["action"] == "profile.export_requested"
    assert row["metadata"]["sla_hours"] == 24


# ── §4 · the deletion that cannot run ────────────────────────────────

def test_account_deletion_is_501_and_says_so_in_the_envelope(client, account):
    """
    `DELETE /me` is blocked, not unfinished. §4 says it executes `DATA_MODEL`
    §10.2, and §10.2's erasure UPDATEs `session_events` — a table migration
    010 makes append-only with an unconditional trigger that refuses even the
    table owner.

    **This test exists so the 501 is a decision rather than an omission.** If
    someone implements the endpoint, this fails and they have to come and read
    API-9 before changing it. Returning 204 having anonymised only the profile
    would claim an erasure that did not happen, and §10.2 itself says a user
    "has a right to know what does not disappear".
    """
    _, headers = account
    r = client.delete("/v1/me", json={"confirmation": "DELETE"}, headers=headers)
    assert r.status_code == 501
    assert r.get_json()["error"]["code"] == "not_implemented"


def test_the_append_only_trigger_really_does_refuse_the_erasure(live_db):
    """
    The claim above, verified against the running database rather than taken
    from a migration file.

    If this ever stops raising — someone narrows the trigger, or disables it —
    then API-9 has been resolved and `DELETE /me` can be built. The test
    failing is the signal to go and build it.
    """
    # A row must exist, or the UPDATE matches nothing and the trigger never
    # fires — which would make this pass for the wrong reason. The first
    # version of this test did exactly that.
    with live_db.connect() as c:
        with pytest.raises(sa.exc.ProgrammingError, match="append-only"):
            with c.begin():
                version = c.execute(sa.text(
                    "SELECT id FROM case_versions LIMIT 1")).scalar_one()
                owner = uuid.uuid4()
                c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                          {"id": owner})
                c.execute(sa.text(
                    "INSERT INTO profiles (id, timezone) VALUES (:id, 'UTC')"),
                    {"id": owner})
                sid = uuid.uuid4()
                c.execute(sa.text("""
                    INSERT INTO sessions (id, user_id, case_version_id,
                                          sequence_index, status)
                    VALUES (:id, :uid, :vid, 1, 'active')
                """), {"id": sid, "uid": owner, "vid": version})
                c.execute(sa.text("""
                    INSERT INTO session_events (session_id, seq, type, payload)
                    VALUES (:sid, 1, 'question', CAST(:p AS jsonb))
                """), {"sid": sid, "p": '{"text": "real text", "char_count": 9}'})

                c.execute(sa.text("""
                    UPDATE session_events
                       SET payload = jsonb_set(payload, '{text}', '"[redacted]"')
                     WHERE session_id = :sid AND type = 'question'
                """), {"sid": sid})

    # The transaction aborted, so nothing above persisted.
    with live_db.begin() as c:
        c.exec_driver_sql(TRUNCATE_SESSION_TABLES)
