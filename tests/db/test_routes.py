"""
The consultation, end to end, through the event log (BUILD_PLAN T-013).

These replace five smoke tests that used to assert a route returned 200 while
session state sat in a dictionary. They are slower — a real PostgreSQL, a real
transaction per request — and they check something the old ones could not: that
a consultation is reconstructed from an append-only log and survives the
process that created it.

Criteria 2, 4 and 5 are all here. Criterion 5 ("2 gunicorn workers, no session
bleed") is checked as the property that actually matters: two clients sharing
one engine cannot see each other's consultation, and no request depends on
anything held in the process between requests.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from nidan.app import create_app

# Every application these tests build signs its session cookies with this.
#
# It is passed as config rather than set as an environment variable, and that
# distinction is what CI caught: `settings` is a module-level singleton read at
# import, so `monkeypatch.setenv` after import changes nothing. Locally the key
# came from a developer's `.env` and the tests passed; on a runner with no
# `.env` each `create_app` fell back to `os.urandom(24)`, so the second
# application could not read the first one's cookie.
#
# The same fallback is a real hazard in production now that T-013 raised the
# worker count — gunicorn imports the app separately per worker — which is why
# `config.py` refuses to start a production environment without a key.
TEST_SECRET = "t013-tests-fixed-secret"


def _app():
    return create_app({"TESTING": True, "SECRET_KEY": TEST_SECRET})


@pytest.fixture
def client(live_db, fake_llm):
    return _app().test_client()


def _start(client, case_id="case_1"):
    return client.post(f"/pre_case/{case_id}", data={
        "participant_id": "T13", "year_of_study": "year_3", "confidence": "3"})


def _events(live_db, session_id=None):
    with live_db.connect() as c:
        return c.execute(sa.text(
            "SELECT session_id, seq, type, payload FROM session_events "
            "ORDER BY session_id, seq")).mappings().all()


# ── the flow ─────────────────────────────────────────────────────────

def test_a_consultation_records_every_action_as_an_event(client, live_db):
    """
    Criterion 2: every action appends an event before the response is returned.

    Checked by reading the table after each response rather than by trusting
    the route, because "the handler calls append()" is a claim about code and
    "the row is there when the response arrives" is a claim about behaviour.
    """
    assert _start(client).status_code == 200
    assert _events(live_db) == []

    client.post("/chat", json={"message": "Does the pain burn after meals?"})
    types = [e["type"] for e in _events(live_db)]
    assert types == ["question", "patient_reply"]

    client.post("/examine", json={"system": "vitals"})
    client.post("/investigate", json={"test": "ecg"})
    types = [e["type"] for e in _events(live_db)]
    assert types == ["question", "patient_reply", "examination", "investigation"]

    client.post("/conclude", json={"diagnosis": "GERD"})
    assert [e["type"] for e in _events(live_db)][-1] == "diagnosis"

    assert client.get("/feedback").status_code == 200


def test_the_sequence_is_dense_and_starts_at_one(client, live_db):
    _start(client)
    for i in range(3):
        client.post("/chat", json={"message": f"question number {i}"})
    client.post("/examine", json={"system": "vitals"})

    seqs = [e["seq"] for e in _events(live_db)]
    assert seqs == list(range(1, len(seqs) + 1)), "a gap means an append was lost"


def test_a_question_and_its_reply_are_appended_together(client, live_db):
    """
    Never one without the other. `question_count` feeds premature closure
    (P1: q < q_min), so a question recorded without an answer — after a failed
    model call and a retype — would inflate the count and suppress a flag the
    learner should have seen.
    """
    _start(client)
    client.post("/chat", json={"message": "Where exactly is the pain?"})
    types = [e["type"] for e in _events(live_db)]
    assert types.count("question") == types.count("patient_reply")


def test_topics_are_recorded_on_the_reply_not_the_question(client, live_db):
    """
    DATA_MODEL §8.2, and deliberate: `matched_topics` records what the system
    *understood*, under the engine version then current, so a recomputation can
    detect drift. On the question it would record only what was asked.
    """
    _start(client)
    client.post("/chat", json={"message": "Does the pain come after meals?"})

    events = {e["type"]: e["payload"] for e in _events(live_db)}
    assert "matched_topics" in events["patient_reply"]
    assert "matched_topics" not in events["question"]


def test_an_early_diagnosis_gets_its_own_event(client, live_db):
    _start(client)
    client.post("/chat", json={"message": "I think this is a heart attack"})
    assert "early_diagnosis" in [e["type"] for e in _events(live_db)]


def test_a_second_early_diagnosis_is_not_recorded_twice(client, live_db):
    """First commitment wins — what they revised it to is a different question."""
    _start(client)
    client.post("/chat", json={"message": "I think this is reflux"})
    client.post("/chat", json={"message": "actually I suspect an ulcer"})
    types = [e["type"] for e in _events(live_db)]
    assert types.count("early_diagnosis") == 1


# ── criterion 4: nothing is held in the process ──────────────────────

def test_a_consultation_survives_losing_the_process(client, live_db):
    """
    Criterion 4: killing the process mid-consultation loses nothing.

    The engine is disposed and a brand-new application is built — no shared
    memory, no warm pool, nothing carried over but the cookie the browser
    holds. Before T-013 this test could not be written at all: the state was
    the process.
    """
    from nidan.infra.db import engine as engine_mod

    _start(client)
    client.post("/chat", json={"message": "Does it burn after meals?"})
    client.post("/examine", json={"system": "vitals"})

    # BOTH cookies. Since T-015 the browser carries a signed Flask session
    # (which session it is on) and the `anonymous_id` trial cookie (whose
    # consultation it is). Copying only the first was enough until the visitor
    # id moved out of the Flask session, and the test failed the moment it did
    # — correctly, because a browser that kept only one of them would be a
    # browser that had lost its trial.
    carried = {name: client.get_cookie(name)
               for name in ("session", "anonymous_id")}
    assert all(c is not None for c in carried.values()), carried

    # The process dies.
    engine_mod.dispose_engine()

    reborn = _app().test_client()
    for name, cookie in carried.items():
        reborn.set_cookie(name, cookie.value)

    # And the consultation continues where it left off.
    r = reborn.post("/chat", json={"message": "and does anything relieve it?"})
    assert r.status_code == 200
    assert r.get_json()["question_count"] == 2, (
        "the replayed session did not remember the first question")

    reborn.post("/conclude", json={"diagnosis": "GERD"})
    assert reborn.get("/feedback").status_code == 200


def test_two_clients_do_not_share_a_consultation(client, live_db):
    """
    Criterion 5 as a property rather than a deployment: with state in the
    database and nothing in the process, two concurrent browsers cannot bleed
    into each other. This is what "no session bleed across workers" means.
    """
    other = _app().test_client()

    _start(client)
    _start(other, case_id="case_2")

    client.post("/chat", json={"message": "first browser question"})
    client.post("/chat", json={"message": "first browser again"})
    r = other.post("/chat", json={"message": "second browser question"})

    assert r.get_json()["question_count"] == 1, (
        "the second browser inherited the first browser's questions")

    rows = _events(live_db)
    assert len({e["session_id"] for e in rows}) == 2


# ── conclude and feedback ────────────────────────────────────────────

def test_submitting_a_diagnosis_twice_records_it_once(client, live_db):
    """
    Idempotent at the database (`diagnosis_submitted_at IS NULL`), not in a
    check the second request could race past.
    """
    _start(client)
    client.post("/chat", json={"message": "does it burn"})
    assert client.post("/conclude", json={"diagnosis": "GERD"}).status_code == 200
    assert client.post("/conclude", json={"diagnosis": "Something else"}).status_code == 200

    types = [e["type"] for e in _events(live_db)]
    assert types.count("diagnosis") == 1

    with live_db.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM feedback_texts")).scalar() == 1


def test_the_feedback_page_stores_prose_and_recomputes_everything_else(
        client, live_db):
    """
    ADR-0003 and ADR-0005 together: the model's words are stored because they
    cannot be recomputed; every number is recomputed because it can be, and a
    stored score is a cache that can silently disagree with its own log.
    """
    _start(client)
    client.post("/chat", json={"message": "does the pain burn after meals"})
    client.post("/conclude", json={"diagnosis": "GERD"})

    with live_db.connect() as c:
        stored = c.execute(sa.text(
            "SELECT lines, generator FROM feedback_texts")).mappings().one()
    assert stored["lines"], "the prose must be stored"
    assert stored["generator"] in ("llm", "rule_fallback")

    # No score, flag or verdict is stored anywhere.
    with live_db.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM session_results")).scalar() == 0

    assert client.get("/feedback").status_code == 200


def test_opening_the_feedback_page_is_recorded(client, live_db):
    _start(client)
    client.post("/conclude", json={"diagnosis": "GERD"})
    client.get("/feedback")
    assert "feedback_viewed" in [e["type"] for e in _events(live_db)]


def test_feedback_before_a_diagnosis_redirects(client, live_db):
    _start(client)
    assert client.get("/feedback").status_code == 302


# ── the session row ──────────────────────────────────────────────────

def test_the_session_is_anonymous_and_points_at_a_real_case_version(
        client, live_db):
    """
    The prototype has no accounts yet, so every consultation is a trial
    (PRD FR-2) — the path T-015 later claims into a real account. It still
    points at a genuine `case_versions` row.
    """
    _start(client)
    with live_db.connect() as c:
        row = c.execute(sa.text("""
            SELECT s.user_id, s.anonymous_id, s.status, s.confidence_pre, c.slug
            FROM sessions s
            JOIN case_versions cv ON cv.id = s.case_version_id
            JOIN cases c ON c.id = cv.case_id
        """)).mappings().one()

    assert row["user_id"] is None
    assert row["anonymous_id"]
    assert row["status"] == "active"
    assert row["confidence_pre"] == 3
    assert row["slug"] == "chest-pain-gerd"


def test_concluding_completes_the_session(client, live_db):
    _start(client)
    client.post("/conclude", json={"diagnosis": "GERD"})
    with live_db.connect() as c:
        row = c.execute(sa.text(
            "SELECT status, ended_at, diagnosis_submitted_at FROM sessions"
        )).mappings().one()
    assert row["status"] == "completed"
    assert row["ended_at"] is not None
    assert row["diagnosis_submitted_at"] is not None
