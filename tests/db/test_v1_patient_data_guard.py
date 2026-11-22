"""
T-035 · the real-patient-data guard on the route (`API_CONTRACT` §6).

The detector has its own unit tests in `tests/test_patient_data_guard.py`.
What this file checks is the three things the route has to get right, each of
which is an acceptance criterion:

2. the question is **blocked** with 422 `patient_data_detected`, and **not
   consumed**;
3. an `input_blocked` event is logged with the **reason only, never the text**.

Against a real database, because "not consumed" and "logged" are both claims
about the event log, and a mock would be asserting the mock. The one that
would hurt most if it silently stopped holding is the text never reaching the
table — so it is checked by reading every payload back out of Postgres rather
than by trusting the handler.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from tests.app_config import TEST_SECRET, TRUNCATE_SESSION_TABLES

# A string carrying several detectable things at once, so one post exercises
# the whole path. Every fragment of it is checked for absence afterwards.
PASTED_RECORD = (
    "Mrs Anita Patel, hospital number 1123456, DOB 03/04/1978 — "
    "she rang from 07700 900123 about the chest pain"
)


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

    # TRUNCATE before the profile delete: `session_events` refuses DELETE even
    # to the owner (migration 002), and a cascade into it aborts the whole
    # transaction. See test_v1_consultation.py's note.
    with live_db.begin() as c:
        # `TRUNCATE_SESSION_TABLES` is a complete statement, not a list of
        # table names — "TRUNCATE llm_calls, leakage_flags, sessions". My first
        # version looped over it, which iterates the string character by
        # character and produced `TRUNCATE T CASCADE`.
        c.exec_driver_sql(TRUNCATE_SESSION_TABLES)
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": user_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": user_id})


# Lifted verbatim from test_v1_consultation.py. Four modules in tests/db now
# carry their own copy of this; see the build log's "found and not fixed".
# My own first attempt invented the columns — `role` for `platform_role`,
# `verdict` for `decision`, and no `scores` — which is precisely the drift
# that duplication causes.
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


def _events(live_db, session_id):
    with live_db.begin() as c:
        return c.execute(sa.text(
            "SELECT type, payload FROM session_events "
            "WHERE session_id = :s ORDER BY seq"), {"s": session_id}).mappings().all()


# ── Criterion 2 · blocked, and not consumed ──────────────────────────

def test_a_pasted_record_is_refused_with_422(client, account, session_id):
    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": PASTED_RECORD}, headers=headers)
    assert r.status_code == 422, r.get_json()
    assert r.get_json()["error"]["code"] == "patient_data_detected"


def test_the_question_is_not_consumed(client, account, session_id, live_db):
    """
    Criterion 2, and the half with teeth.

    `question_count` feeds the premature-closure detector (`P1: q < q_min`),
    so a blocked question logged as a question would inflate the count and
    **suppress a flag the learner should have seen**. The same reasoning as
    `patient_unavailable` not consuming the question, for a different reason.
    """
    _, headers = account
    client.post(f"/v1/sessions/{session_id}/questions",
                json={"text": PASTED_RECORD}, headers=headers)

    types = [e["type"] for e in _events(live_db, session_id)]
    assert "question" not in types, (
        "the blocked question was logged as a question; it would count "
        "against the 40-question cap and inflate question_count")
    assert "patient_reply" not in types, "nothing should have been asked"


def test_no_model_call_is_made(client, account, session_id, monkeypatch):
    """
    The guard must run **before** the gateway, not alongside it.

    The autouse `_no_real_llm` fixture would also fail a real call, so this
    patches in a counting stub and asserts zero — otherwise the test would
    pass with the guard removed, which is the mistake T-031 made once already.
    """
    calls = []

    def _counted(*a, **k):
        calls.append(1)
        raise AssertionError("the gateway was reached despite the guard")

    monkeypatch.setattr("nidan.api.v1.consultation.call_llm", _counted)

    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": PASTED_RECORD}, headers=headers)
    assert r.status_code == 422
    assert calls == [], "a blocked question still cost a model call"


def test_a_clean_question_still_goes_through(
        client, account, session_id, fake_llm):
    """The guard must not become a wall. The ordinary path is unaffected."""
    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": "Does the pain get worse after meals?"},
                    headers=headers)
    assert r.status_code == 201, r.get_json()


# ── Criterion 3 · the event, and what it must not contain ────────────

def test_an_input_blocked_event_is_logged_with_a_reason(
        client, account, session_id, live_db):
    _, headers = account
    client.post(f"/v1/sessions/{session_id}/questions",
                json={"text": PASTED_RECORD}, headers=headers)

    blocked = [e for e in _events(live_db, session_id)
               if e["type"] == "input_blocked"]
    assert len(blocked) == 1, "UX_SPEC S-10: 'Event logged for admin review'"
    assert blocked[0]["payload"]["reason"] == "named_individual", (
        "a name beside an identifier is the clearest case of a real person, "
        "and the reason admin review most needs to see")


def test_the_blocked_text_reaches_nothing(client, account, session_id, live_db):
    """
    **The one that matters most.** `DATA_MODEL` §8.2 — "never the offending
    text".

    Checked by reading every payload in the session back out of Postgres and
    searching for each fragment, rather than by inspecting the one event we
    expect to find. If a future change starts recording the text somewhere
    else in the log — a `session_meta`, an audit note, a "context" key — this
    still fails.

    Storing what we refused would put real patient data into the table we keep
    for ever, under the name of protecting it, and the block would be worse
    than no block at all.
    """
    _, headers = account
    client.post(f"/v1/sessions/{session_id}/questions",
                json={"text": PASTED_RECORD}, headers=headers)

    everything = str([dict(e) for e in _events(live_db, session_id)])
    for fragment in ("Anita", "Patel", "1123456", "03/04/1978", "900123",
                     "07700"):
        assert fragment not in everything, (
            f"{fragment!r} was written to session_events — the guard stored "
            f"the very data it refused")


def test_the_response_does_not_echo_the_input(client, account, session_id):
    """
    The 422 says *that* something looked like patient data and which
    category, never which characters matched. An error that quotes the input
    back puts it in logs, in browser history and in any client that renders
    `message` — all places the event log deliberately avoids.
    """
    _, headers = account
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": PASTED_RECORD}, headers=headers)
    rendered = r.get_data(as_text=True)
    for fragment in ("Anita", "Patel", "1123456", "03/04/1978", "900123"):
        assert fragment not in rendered, f"{fragment!r} echoed in the 422"


# ── §2.7 · the refusal order must not leak ───────────────────────────

def test_someone_elses_session_is_still_404(
        client, account, session_id, authority, live_db):
    """
    The guard runs inside the scope, after the ownership check, and that
    ordering is deliberate: a 422 on a stranger's session would confirm the
    session exists, which §2.7 calls the same leak in a quieter form.
    """
    stranger = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                  {"id": stranger})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, timezone) "
            "VALUES (:id, 'Stranger', 'UTC')"), {"id": stranger})

    headers = {"Authorization": f"Bearer {authority.token(sub=str(stranger))}"}
    r = client.post(f"/v1/sessions/{session_id}/questions",
                    json={"text": PASTED_RECORD}, headers=headers)

    assert r.status_code == 404, (
        "a stranger posting patient data got something other than 404, which "
        "tells them the session exists")
    assert r.get_json()["error"]["code"] == "not_found"

    with live_db.begin() as c:
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": stranger})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": stranger})
