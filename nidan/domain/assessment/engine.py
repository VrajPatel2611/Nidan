"""
The assessment engine (BUILD_PLAN T-016 ⭐, `TECH_SPEC` §4.4).

```python
assess(events, case, engine) -> AssessmentResult
```

**A pure function.** Same inputs, same outputs, always. No clock, no
randomness, no network, no database. That is not a stylistic preference — it is
the whole basis of the guarantee in `CLAUDE.md`:

> **The event log is the source of truth.** Derived state is reproducible from
> it. (`ADR-0003`)

and of the one above it:

> **The LLM never marks.** Every flag, score and verdict is deterministic
> Python. (`ADR-0005`)

Both become checkable here rather than merely asserted, because a function of
this shape can be replayed and compared. The pilot already relied on that
property without naming it: its data-integrity check recomputed bias flags from
stored questions and matched all 16 sessions exactly.

**Thresholds are inputs, not constants.** They arrive on the `EngineVersion`,
loaded from `engine_versions`, and the id travels with every result written.
That is what makes a past score interpretable — 0.75 means nothing unless you
know what it was measured against — and what makes calibration a data
operation rather than an edit to `bias.py` that invalidates history
(`DATA_MODEL` §6.4).

**The duration comes from the events, not from a clock**, for the same reason:
a session assessed today and re-assessed next year must report the same number.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from nidan.domain.assessment.bias import detect_all_biases
from nidan.domain.assessment.clinical import evaluate_clinical
from nidan.domain.assessment.thresholds import PILOT, Thresholds
from nidan.domain.events import Event
from nidan.domain.feedback_view import (
    build_examination_scorecard,
    build_investigation_scorecard,
)
from nidan.domain.session import replay
from nidan.domain.types import Case

# Scores are stored as NUMERIC(4,3) (DATA_MODEL §6.3). Rounding happens once,
# here, so the number written to the database and the number rendered on the
# page cannot disagree — two code paths rounding separately is the ordinary way
# "byte-identical" quietly stops being true.
SCORE_DECIMALS = 3
COVERAGE_DECIMALS = 2


@dataclass(frozen=True)
class EngineVersion:
    """
    One row of `engine_versions`, as the engine sees it.

    `id` is optional so the pilot values can be used without a database — the
    detector tests and the validation harness have no `engine_versions` table.
    Anything that WRITES a result has an id, because `session_results` requires
    one.
    """

    version: str
    detector_version: str
    lexicon_version: str
    thresholds: Thresholds
    encoder_model: str | None = None
    id: UUID | None = None

    @classmethod
    def pilot(cls) -> EngineVersion:
        """The values validated in the pilot. No id: nothing may be written under it."""
        return cls(version="1.0.0", detector_version="1.0.0",
                   lexicon_version="1.0.0", thresholds=PILOT)


@dataclass(frozen=True)
class AssessmentResult:
    """
    Everything `session_results` stores, plus what the feedback screen renders.

    One object rather than two, because they must agree: the row a researcher
    queries and the page a learner reads are the same assessment, and computing
    them separately is how they come to differ.
    """

    question_count: int
    examination_count: int
    investigation_count: int
    duration_seconds: int | None

    coverage_pct: float
    topics_hit: list[str]
    topics_missed: list[str]

    diagnosis_submitted: str
    diagnosis_verdict: str

    bias_detail: dict[str, Any]
    exam_scorecard: dict[str, list[str]]
    investigation_scorecard: dict[str, list[str]]

    key_investigations_done: int
    key_investigations_total: int

    engine_version: EngineVersion
    clinical_eval: dict[str, Any] = field(default_factory=dict)

    @property
    def scalars(self) -> dict[str, Any]:
        """
        The six detector scalars duplicated out of `bias_detail` for indexed
        queries (`DATA_MODEL` §6.3 explains why: JSONB extraction cannot use a
        btree index, and every analytical query filters on these).
        """
        out: dict[str, Any] = {}
        for name in ("anchoring", "premature_closure", "confirmation_bias"):
            detail = self.bias_detail[name]
            out[f"{name}_detected"] = bool(detail["detected"])
            out[f"{name}_score"] = float(detail["score"])
        return out


def assess(events: Iterable[Event], case: Case,
           engine: EngineVersion | None = None) -> AssessmentResult:
    """
    Assess one consultation from its event log.

    `engine` defaults to the pilot values so the function can be exercised
    without a database. A result written to `session_results` always passes a
    loaded version, because the row requires an `engine_version_id`.
    """
    engine = engine or EngineVersion.pilot()
    events = list(events)

    session = replay(events, case_id=case["id"],
                     started_at=_first_timestamp(events))

    bias_results = detect_all_biases(session, case,
                                     thresholds=engine.thresholds)
    clinical = evaluate_clinical(session, case)

    required = case["required_topics"]
    covered = session["topics_covered"]
    topics_hit = [t for t in required if t in covered]
    topics_missed = [t for t in required if t not in covered]

    investigations = clinical["investigations"]

    return AssessmentResult(
        question_count=session["question_count"],
        examination_count=len(session["exams_performed"]),
        investigation_count=len(session["investigations_ordered"]),
        duration_seconds=_duration_seconds(events),
        coverage_pct=round(
            (len(topics_hit) / len(required) * 100) if required else 0.0,
            COVERAGE_DECIMALS),
        topics_hit=topics_hit,
        topics_missed=topics_missed,
        # NOT NULL in the schema, and rightly: a result without a diagnosis is
        # an unfinished consultation, which has nothing to assess.
        diagnosis_submitted=session["diagnosis_submitted"] or "",
        diagnosis_verdict=clinical["diagnosis"]["verdict"],
        bias_detail=_round_scores(bias_results),
        exam_scorecard=build_examination_scorecard(session, case),
        investigation_scorecard=build_investigation_scorecard(session, case),
        key_investigations_done=len(investigations["key_done"]),
        # Stored rather than derived, because the total varies per case — the
        # denominator artefact that invalidated the pilot's key-test metric
        # (DATA_MODEL §6.3). Storing both makes the incomparability visible in
        # the data instead of hidden inside a ratio.
        key_investigations_total=investigations["total_key"],
        engine_version=engine,
        clinical_eval=clinical,
    )


def _first_timestamp(events: Sequence[Event]) -> str:
    """
    When the consultation started, from the log itself.

    Falls back to the epoch for an empty log rather than reading a clock: a
    clock would make `assess` impure, and an assessment of nothing has no
    duration to get wrong.
    """
    for event in events:
        if event.created_at is not None:
            return event.created_at.isoformat()
    return datetime.fromtimestamp(0).isoformat()


def _duration_seconds(events: Sequence[Event]) -> int | None:
    """
    Wall-clock seconds between the first and last event, or None.

    From the events, never from a clock. A session assessed today and
    re-assessed next year must report the same duration.
    """
    stamps = [e.created_at for e in events if e.created_at is not None]
    if len(stamps) < 2:
        return None
    return int((max(stamps) - min(stamps)).total_seconds())


def _round_scores(bias_results: dict[str, Any]) -> dict[str, Any]:
    """
    Round every score once, at the boundary.

    `session_results` stores NUMERIC(4,3). Rounding at the point of storage
    only would mean the page shows 0.8333 and the database holds 0.833, and a
    recomputation comparing the two would report a mismatch that is really a
    formatting difference.
    """
    rounded: dict[str, Any] = {}
    for name, detail in bias_results.items():
        entry = dict(detail)
        entry["score"] = round(float(entry["score"]), SCORE_DECIMALS)
        rounded[name] = entry
    return rounded
