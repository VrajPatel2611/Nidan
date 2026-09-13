#!/usr/bin/env python3
"""
Import the 16 pilot sessions into the schema (BUILD_PLAN T-018, `DATA_MODEL` §9.3).

    python scripts/backfill_pilot.py            # import
    python scripts/backfill_pilot.py --dry-run  # report what would change

Optional, and safe to run more than once: every id is derived from the source
data with `uuid5`, so a second run updates the same rows instead of creating a
second copy of your pilot.

**Results are inserted verbatim, never recomputed.** That is the whole point of
the exercise. Today's engine does not reproduce one of the sixteen — P07's
anchoring score, because the anchor keyword "travel bug" was removed under
invariant C-4 — and recomputing would overwrite the published record with
today's numbers and destroy the evidence. Instead the pilot's results are
stored under their own `engine_versions` row, `pilot-2026-07`, so both numbers
are in the database and both are correct: 0.71 under the engine that produced
it, 0.00 under the engine that ships. `DATA_MODEL` §6.4 said this table would
make such a thing "a query rather than a forensic exercise"; this is where that
stops being a claim.

**Where to run it.** Locally and in staging. Whether the pilot belongs in the
production database is a privacy decision about real participants' data, not an
engineering one, and it is deliberately not this script's default.

⚠️ **Synthesised events carry `provenance: "backfilled"` and must be excluded
from any timing analysis.** The JSON preserved questions, examinations and
investigations as separate blocks but not their interleaving, so the log is
block-ordered and its timestamps are invented.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import sqlalchemy as sa  # noqa: E402

from nidan.domain.assessment.thresholds import PILOT  # noqa: E402
from nidan.domain.content.cases import CASE_SLUGS, get_case  # noqa: E402
from nidan.domain.events import validate_payload  # noqa: E402
from nidan.infra.db.engine import get_engine  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent

# A fixed namespace, so ids are reproducible across machines and runs. Changing
# it would re-import everything as new rows, which is exactly what idempotency
# is supposed to prevent — so it is a constant, not a setting.
NAMESPACE = uuid.UUID("6f1b7f4e-0e2a-4a1c-9f3d-7c2b5a9e1d40")

ENGINE_VERSION = "pilot-2026-07"
PROVENANCE = "backfilled"

# The pilot's own consent and ethics record covers these participants; the rows
# carry no email and no credentials, so nobody can sign in as them.
ENGINE_NOTES = (
    "The engine as it ran during the July 2026 pilot. Thresholds identical to "
    "1.0.0; the difference is case content. Case 2's anchor keyword list "
    "contained 'travel bug', which overlapped the travel-history clue pointing "
    "at the correct diagnosis (pulmonary embolism). It was removed under "
    "invariant C-4, which is why P07_case_2's anchoring score differs between "
    "this version and 1.0.0. Results stored under this version are the "
    "published ones and must not be recomputed."
)


def stable_id(*parts: str) -> uuid.UUID:
    """A reproducible id for a thing identified by its source data."""
    return uuid.uuid5(NAMESPACE, "nidan:pilot:" + ":".join(parts))


def pilot_files() -> list[pathlib.Path]:
    """The committed pilot sessions, newest last."""
    import subprocess

    listed = subprocess.run(
        ["git", "ls-files", "sessions/"], cwd=REPO,
        capture_output=True, text=True, check=True).stdout.split()
    return sorted(REPO / f for f in listed if f.endswith(".json"))


def year_of_training(year_of_study: str) -> int | None:
    """'year_3' -> 3. The JSON stores a label; the column is SMALLINT 1-10."""
    digits = "".join(c for c in (year_of_study or "") if c.isdigit())
    return int(digits) if digits else None


def synthesise_events(record: dict[str, Any]) -> list[dict[str, Any]]:
    """
    One pilot session as an event log.

    Block-ordered, because the JSON did not preserve the interleaving, and
    every payload carries the provenance marker that says so.
    """
    started = datetime.fromisoformat(record["start_time"])
    events: list[dict[str, Any]] = []

    def add(event_type: str, payload: dict[str, Any]) -> None:
        payload = {**payload, "provenance": PROVENANCE}
        # Validated on the way in, exactly like a live event. A backfill that
        # skipped this could write payloads the replayer cannot read.
        validate_payload(event_type, payload)
        events.append({
            "seq": len(events) + 1,
            "type": event_type,
            "payload": payload,
            # Synthetic: one second apart, in block order. Real enough to sort,
            # meaningless for timing — hence the provenance marker.
            "created_at": started + timedelta(seconds=len(events)),
        })

    topics = record.get("topics_covered", [])
    for index, question in enumerate(record.get("questions_asked", [])):
        add("question", {"text": question, "char_count": len(question)})
        add("patient_reply", {"text": "", "matched_topics": topics if index == 0 else []})

    for key in record.get("exams_performed", []):
        add("examination", {"key": key, "label": key, "finding": ""})
    for key in record.get("investigations_ordered", []):
        add("investigation", {"key": key, "label": key, "result": ""})

    if record.get("early_diagnosis"):
        add("early_diagnosis", {"text": record["early_diagnosis"]})
    if record.get("diagnosis_submitted"):
        add("diagnosis", {"text": record["diagnosis_submitted"]})

    return events


def coverage_of(record: dict[str, Any]) -> float:
    """Topic coverage, from the stored topics and the case's required list."""
    case = get_case(record["case_id"])
    required = case["required_topics"]
    covered = record.get("topics_covered", [])
    hit = [t for t in required if t in covered]
    return round(len(hit) / len(required) * 100, 2) if required else 0.0


def duration_of(record: dict[str, Any]) -> int | None:
    start, end = record.get("start_time"), record.get("end_time")
    if not start or not end:
        return None
    return int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())


def backfill(conn: sa.engine.Connection, *, dry_run: bool = False) -> dict[str, int]:
    """Import every pilot session. Returns a count of what was written."""
    files = pilot_files()
    counts = {"profiles": 0, "sessions": 0, "events": 0, "results": 0,
              "feedback": 0, "history": 0}
    if not files:
        raise SystemExit("no pilot sessions found — this needs a git checkout")

    engine_id = _ensure_engine_version(conn, dry_run=dry_run)
    case_versions = _case_version_ids(conn)

    for path in files:
        record = json.loads(path.read_text(encoding="utf-8"))
        participant = record["participant"]
        research_pid = participant["participant_id"]

        user_id = stable_id("profile", research_pid)
        session_id = stable_id("session", path.name)
        case_version_id = case_versions.get(record["case_id"])
        if case_version_id is None:
            raise SystemExit(
                f"{path.name}: no case_versions row for {record['case_id']}. "
                f"Run `alembic upgrade head` first — migration 019 seeds them.")

        if dry_run:
            counts["sessions"] += 1
            continue

        _upsert_profile(conn, user_id, research_pid, participant)
        counts["profiles"] += 1

        _upsert_session(conn, session_id, user_id, case_version_id,
                        record, participant)
        counts["sessions"] += 1

        counts["events"] += _insert_events(conn, session_id, record)
        _upsert_result(conn, session_id, record, engine_id)
        counts["results"] += 1
        counts["feedback"] += _upsert_feedback(conn, session_id, record)
        _upsert_history(conn, user_id, case_version_id, record)
        counts["history"] += 1

    return counts


# ── the pieces ───────────────────────────────────────────────────────

def _ensure_engine_version(conn, *, dry_run: bool) -> uuid.UUID:
    """
    The engine the pilot ran under.

    `is_current` stays false — `only_one_current_engine` is a partial unique
    index, and the shipped engine is 1.0.0. This row exists to interpret old
    scores, not to produce new ones.
    """
    engine_id = stable_id("engine", ENGINE_VERSION)
    if dry_run:
        return engine_id
    conn.execute(sa.text("""
        INSERT INTO engine_versions
            (id, version, detector_version, lexicon_version, encoder_model,
             thresholds, is_current, notes)
        VALUES (:id, :version, '0.9.0-pilot', '0.9.0-pilot', NULL,
                CAST(:thresholds AS jsonb), false, :notes)
        ON CONFLICT (version) DO UPDATE SET notes = EXCLUDED.notes
    """), {"id": engine_id, "version": ENGINE_VERSION,
           "thresholds": json.dumps(PILOT.to_row()), "notes": ENGINE_NOTES})
    return conn.execute(sa.text(
        "SELECT id FROM engine_versions WHERE version = :v"),
        {"v": ENGINE_VERSION}).scalar_one()


def _case_version_ids(conn) -> dict[str, uuid.UUID]:
    """case_1 … case_5 -> the seeded case_versions row, via the slug map."""
    rows = conn.execute(sa.text("""
        SELECT DISTINCT ON (c.slug) c.slug, cv.id
        FROM case_versions cv JOIN cases c ON c.id = cv.case_id
        ORDER BY c.slug, cv.version DESC
    """)).all()
    by_slug = {slug: cv_id for slug, cv_id in rows}
    return {case_id: by_slug[slug] for case_id, slug in CASE_SLUGS.items()
            if slug in by_slug}


def _upsert_profile(conn, user_id, research_pid, participant) -> None:
    """
    A participant.

    `profiles.id` references `auth.users`, which Supabase owns in production.
    The pilot participants have no account and never will — no email, no
    credentials, nobody can sign in as them — so the auth row is a placeholder
    that exists only to satisfy the foreign key. This is the one place that
    writes to `auth.users`, and it is the line to replace with Supabase's admin
    API if this is ever run against a live project.
    """
    conn.execute(sa.text(
        "INSERT INTO auth.users (id) VALUES (:id) ON CONFLICT (id) DO NOTHING"),
        {"id": user_id})
    conn.execute(sa.text("""
        INSERT INTO profiles (id, research_pid, year_of_training, timezone,
                              consent_research, consent_version, consent_at)
        VALUES (:id, :pid, :year, 'UTC', true, 'pilot-2026-07', now())
        ON CONFLICT (id) DO UPDATE SET year_of_training = EXCLUDED.year_of_training
    """), {"id": user_id, "pid": research_pid,
           "year": year_of_training(participant.get("year_of_study", ""))})


def _upsert_session(conn, session_id, user_id, case_version_id, record,
                    participant) -> None:
    confidence = participant.get("confidence_pre")
    conn.execute(sa.text("""
        INSERT INTO sessions (id, user_id, case_version_id, sequence_index,
                              status, confidence_pre, started_at, ended_at,
                              last_activity_at, diagnosis_submitted_at)
        VALUES (:id, :uid, :cv, :seq, 'completed', :confidence,
                :started, :ended, :ended, :ended)
        ON CONFLICT (id) DO UPDATE SET status = 'completed'
    """), {"id": session_id, "uid": user_id, "cv": case_version_id,
           "seq": participant["session_sequence"],
           "confidence": int(confidence) if confidence else None,
           "started": record["start_time"], "ended": record["end_time"]})


def _insert_events(conn, session_id, record) -> int:
    """
    The synthesised log.

    `session_events` is append-only — the trigger refuses UPDATE and DELETE —
    so idempotency cannot be an upsert. Instead: if this session already has
    events, leave them alone. Deterministic ids make that safe; a half-finished
    import is re-run from the top and the events it already wrote are kept.
    """
    already = conn.execute(sa.text(
        "SELECT count(*) FROM session_events WHERE session_id = :sid"),
        {"sid": session_id}).scalar_one()
    if already:
        return 0

    events = synthesise_events(record)
    for event in events:
        conn.execute(sa.text("""
            INSERT INTO session_events (session_id, seq, type, payload, created_at)
            VALUES (:sid, :seq, CAST(:type AS event_type),
                    CAST(:payload AS jsonb), :created_at)
        """), {"sid": session_id, "seq": event["seq"], "type": event["type"],
               "payload": json.dumps(event["payload"]),
               "created_at": event["created_at"]})
    return len(events)


def _upsert_result(conn, session_id, record, engine_id) -> None:
    """
    The pilot's own numbers, verbatim.

    `bias_detail` is the pilot's `biases_detected` block unchanged. It has no
    `counters` and no `rule_fired` — both were added in T-016 — so these
    sixteen rows are the only ones in the table without them. A reader that
    assumes §8.5's current shape will break on exactly the oldest data, which
    is worth knowing before writing that reader.

    The scorecards are the pilot's `clinical_eval` blocks, also unchanged, and
    also not §8.6's shape. Rebuilding them would be recomputation, and
    criterion 3 says the results match the original JSON exactly.
    """
    biases = record["biases_detected"]
    clinical = record["clinical_eval"]
    case = get_case(record["case_id"])
    required = case["required_topics"]
    covered = record.get("topics_covered", [])

    conn.execute(sa.text("""
        INSERT INTO session_results (
            session_id, question_count, examination_count, investigation_count,
            duration_seconds, coverage_pct, topics_hit, topics_missed,
            diagnosis_submitted, diagnosis_verdict,
            anchoring_detected, anchoring_score,
            premature_closure_detected, premature_closure_score,
            confirmation_bias_detected, confirmation_bias_score,
            bias_detail, exam_scorecard, investigation_scorecard,
            key_investigations_done, key_investigations_total, engine_version_id)
        VALUES (
            :sid, :q, :exams, :invs, :duration, :coverage, :hit, :missed,
            :diagnosis, :verdict,
            :a_det, :a_score, :p_det, :p_score, :c_det, :c_score,
            CAST(:bias_detail AS jsonb), CAST(:exam_card AS jsonb),
            CAST(:inv_card AS jsonb), :key_done, :key_total, :engine)
        ON CONFLICT (session_id) DO UPDATE SET
            bias_detail = EXCLUDED.bias_detail,
            engine_version_id = EXCLUDED.engine_version_id,
            computed_at = now()
    """), {
        "sid": session_id,
        "q": record["question_count"],
        "exams": len(record.get("exams_performed", [])),
        "invs": len(record.get("investigations_ordered", [])),
        "duration": duration_of(record),
        "coverage": coverage_of(record),
        "hit": [t for t in required if t in covered],
        "missed": [t for t in required if t not in covered],
        "diagnosis": record["diagnosis_submitted"] or "",
        "verdict": clinical["diagnosis"]["verdict"],
        "a_det": biases["anchoring"]["detected"],
        "a_score": biases["anchoring"]["score"],
        "p_det": biases["premature_closure"]["detected"],
        "p_score": biases["premature_closure"]["score"],
        "c_det": biases["confirmation_bias"]["detected"],
        "c_score": biases["confirmation_bias"]["score"],
        "bias_detail": json.dumps(biases),
        "exam_card": json.dumps(clinical["examinations"]),
        "inv_card": json.dumps(clinical["investigations"]),
        "key_done": len(clinical["investigations"]["key_done"]),
        "key_total": clinical["investigations"]["total_key"],
        "engine": engine_id,
    })


def _upsert_feedback(conn, session_id, record) -> int:
    lines = record.get("feedback_given") or []
    if not lines:
        return 0
    existing = conn.execute(sa.text(
        "SELECT count(*) FROM feedback_texts WHERE session_id = :sid"),
        {"sid": session_id}).scalar_one()
    if existing:
        return 0
    conn.execute(sa.text("""
        INSERT INTO feedback_texts (session_id, lines, generator, prompt_version)
        VALUES (:sid, :lines, 'llm', 'pilot-2026-07')
    """), {"sid": session_id, "lines": list(lines)})
    return 1


def _upsert_history(conn, user_id, case_version_id, record) -> None:
    """
    `user_case_history`, using the same ranking as T-017's `record_attempt`.

    Written directly rather than through the repository because that method
    reads `auth.uid()` from the request's actor, and there is no request here.
    """
    from nidan.domain.selection import better_verdict

    case_id = conn.execute(sa.text(
        "SELECT case_id FROM case_versions WHERE id = :id"),
        {"id": case_version_id}).scalar_one()
    verdict = record["clinical_eval"]["diagnosis"]["verdict"]
    existing = conn.execute(sa.text(
        "SELECT best_verdict FROM user_case_history "
        "WHERE user_id = :uid AND case_id = :cid"),
        {"uid": user_id, "cid": case_id}).scalar()

    conn.execute(sa.text("""
        INSERT INTO user_case_history
            (user_id, case_id, times_attempted, first_attempt, last_attempt,
             best_verdict)
        VALUES (:uid, :cid, 1, :at, :at, :verdict)
        ON CONFLICT (user_id, case_id) DO UPDATE SET
            last_attempt = GREATEST(user_case_history.last_attempt, EXCLUDED.last_attempt),
            best_verdict = :best
    """), {"uid": user_id, "cid": case_id, "at": record["start_time"],
           "verdict": verdict, "best": better_verdict(existing, verdict)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be imported, write nothing")
    args = parser.parse_args()

    # Deliberately NOT through repo_scope.
    #
    # This is an operator task, like alembic, not an application request. It
    # writes `engine_versions` and `auth.users`, and migration 020 grants the
    # application role SELECT on the first and nothing at all on the second —
    # on purpose. Widening those grants to let a script through would also
    # widen them for `nidan_service`, which is the role the anonymous-trial
    # path runs as, and that is far too high a price for a run-once import.
    #
    # So it connects as the migrating user, which is who runs migrations and
    # who owns these tables.
    with get_engine().begin() as conn:
        counts = backfill(conn, dry_run=args.dry_run)

    if args.dry_run:
        print(f"Would import {counts['sessions']} pilot sessions.")
        return
    print("Imported the pilot:")
    for name, count in counts.items():
        print(f"  {name:<10} {count}")


if __name__ == "__main__":
    main()
