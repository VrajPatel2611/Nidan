"""
T-030 slice 3 · the consultation write path (`API_CONTRACT` §6).

Contract test **CT-2** lives here: a question's response must carry no
`matched_topics`, no coverage, no bias field. `PRD` FR-4.7 and U2 are the
reason — a learner who can see which topics they have covered optimises for
the meter instead of the history, and the meter is what we are trying to
measure.

The §2.9 limits are checked against a real database rather than a mock,
because both are counts over the event log and a mock would be asserting the
mock. The 40-per-session cap counts **questions**, not events: a learner who
examined eight systems and ordered six tests has not used up a third of their
questions, and a test that counted events would pass while the product
punished thoroughness.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from tests.app_config import TEST_SECRET, TRUNCATE_SESSION_TABLES


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
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": user_id})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, timezone) "
            "VALUES (:id, 'Test Learner', 'UTC')"), {"id": user_id})

    yield user_id, {"Authorization": f"Bearer {authority.token(sub=str(user_id))}"}

    # TRUNCATE the session tables BEFORE deleting the profile, and the order
    # is not cosmetic. `sessions.user_id` cascades from `profiles` and
    # `session_events.session_id` cascades from `sessions`, so deleting the
    # profile reaches `session_events` — where migration 010's
    # `session_events_append_only` trigger refuses any DELETE and raises
    # "Table session_events is append-only". TRUNCATE bypasses row triggers,
    # which is exactly what a teardown wants and what application code must
    # never be able to do.
    #
    # Worth remembering for slice 5: `DELETE /me` will hit the same wall.
    # `DATA_MODEL` §10.2 anonymises a profile rather than deleting it, and
    # this is presumably why.
    with live_db.begin() as c:
        c.exec_driver_sql(TRUNCATE_SESSION_TABLES)
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": user_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": user_id})


@pytest.fixture
def published_version(live_db):
    """
    A published case, via an approving review — migration 007's trigger
    refuses a direct status flip, and a fixture should not take a shortcut the
    product cannot.
    """
    reviewer_id = uuid.uuid4()
    with live_db.begin() as c:
        version_id = c.execute(sa.text(
            "SELECT id FROM case_versions ORDER BY created_at LIMIT 1")).scalar()
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                  {"id": reviewer_id})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, platform_role, timezone) "
            "VALUES (:id, 'Dr Fixture', 'reviewer', 'UTC')"), {"id": reviewer_id})
        c.execute(sa.text("""
            INSERT INTO clinical_reviews (case_version_id, reviewer_id,
                                          decision, scores)
            VALUES (:vid, :rid, 'approved', CAST(:scores AS jsonb))
        """), {"vid": version_id, "rid": reviewer_id,
               "scores": '{"clinical_plausibility": 5, "internal_consistency": 4,'
                         ' "trap_validity": 5, "solvability": 4,'
                         ' "rubric_version": "v1"}'})
        c.execute(sa.text(
            "UPDATE case_versions SET status = 'published', published_at = now() "
            "WHERE id = :id"), {"id": version_id})

    yield version_id

    with live_db.begin() as c:
        c.execute(sa.text("DELETE FROM clinical_reviews WHERE reviewer_id = :r"),
                  {"r": reviewer_id})
        c.execute(sa.text(
            "UPDATE case_versions SET status = 'draft', published_at = NULL "
            "WHERE id = :id"), {"id": version_id})
        c.execute(sa.text("DELETE FROM profiles WHERE id = :r"), {"r": reviewer_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :r"), {"r": reviewer_id})


@pytest.fixture
def session_id(client, account, published_version):
    r = client.post("/v1/sessions", json={}, headers=account[1])
    assert r.status_code == 201, r.get_json()
    return r.get_json()["session_id"]


# ── §6 · asking the patient, and CT-2 ────────────────────────────────

def test_a_question_returns_the_reply(client, account, session_id, fake_llm):
    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "Does the pain get worse after meals?"},
                    headers=headers)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["question"]["text"] == "Does the pain get worse after meals?"
    assert body["reply"]["text"]
    assert body["seq"] >= 2, "the reply should follow the question in the log"


def test_ct2_the_reply_carries_no_assessment_state(
        client, account, session_id, fake_llm, live_db):
    """
    **CT-2.** `PRD` FR-4.7 and U2.

    The assertion has two halves, and the second is the one that matters:
    the response must not carry `matched_topics`, **and** the event must. A
    response that omits it because nothing computed it would pass the first
    half and silently break T-016, which recomputes against the stored value
    to detect drift.
    """
    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "Is the pain burning, and worse after food?"},
                    headers=headers)
    assert r.status_code == 201

    raw = r.get_data(as_text=True)
    for banned in ("matched_topics", "coverage", "topics_covered",
                   "topics_missed", "questions_asked", "questions_remaining",
                   "anchoring", "premature", "confirmation", "score"):
        assert banned not in raw, f"{banned!r} returned mid-consultation"

    with live_db.connect() as c:
        payload = c.execute(sa.text("""
            SELECT payload FROM session_events
            WHERE session_id = :sid AND type = 'patient_reply'
            ORDER BY seq DESC LIMIT 1
        """), {"sid": session_id}).scalar_one()
    assert "matched_topics" in payload, (
        "nothing stored matched_topics; T-016's drift check has nothing to "
        "compare against")


def test_a_question_over_500_characters_is_refused(client, account, session_id):
    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "a" * 501}, headers=headers)
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "question_too_long"
    assert r.get_json()["error"]["details"]["length"] == 501


def test_an_empty_question_is_refused(client, account, session_id):
    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "   "}, headers=headers)
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "validation_failed"


# ── §6 · the failure that must not cost the learner anything ─────────

def test_patient_unavailable_does_not_consume_the_question(
        client, account, session_id, live_db, monkeypatch):
    """
    §6, in bold: "`patient_unavailable` must not consume the question…
    consuming it on failure would lose the user's work."

    And the reason that matters more than the UX: `question_count` feeds the
    premature-closure detector (`P1: q < q_min`), so a question logged with no
    answer inflates the count and **suppresses a flag the learner should have
    seen**. The question event is appended only after the reply returns.
    """
    def boom(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr("nidan.api.v1.consultation.call_llm", boom)

    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "Where exactly is the pain?"}, headers=headers)
    assert r.status_code == 503
    assert r.get_json()["error"]["code"] == "patient_unavailable"

    with live_db.connect() as c:
        n = c.execute(sa.text(
            "SELECT count(*) FROM session_events "
            "WHERE session_id = :sid AND type = 'question'"),
            {"sid": session_id}).scalar_one()
    assert n == 0, "the question was consumed by a failed model call"


def test_the_failure_message_does_not_echo_the_provider(
        client, account, session_id, monkeypatch):
    """
    A provider's error string can carry prompt fragments, and the prompt is
    the patient's chart — which is `system_prompt`, the field CT-1 exists to
    keep away from a learner.
    """
    def boom(*args, **kwargs):
        raise RuntimeError("context: You are playing Ramesh Kumar, "
                           "correct_diagnosis GERD")

    monkeypatch.setattr("nidan.api.v1.consultation.call_llm", boom)

    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "Anything else?"}, headers=headers)
    raw = r.get_data(as_text=True)
    assert "Ramesh" not in raw and "correct_diagnosis" not in raw


# ── §2.9 · the two limits ────────────────────────────────────────────

def _fill_questions(live_db, session_id, n):
    """`n` question events, written straight in — the API would need n LLM calls."""
    with live_db.begin() as c:
        for i in range(n):
            c.execute(sa.text("""
                INSERT INTO session_events (session_id, seq, type, payload)
                VALUES (:sid, :seq, 'question', CAST(:p AS jsonb))
            """), {"sid": session_id, "seq": 1000 + i,
                   "p": '{"text": "filler", "char_count": 6}'})


def test_the_session_cap_is_forty_questions(
        client, account, session_id, live_db, fake_llm):
    _, headers = account
    _fill_questions(live_db, session_id, 40)

    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "One more?"}, headers=headers)
    assert r.status_code == 429
    assert r.get_json()["error"]["code"] == "question_limit_reached"
    assert r.get_json()["error"]["details"]["limit"] == 40


def test_the_cap_counts_questions_not_events(
        client, account, session_id, live_db, fake_llm):
    """
    The distinction the limit lives or dies on. A learner who examined and
    investigated thoroughly has used no questions, and a cap that counted
    events would punish exactly the behaviour the product is trying to teach.
    """
    _, headers = account
    _fill_questions(live_db, session_id, 10)
    with live_db.begin() as c:
        for i in range(40):
            c.execute(sa.text("""
                INSERT INTO session_events (session_id, seq, type, payload)
                VALUES (:sid, :seq, 'examination', CAST(:p AS jsonb))
            """), {"sid": session_id, "seq": 2000 + i,
                   "p": '{"key": "vitals", "label": "V", "finding": "f"}'})

    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "Still allowed?"}, headers=headers)
    assert r.status_code == 201, (
        "50 events but only 10 questions — the cap counted the wrong thing")


def test_the_hourly_limit_sends_retry_after(
        client, account, session_id, live_db, fake_llm):
    """
    §2.9: "429 responses carry `Retry-After` in seconds." Without it a client
    either gives up or hammers, and neither is what the limit is for.
    """
    _, headers = account
    _fill_questions(live_db, session_id, 60)

    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "Again?"}, headers=headers)
    assert r.status_code == 429
    # The per-session cap fires first at 40, which is correct — but then this
    # test would be asserting the wrong limit, so check which one answered.
    assert r.get_json()["error"]["code"] == "question_limit_reached"
    assert "Retry-After" not in r.headers, (
        "the session cap is not a rate limit and has nothing to retry after")


def test_a_concluded_consultation_refuses_more_questions(
        client, account, session_id, live_db, fake_llm):
    _, headers = account
    with live_db.begin() as c:
        c.execute(sa.text(
            "UPDATE sessions SET status = 'completed', ended_at = now() "
            "WHERE id = :id"), {"id": session_id})

    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "One more thought"}, headers=headers)
    assert r.status_code == 409
    assert r.get_json()["error"]["code"] == "session_concluded"


# ── §6 · examining and investigating ─────────────────────────────────

@pytest.mark.parametrize(("endpoint", "key"), [
    ("examinations", "vitals"),
    ("investigations", "ecg"),
])
def test_ordering_returns_a_result_with_no_relevance_signal(
        client, account, session_id, endpoint, key):
    """
    §6, in bold: "Response must not include `category` or `is_key`"
    (`PRD` FR-6.6).

    `was_case_specific` is stored on the event — the scorecard needs it — and
    is the same signal under another name, so it must not come back either.
    Whether a result was this case's own IS its relevance.
    """
    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/{endpoint}",
                    json={"key": key}, headers=headers)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert set(body) == {"key", "label", "result", "at", "already_ordered"}
    assert body["key"] == key
    assert body["label"] and body["result"]
    assert body["already_ordered"] is False

    raw = r.get_data(as_text=True)
    for banned in ("category", "is_key", "was_case_specific", "normal_result"):
        assert banned not in raw, f"{banned!r} leaked a relevance signal"


@pytest.mark.parametrize("endpoint", ["examinations", "investigations"])
def test_an_unknown_key_is_404(client, account, session_id, endpoint):
    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/{endpoint}",
                    json={"key": "palpate_the_vibes"}, headers=headers)
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "unknown_key"


@pytest.mark.parametrize(("endpoint", "key"), [
    ("examinations", "vitals"),
    ("investigations", "ecg"),
])
def test_ordering_twice_replays_the_first_result(
        client, account, session_id, live_db, endpoint, key):
    """
    §6: `already_ordered: true` "returns the stored result without creating a
    duplicate event" (`PRD` FR-5.3, FR-6.3).

    Two reasons, and the second is the one a test should pin: ordering the
    same test twice is one clinical decision, and a duplicate event would
    inflate the investigation count the scorecard divides by — so a learner
    who double-clicked would score differently from one who did not.
    """
    _, headers = account
    first = client.post(f"/v1/sessions/{session_id}/{endpoint}",
                        json={"key": key}, headers=headers)
    second = client.post(f"/v1/sessions/{session_id}/{endpoint}",
                         json={"key": key}, headers=headers)

    assert second.status_code == 200
    assert second.get_json()["already_ordered"] is True
    assert second.get_json()["result"] == first.get_json()["result"]

    event_type = "examination" if endpoint == "examinations" else "investigation"
    with live_db.connect() as c:
        n = c.execute(sa.text(
            "SELECT count(*) FROM session_events "
            "WHERE session_id = :sid AND type = CAST(:t AS event_type)"),
            {"sid": session_id, "t": event_type}).scalar_one()
    assert n == 1, "the second order created a duplicate event"


def test_a_key_the_case_does_not_use_returns_the_normal_result(
        client, account, session_id, live_db):
    """
    The universal-panel design (`PRD` FR-5.1), and why a key being absent
    from this case is not an error.

    Every learner sees all 91 investigations whatever case they are on, so
    ordering an irrelevant one must return a plausible normal report rather
    than a 404 — a 404 would tell them the test is irrelevant, which is the
    answer.
    """
    _, headers = account
    # Seeded by migration 031 for case_9; no other case uses it, so for
    # whatever case was selected here it is almost certainly not case-specific.
    r = client.post(f"/v1/sessions/{session_id}/investigations",
                    json={"key": "hla_b27"}, headers=headers)
    assert r.status_code == 201
    assert r.get_json()["result"], "no result text for an irrelevant test"

    with live_db.connect() as c:
        payload = c.execute(sa.text("""
            SELECT payload FROM session_events
            WHERE session_id = :sid AND type = 'investigation'
            ORDER BY seq DESC LIMIT 1
        """), {"sid": session_id}).scalar_one()
    assert "was_case_specific" in payload, (
        "the scorecard needs to know whether this was the case's own result")


@pytest.mark.parametrize("endpoint", ["examinations", "investigations"])
def test_a_concluded_consultation_refuses_more_orders(
        client, account, session_id, live_db, endpoint):
    _, headers = account
    with live_db.begin() as c:
        c.execute(sa.text(
            "UPDATE sessions SET status = 'completed', ended_at = now() "
            "WHERE id = :id"), {"id": session_id})

    r = client.post(f"/v1/sessions/{session_id}/{endpoint}",
                    json={"key": "vitals"}, headers=headers)
    assert r.status_code == 409
    assert r.get_json()["error"]["code"] == "session_concluded"


@pytest.mark.parametrize("endpoint", ["questions", "examinations", "investigations"])
def test_ct9_another_learner_cannot_write_to_your_consultation(
        client, account, session_id, authority, live_db, endpoint):
    """
    CT-9 on the write path. §2.7: 404, never 403 — a 403 would confirm the
    consultation exists.

    Enforced by `own_sessions` rather than by these handlers: `sessions.get()`
    carries no owner filter, so the refusal takes the same path as a session
    id that was never issued.
    """
    other = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": other})
        c.execute(sa.text("INSERT INTO profiles (id, timezone) VALUES (:id, 'UTC')"),
                  {"id": other})

    r = client.post(
        f"/v1/sessions/{session_id}/{endpoint}",
        json={"text": "Whose patient is this?", "key": "vitals"},
        headers={"Authorization": f"Bearer {authority.token(sub=str(other))}"})
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "not_found"

    with live_db.begin() as c:
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": other})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": other})
