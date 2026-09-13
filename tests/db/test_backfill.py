"""
The pilot backfill (BUILD_PLAN T-018, `DATA_MODEL` §9.3).

The task is an import, so the tests are mostly about fidelity: the 16 sessions
must arrive with their own numbers, under their own engine version, and a
second run must change nothing.

The interesting one is `test_the_pilot_keeps_its_own_anchoring_score`. Today's
engine does not reproduce P07's anchoring result — the anchor keyword
"travel bug" was removed under invariant C-4 — and that is exactly why
`engine_version_id` exists. After this import both numbers are in the database
and both are correct.
"""

from __future__ import annotations

import json

import pytest
import sqlalchemy as sa

from scripts.backfill_pilot import ENGINE_VERSION, PROVENANCE, backfill, pilot_files


@pytest.fixture
def imported(app_db):
    """
    Run the backfill once.

    Through the admin engine, not `repo_scope` — the script is an operator
    task and writes tables the application role deliberately cannot
    (`engine_versions`, `auth.users`). Running it as the application would
    prove the wrong thing.
    """
    with app_db.begin() as conn:
        return backfill(conn)


def _one(app_db, sql: str, **params):
    with app_db.connect() as c:
        return c.execute(sa.text(sql), params).scalar()


# ── criterion 1: 16 sessions, 8 profiles ─────────────────────────────

def test_sixteen_sessions_and_eight_participants_are_imported(imported, app_db):
    assert imported["sessions"] == 16
    assert _one(app_db, "SELECT count(*) FROM sessions WHERE user_id IS NOT NULL") == 16
    assert _one(app_db, "SELECT count(DISTINCT research_pid) FROM profiles") == 8


def test_participants_are_keyed_on_their_research_pid(imported, app_db):
    with app_db.connect() as c:
        pids = sorted(c.execute(sa.text(
            "SELECT research_pid FROM profiles ORDER BY research_pid")).scalars())
    assert pids == [f"P0{n}" for n in range(1, 9)]


def test_participants_have_no_credentials(imported, app_db):
    """
    Research records, not accounts. No email, and the `auth.users` rows are
    placeholders that exist only to satisfy the foreign key — nobody can sign
    in as a pilot participant.
    """
    assert _one(app_db, "SELECT count(*) FROM profiles WHERE research_pid LIKE 'P0%'") == 8
    with app_db.connect() as c:
        cols = set(c.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'profiles'")).scalars())
    assert "email" not in cols, (
        "profiles has grown an email column — the pilot import must keep it NULL")


def test_the_year_of_study_label_becomes_a_number(imported, app_db):
    """'year_3' in the JSON, SMALLINT CHECK 1-10 in the column."""
    with app_db.connect() as c:
        years = set(c.execute(sa.text(
            "SELECT DISTINCT year_of_training FROM profiles")).scalars())
    assert years and years <= {2, 3, 4, 5}


def test_sessions_are_completed_and_numbered_from_the_pilot(imported, app_db):
    assert _one(app_db,
                "SELECT count(*) FROM sessions WHERE status <> 'completed'") == 0
    with app_db.connect() as c:
        sequences = sorted(c.execute(sa.text(
            "SELECT sequence_index FROM sessions")).scalars())
    assert sequences == [1] * 8 + [2] * 8


# ── criterion 2: provenance ──────────────────────────────────────────

def test_every_synthesised_event_is_marked_backfilled(imported, app_db):
    """
    `DATA_MODEL` §9.3's warning depends on this marker: the timestamps are
    synthetic, so any query computing think-time must be able to filter them
    out. An unmarked event is indistinguishable from a real one.
    """
    assert imported["events"] > 0
    unmarked = _one(app_db, """
        SELECT count(*) FROM session_events
        WHERE payload->>'provenance' IS DISTINCT FROM :p
    """, p=PROVENANCE)
    assert unmarked == 0


def test_the_synthesised_log_is_dense_and_ordered(imported, app_db):
    """Gaps would mean a lost insert; duplicates would violate UNIQUE(session_id, seq)."""
    with app_db.connect() as c:
        bad = c.execute(sa.text("""
            SELECT session_id FROM session_events
            GROUP BY session_id
            HAVING min(seq) <> 1 OR max(seq) <> count(*)
        """)).all()
    assert bad == []


def test_a_backfilled_session_replays_to_its_recorded_questions(imported, app_db):
    """
    The synthesised log is not decoration: it must reconstruct the session.
    A log that cannot be replayed would make these sixteen useless to T-016's
    recomputation and to every future analysis.
    """
    from nidan.domain.events import Event
    from nidan.domain.session import replay

    record = json.loads(pilot_files()[0].read_text(encoding="utf-8"))
    session_id = _one(app_db, """
        SELECT s.id FROM sessions s JOIN profiles p ON p.id = s.user_id
        WHERE p.research_pid = :pid AND s.sequence_index = :seq
    """, pid=record["participant"]["participant_id"],
        seq=record["participant"]["session_sequence"])

    with app_db.connect() as c:
        rows = c.execute(sa.text(
            "SELECT seq, type, payload, created_at FROM session_events "
            "WHERE session_id = :sid ORDER BY seq"), {"sid": session_id}).mappings().all()

    state = replay([Event(r["seq"], r["type"], r["payload"], r["created_at"])
                    for r in rows],
                   case_id=record["case_id"], started_at=record["start_time"])
    assert state["question_count"] == record["question_count"]
    assert state["questions_asked"] == record["questions_asked"]
    assert state["diagnosis_submitted"] == record["diagnosis_submitted"]


# ── criterion 3: results match the JSON exactly ──────────────────────

def test_every_result_matches_the_original_json(imported, app_db):
    """
    Criterion 3, over all sixteen. Verbatim, never recomputed: recomputing
    would overwrite the published record with today's numbers.
    """
    mismatches = []
    for path in pilot_files():
        record = json.loads(path.read_text(encoding="utf-8"))
        with app_db.connect() as c:
            stored = c.execute(sa.text("""
                SELECT r.* FROM session_results r
                JOIN sessions s ON s.id = r.session_id
                JOIN profiles p ON p.id = s.user_id
                WHERE p.research_pid = :pid AND s.sequence_index = :seq
            """), {"pid": record["participant"]["participant_id"],
                   "seq": record["participant"]["session_sequence"]}).mappings().one()

        for name, column in (("anchoring", "anchoring"),
                             ("premature_closure", "premature_closure"),
                             ("confirmation_bias", "confirmation_bias")):
            published = record["biases_detected"][name]
            if stored[f"{column}_detected"] != published["detected"]:
                mismatches.append(f"{path.name}/{name}: detected")
            if round(float(stored[f"{column}_score"]), 2) != round(published["score"], 2):
                mismatches.append(
                    f"{path.name}/{name}: {stored[f'{column}_score']} != {published['score']}")

        if stored["diagnosis_verdict"] != record["clinical_eval"]["diagnosis"]["verdict"]:
            mismatches.append(f"{path.name}: verdict")
        if stored["question_count"] != record["question_count"]:
            mismatches.append(f"{path.name}: question_count")

    assert not mismatches, "the import did not preserve the pilot:\n  " + "\n  ".join(mismatches)


def test_results_are_stored_under_the_pilot_engine_not_the_current_one(
        imported, app_db):
    with app_db.connect() as c:
        versions = set(c.execute(sa.text("""
            SELECT e.version FROM session_results r
            JOIN engine_versions e ON e.id = r.engine_version_id
        """)).scalars())
    assert versions == {ENGINE_VERSION}
    assert _one(app_db,
                "SELECT is_current FROM engine_versions WHERE version = :v",
                v=ENGINE_VERSION) is False


def test_the_pilot_keeps_its_own_anchoring_score(imported, app_db):
    """
    The point of the whole design, made concrete.

    P07's case 2 is the pulmonary embolism case. The learner asked about a
    "travel bug on the flight" — a question that pointed AT the correct
    diagnosis — and the pilot-era keyword list counted it as anchoring, giving
    0.71. The keyword was removed under invariant C-4, so today's engine gives
    0.00.

    Both are now in the database, and both are correct, because each is
    attached to the engine version that produced it. `DATA_MODEL` §6.4 said
    this table would make such a thing "a query rather than a forensic
    exercise".
    """
    from nidan.domain.assessment.engine import assess
    from nidan.domain.content.cases import get_case
    from tests.pilot import events_from, load

    path = next(p for p in pilot_files() if p.name.startswith("P07_case_2"))
    record = load(path)

    stored = _one(app_db, """
        SELECT r.anchoring_score FROM session_results r
        JOIN sessions s ON s.id = r.session_id
        JOIN profiles p ON p.id = s.user_id
        WHERE p.research_pid = 'P07' AND s.sequence_index = :seq
    """, seq=record["participant"]["session_sequence"])

    today = assess(events_from(record), get_case(record["case_id"]))

    assert round(float(stored), 2) == 0.71, "the published score was not preserved"
    assert today.bias_detail["anchoring"]["score"] == 0.0
    assert float(stored) != today.bias_detail["anchoring"]["score"], (
        "if these ever agree, the C-4 keyword fix may have been reverted")


def test_feedback_prose_is_imported(imported, app_db):
    assert _one(app_db, "SELECT count(*) FROM feedback_texts") == 16
    assert _one(app_db,
                "SELECT count(*) FROM feedback_texts WHERE generator <> 'llm'") == 0


def test_case_history_records_both_attempts_per_participant(imported, app_db):
    """Eight participants, two cases each, and the best verdict kept."""
    assert _one(app_db, "SELECT count(*) FROM user_case_history") == 16
    assert _one(app_db, """
        SELECT count(*) FROM user_case_history
        WHERE best_verdict NOT IN ('correct','partial','anchored','other')
    """) == 0


# ── criterion 4: idempotent ──────────────────────────────────────────

def test_running_it_twice_changes_nothing(imported, app_db):
    """
    Every id is derived from the source data with uuid5, so a second run
    addresses the same rows. Checked by counting every table it touches — a
    duplicate anywhere would double one of them.
    """
    def snapshot() -> dict:
        with app_db.connect() as c:
            return {t: c.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar()
                    for t in ("profiles", "sessions", "session_events",
                              "session_results", "feedback_texts",
                              "user_case_history", "engine_versions")}

    before = snapshot()
    with app_db.begin() as conn:
        backfill(conn)
    assert snapshot() == before


def test_a_dry_run_writes_nothing(app_db):
    with app_db.begin() as conn:
        counts = backfill(conn, dry_run=True)
    assert counts["sessions"] == 16
    assert _one(app_db, "SELECT count(*) FROM profiles") == 0
