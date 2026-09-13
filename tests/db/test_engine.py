"""
The engine against the database (BUILD_PLAN T-016).

`tests/test_golden_assessment.py` proves the engine computes the right answers;
this file proves the answers are stored with the version that produced them,
and that a stored result is as private as the consultation it describes.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.domain.assessment.engine import EngineVersion, assess
from nidan.domain.assessment.thresholds import PILOT
from nidan.domain.content.cases import get_case
from nidan.domain.events import Event
from nidan.infra.db.actor import AuthenticatedUser
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.anonymous import anonymous_scope

USER_ID = uuid.UUID("3f7c1b6e-2a4d-4c8f-9b1e-5d6a7c8e9f01")
OTHER_ID = uuid.UUID("9a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d")


@pytest.fixture
def user(app_db):
    def _make(user_id: uuid.UUID = USER_ID) -> uuid.UUID:
        with app_db.begin() as c:
            c.execute(sa.text(
                "INSERT INTO auth.users (id) VALUES (:id) ON CONFLICT DO NOTHING"),
                {"id": user_id})
        with repo_scope(AuthenticatedUser(user_id)) as db:
            db.profiles.ensure()
        return user_id
    return _make


def _events(diagnosis: str = "GERD") -> list[Event]:
    return [
        Event(1, "question", {"text": "Could this be a heart attack?",
                              "char_count": 29}),
        Event(2, "patient_reply", {"text": "I don't know",
                                   "matched_topics": ["pain_character"]}),
        Event(3, "examination", {"key": "vitals", "label": "Vitals",
                                 "finding": "HR 78"}),
        Event(4, "diagnosis", {"text": diagnosis}),
    ]


# ── the engine version ───────────────────────────────────────────────

def test_the_current_engine_is_the_seeded_one(app_db, user):
    user()
    with repo_scope(AuthenticatedUser(USER_ID)) as db:
        engine = db.engines.current()

    assert engine is not None, "migration 018 seeds exactly one current engine"
    assert engine.id is not None
    assert engine.version == "1.0.0"
    assert engine.thresholds == PILOT, (
        "the stored thresholds and the in-code fallback describe different "
        "engines — a score would mean something other than what it says")


def test_an_engine_version_can_be_fetched_by_id(app_db, user):
    """Needed to interpret an old result, or replay under a candidate version."""
    user()
    with repo_scope(AuthenticatedUser(USER_ID)) as db:
        current = db.engines.current()
        assert db.engines.by_id(current.id).version == current.version
        assert db.engines.by_id(uuid.uuid4()) is None


# ── storing a result ─────────────────────────────────────────────────

def test_a_result_is_stored_with_the_engine_that_produced_it(
        app_db, user, published_case):
    user()
    cv = published_case()
    with repo_scope(AuthenticatedUser(USER_ID)) as db:
        session_id = db.sessions.create(cv)["id"]
        engine = db.engines.current()
        result = assess(_events(), get_case("case_1"), engine)
        db.results.save(session_id, result)

    with repo_scope(AuthenticatedUser(USER_ID)) as db:
        stored = db.results.get(session_id)

    assert stored["engine_version_id"] == engine.id
    assert stored["diagnosis_verdict"] == result.diagnosis_verdict
    assert float(stored["coverage_pct"]) == result.coverage_pct
    assert stored["question_count"] == result.question_count
    # DATA_MODEL §8.5 — the counters survive the round trip, which is what
    # makes a future mismatch localisable.
    assert all("counters" in d for d in stored["bias_detail"].values())


def test_a_result_without_an_engine_version_is_refused(app_db, user,
                                                       published_case):
    """
    `EngineVersion.pilot()` has no id on purpose. A score whose thresholds are
    unrecorded cannot be interpreted later, which is the whole reason
    `engine_versions` exists (DATA_MODEL §6.4).
    """
    user()
    cv = published_case()
    with repo_scope(AuthenticatedUser(USER_ID)) as db:
        session_id = db.sessions.create(cv)["id"]
        result = assess(_events(), get_case("case_1"), EngineVersion.pilot())
        with pytest.raises(ValueError, match="engine_version_id"):
            db.results.save(session_id, result)


def test_recomputing_replaces_the_row_rather_than_failing(
        app_db, user, published_case):
    """
    `session_results` is keyed on `session_id`, and it is derived data — unlike
    `session_events`, which is append-only precisely because it is not. A
    recomputation under a new engine must replace the old row.
    """
    user()
    cv = published_case()
    with repo_scope(AuthenticatedUser(USER_ID)) as db:
        session_id = db.sessions.create(cv)["id"]
        engine = db.engines.current()
        db.results.save(session_id, assess(_events("GERD"), get_case("case_1"), engine))
        db.results.save(session_id,
                        assess(_events("Myocardial infarction"), get_case("case_1"), engine))
        stored = db.results.get(session_id)

    assert stored["diagnosis_submitted"] == "Myocardial infarction"
    with app_db.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM session_results")).scalar() == 1


def test_a_second_users_result_is_invisible(app_db, user, published_case):
    """
    `own_session_results` inherits through the parent session. The query in the
    repository carries no owner clause, so this fails if the policy is inert.
    """
    user(USER_ID)
    user(OTHER_ID)
    cv = published_case()

    with repo_scope(AuthenticatedUser(USER_ID)) as db:
        session_id = db.sessions.create(cv)["id"]
        db.results.save(session_id,
                        assess(_events(), get_case("case_1"), db.engines.current()))

    with repo_scope(AuthenticatedUser(OTHER_ID)) as db:
        assert db.results.get(session_id) is None


def test_a_trial_result_is_scoped_to_its_visitor(app_db, published_case):
    """
    A trial is a complete case including feedback (`PRD` FR-2.2), so it is
    assessed like any other consultation. RLS is bypassed on that path, so the
    `anonymous_id` filter is the only thing scoping it.
    """
    cv = published_case()
    with anonymous_scope("visitor-a") as db:
        session_id = db.sessions.create(cv)["id"]
        db.results.save(session_id,
                        assess(_events(), get_case("case_1"), db.engines.current()))
        assert db.results.get(session_id) is not None

    with anonymous_scope("visitor-b") as db:
        assert db.results.get(session_id) is None


def test_concluding_a_consultation_stores_its_assessment(live_db, fake_llm):
    """
    End to end through the prototype: the row appears, with an engine version,
    and its counters match a fresh recomputation from the same log.
    """
    from nidan.app import create_app

    client = create_app({"TESTING": True, "SECRET_KEY": "t016"}).test_client()
    client.post("/pre_case/case_1", data={
        "participant_id": "T16", "year_of_study": "year_4", "confidence": "3"})
    client.post("/chat", json={"message": "does the pain burn after meals?"})
    client.post("/conclude", json={"diagnosis": "GERD"})

    with live_db.connect() as c:
        stored = c.execute(sa.text(
            "SELECT r.*, s.id AS sid FROM session_results r "
            "JOIN sessions s ON s.id = r.session_id")).mappings().one()

    assert stored["engine_version_id"] is not None
    assert stored["question_count"] == 1
    assert stored["diagnosis_submitted"] == "GERD"
    assert stored["bias_detail"]["anchoring"]["counters"]["q"] == 1
