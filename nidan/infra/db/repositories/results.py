"""
Engine versions and stored results (BUILD_PLAN T-016).

Two tables, and the link between them is the point: every row in
`session_results` records the `engine_version_id` that produced it, so a score
stays interpretable after the thresholds change. `DATA_MODEL` §6.4 calls this
"the mechanism that would have made the pilot's stale 0.88 confirmation scores
a query rather than a forensic exercise."

**Storing a result does not contradict T-013.** That task deliberately stores
no scores and recomputes the feedback screen from the log every time, because a
stored score is a cache of a conclusion and a cache can disagree with its own
log. Both hold here, because they answer different questions:

* the feedback screen is recomputed, always — what a learner reads is derived
  live from their events;
* `session_results` is the durable analytical record — progress trends,
  research export, threshold calibration — stamped with the engine that made it.

The cache-drift risk is handled rather than accepted: the golden-file test
replays the pilot sessions and fails if a recomputation stops matching, so a
divergence is a finding rather than a silent inconsistency.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.domain.assessment.engine import AssessmentResult, EngineVersion
from nidan.domain.assessment.thresholds import Thresholds
from nidan.infra.db.repositories.base import Repository


class EngineVersionRepository(Repository):
    """
    Read-only. Engine versions are created by migration or by the calibration
    tooling (Phase 5), never by a request — a request that could write one
    could change what every future score means.
    """

    def current(self) -> EngineVersion | None:
        """
        The engine in force. `only_one_current_engine` (migration 008) is a
        partial unique index, so there is at most one.
        """
        row = self._conn.execute(sa.text("""
            SELECT id, version, detector_version, lexicon_version,
                   encoder_model, thresholds
            FROM engine_versions WHERE is_current
        """)).mappings().first()
        return _to_engine_version(row) if row else None

    def by_id(self, engine_version_id: UUID) -> EngineVersion | None:
        """
        A specific version, for interpreting an old result or replaying under a
        candidate one.
        """
        row = self._conn.execute(sa.text("""
            SELECT id, version, detector_version, lexicon_version,
                   encoder_model, thresholds
            FROM engine_versions WHERE id = :id
        """), {"id": engine_version_id}).mappings().first()
        return _to_engine_version(row) if row else None


class ResultRepository(Repository):
    """
    Stored assessments.

    `own_session_results` (migration 016) inherits ownership through the parent
    session, so these queries carry no owner clause of their own.
    """

    _OWNERSHIP = ""

    def _ownership_params(self) -> dict[str, Any]:
        return {}

    def get(self, session_id: UUID) -> Mapping[str, Any] | None:
        return self._conn.execute(sa.text(f"""
            SELECT r.* FROM session_results r
            WHERE r.session_id = :sid
              AND EXISTS (SELECT 1 FROM sessions s
                          WHERE s.id = :sid {self._OWNERSHIP})
        """), {"sid": session_id, **self._ownership_params()}).mappings().first()

    def save(self, session_id: UUID, result: AssessmentResult) -> None:
        """
        Write the assessment for a session.

        `ON CONFLICT DO UPDATE` rather than plain INSERT: `session_results` is
        keyed on `session_id`, and a recomputation under a new engine version
        must replace the old row rather than fail. The row is derived data —
        unlike `session_events`, which is append-only precisely because it is
        not derived.
        """
        if result.engine_version.id is None:
            raise ValueError(
                "refusing to store a result with no engine_version_id: a score "
                "whose thresholds are unknown cannot be interpreted later "
                "(DATA_MODEL §6.4)")

        params: dict[str, Any] = {
            "sid": session_id,
            "question_count": result.question_count,
            "examination_count": result.examination_count,
            "investigation_count": result.investigation_count,
            "duration_seconds": result.duration_seconds,
            "coverage_pct": result.coverage_pct,
            "topics_hit": list(result.topics_hit),
            "topics_missed": list(result.topics_missed),
            "diagnosis_submitted": result.diagnosis_submitted,
            "diagnosis_verdict": result.diagnosis_verdict,
            "bias_detail": json.dumps(result.bias_detail),
            "exam_scorecard": json.dumps(result.exam_scorecard),
            "investigation_scorecard": json.dumps(result.investigation_scorecard),
            "key_done": result.key_investigations_done,
            "key_total": result.key_investigations_total,
            "engine_version_id": result.engine_version.id,
            **result.scalars,
            # The ownership predicate is interpolated into the SQL above, so
            # its parameters have to travel with it. Forgetting them fails at
            # the driver rather than silently writing an unowned row — which is
            # the right way round, but only because the clause is a bind
            # parameter and not a formatted string.
            **self._ownership_params(),
        }

        self._conn.execute(sa.text(f"""
            INSERT INTO session_results (
                session_id, question_count, examination_count,
                investigation_count, duration_seconds,
                coverage_pct, topics_hit, topics_missed,
                diagnosis_submitted, diagnosis_verdict,
                anchoring_detected, anchoring_score,
                premature_closure_detected, premature_closure_score,
                confirmation_bias_detected, confirmation_bias_score,
                bias_detail, exam_scorecard, investigation_scorecard,
                key_investigations_done, key_investigations_total,
                engine_version_id)
            SELECT :sid, :question_count, :examination_count,
                   :investigation_count, :duration_seconds,
                   :coverage_pct, :topics_hit, :topics_missed,
                   :diagnosis_submitted, :diagnosis_verdict,
                   :anchoring_detected, :anchoring_score,
                   :premature_closure_detected, :premature_closure_score,
                   :confirmation_bias_detected, :confirmation_bias_score,
                   CAST(:bias_detail AS jsonb), CAST(:exam_scorecard AS jsonb),
                   CAST(:investigation_scorecard AS jsonb),
                   :key_done, :key_total, :engine_version_id
            WHERE EXISTS (SELECT 1 FROM sessions s
                          WHERE s.id = :sid {self._OWNERSHIP})
            ON CONFLICT (session_id) DO UPDATE SET
                question_count = EXCLUDED.question_count,
                examination_count = EXCLUDED.examination_count,
                investigation_count = EXCLUDED.investigation_count,
                duration_seconds = EXCLUDED.duration_seconds,
                coverage_pct = EXCLUDED.coverage_pct,
                topics_hit = EXCLUDED.topics_hit,
                topics_missed = EXCLUDED.topics_missed,
                diagnosis_submitted = EXCLUDED.diagnosis_submitted,
                diagnosis_verdict = EXCLUDED.diagnosis_verdict,
                anchoring_detected = EXCLUDED.anchoring_detected,
                anchoring_score = EXCLUDED.anchoring_score,
                premature_closure_detected = EXCLUDED.premature_closure_detected,
                premature_closure_score = EXCLUDED.premature_closure_score,
                confirmation_bias_detected = EXCLUDED.confirmation_bias_detected,
                confirmation_bias_score = EXCLUDED.confirmation_bias_score,
                bias_detail = EXCLUDED.bias_detail,
                exam_scorecard = EXCLUDED.exam_scorecard,
                investigation_scorecard = EXCLUDED.investigation_scorecard,
                key_investigations_done = EXCLUDED.key_investigations_done,
                key_investigations_total = EXCLUDED.key_investigations_total,
                engine_version_id = EXCLUDED.engine_version_id,
                computed_at = now()
        """), params)


def _to_engine_version(row: Mapping[str, Any]) -> EngineVersion:
    thresholds = row["thresholds"]
    if isinstance(thresholds, str):
        thresholds = json.loads(thresholds)
    return EngineVersion(
        id=row["id"],
        version=row["version"],
        detector_version=row["detector_version"],
        lexicon_version=row["lexicon_version"],
        encoder_model=row["encoder_model"],
        thresholds=Thresholds.from_row(thresholds),
    )
