"""
A learner's own data, as JSON (BUILD_PLAN T-038 criterion 1, `PRD` FR-11.3).

`PRD` 1.9 is the whole written requirement — "data export produces JSON of all
sessions within 24 h" — so the shape is decided here. Two rules shaped it.

## It carries what the learner wrote, and what the learner was shown

Those are the two things that are unambiguously theirs: the questions they
typed, the diagnoses they submitted, the patient's replies to them, and the
feedback prose written about it. Plus the facts of each session — which case,
when, how many questions, what coverage, what verdict.

## It does not read `session_results`' detector columns, and that is CT-5

`session_results` has `anchoring_detected`, `confirmation_bias_score`,
`bias_detail` and five more like them. **An export is learner-facing text** —
a file emailed to them — so `PRD` P1's ban on bias vocabulary applies to it
exactly as it applies to a response, and `bias_detail`'s own `reason` strings
contain the forbidden words verbatim ("Confirmation bias occurs when…").

The rule in `CLAUDE.md` is that a detector result reaches a learner through
`api/v1/reasoning.py` and nowhere else. This module obeys it by **not reading
those columns at all**, rather than by reading and filtering them. Nothing is
lost: `feedback_texts.lines` is the neutral prose the learner already read,
and it is in the export in full.

The alternative — importing `reasoning_json` here — would have meant the jobs
worker importing `nidan.api.v1`, whose `__init__` registers every route on a
Flask blueprint as a side effect. A background job should not boot the API to
format a number.

## Every column is named

No `SELECT *`, anywhere, for the same reason `case_view.py` names its fields:
a column added by a later migration would otherwise appear in an export with
no decision and no review. `session_results` gains columns regularly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories.base import Repository

# The format, versioned. A learner who exported twice should be able to tell
# whether a difference is their data changing or ours.
EXPORT_VERSION = "1"


class ExportRepository(Repository):

    def gather(self, user_id: UUID) -> dict[str, Any]:
        """
        Everything the export contains, for one user.

        **Scoped by an explicit `user_id` as well as by RLS**, because the
        worker runs as a `ServiceActor` and that bypasses RLS entirely
        (`ADR-0016`). Under a service actor the `WHERE user_id = :uid` is not
        belt-and-braces, it is the only thing standing between one learner's
        export and another's — so it is asserted rather than assumed.
        """
        if not isinstance(self._actor, ServiceActor):
            # A learner-scoped caller would be safe but would also be a second
            # code path with different guarantees. One caller, one guarantee.
            raise PermissionError(
                "the export is built by the jobs worker; a request-scoped "
                "actor should not be assembling another process's payload")

        profile = self._profile(user_id)
        if profile is None:
            raise LookupError(f"no profile for {user_id}")

        sessions = self._sessions(user_id)
        events = self._events(user_id)
        feedback = self._feedback(user_id)

        # Keyed by `str`, not `UUID`, and that is a bug fixed rather than a
        # style choice. `_jsonable` turns each session's `session_id` into a
        # string on the way out, so a dict keyed by the `UUID` the events
        # carry never matched it -- `by_session.get(...)` returned None for
        # every session and every transcript came back empty. Nothing raised:
        # an empty list is a valid transcript, the export serialised, and the
        # file looked right apart from containing none of the learner's words.
        # `test_the_export_carries_every_event` counts them for that reason.
        by_session: dict[str, list[dict[str, Any]]] = {}
        for row in events:
            by_session.setdefault(str(row["session_id"]), []).append({
                "seq": row["seq"],
                "type": row["type"],
                "at": _iso(row["created_at"]),
                "payload": row["payload"],
            })

        return {
            "export_version": EXPORT_VERSION,
            "profile": profile,
            "sessions": [
                {
                    **session,
                    "transcript": by_session.get(str(session["session_id"]), []),
                    "feedback": feedback.get(str(session["session_id"])),
                }
                for session in sessions
            ],
            # Said in the file as well as in the email, because the file is
            # what gets kept. `DATA_MODEL` §10.2 and `UX_SPEC` S-20 both
            # require the learner to be told what deletion does not remove.
            "notes": [
                "This export contains what you wrote and what you were shown.",
                "Anonymised results linked to a random research code are "
                "retained after account deletion, so that published research "
                "stays reproducible. They are not linked to your name or "
                "email.",
            ],
        }

    # ── the four queries ────────────────────────────────────────────────

    def _profile(self, user_id: UUID) -> dict[str, Any] | None:
        row = self._conn.execute(sa.text("""
            SELECT display_name, professional_role, year_of_training, country,
                   timezone, subscription_tier, consent_research, consent_at,
                   consent_version, onboarded_at, created_at, deleted_at
            FROM profiles WHERE id = :uid
        """), {"uid": user_id}).mappings().first()
        if row is None:
            return None
        # `research_pid` is deliberately absent. It is the key that links an
        # erased account to retained results, and putting it in a file the
        # learner keeps would hand them — or anyone who later reads the file —
        # the one value that re-identifies the anonymised dataset.
        return {k: _jsonable(v) for k, v in row.items()}

    def _sessions(self, user_id: UUID) -> list[dict[str, Any]]:
        rows = self._conn.execute(sa.text("""
            SELECT s.id AS session_id, s.sequence_index, s.status,
                   s.confidence_pre, s.started_at, s.ended_at,
                   s.diagnosis_submitted_at,
                   c.slug AS case_slug, cv.title AS case_title,
                   cv.version AS case_version,
                   r.question_count, r.examination_count,
                   r.investigation_count, r.duration_seconds, r.coverage_pct,
                   r.diagnosis_submitted, r.diagnosis_verdict,
                   r.key_investigations_done, r.key_investigations_total
              FROM sessions s
              JOIN case_versions cv ON cv.id = s.case_version_id
              JOIN cases c          ON c.id  = cv.case_id
              LEFT JOIN session_results r ON r.session_id = s.id
             WHERE s.user_id = :uid
             ORDER BY s.started_at ASC
        """), {"uid": user_id}).mappings().all()
        return [{k: _jsonable(v) for k, v in row.items()} for row in rows]

    def _events(self, user_id: UUID) -> list[Mapping[str, Any]]:
        return self._conn.execute(sa.text("""
            SELECT e.session_id, e.seq, e.type, e.payload, e.created_at
              FROM session_events e
              JOIN sessions s ON s.id = e.session_id
             WHERE s.user_id = :uid
             ORDER BY e.session_id, e.seq
        """), {"uid": user_id}).mappings().all()

    def _feedback(self, user_id: UUID) -> dict[str, dict[str, Any]]:
        rows = self._conn.execute(sa.text("""
            SELECT f.session_id, f.lines, f.generator, f.was_helpful,
                   f.rated_at, f.created_at
              FROM feedback_texts f
              JOIN sessions s ON s.id = f.session_id
             WHERE s.user_id = :uid
        """), {"uid": user_id}).mappings().all()
        return {
            str(row["session_id"]): {
                "lines": list(row["lines"]),
                "generator": row["generator"],
                "was_helpful": row["was_helpful"],
                "rated_at": _iso(row["rated_at"]),
                "created_at": _iso(row["created_at"]),
            }
            for row in rows
        }


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _jsonable(value: Any) -> Any:
    """
    Postgres types `json` cannot serialise, converted at the edge.

    NUMERIC arrives as `Decimal` and TIMESTAMPTZ as `datetime`; both raise in
    `json.dumps`, and a worker that fails at serialisation time has already
    done all the expensive work.
    """
    import datetime
    import decimal
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value
