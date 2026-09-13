"""
Shared type aliases for the domain layer.

These name the dictionary shapes the domain passes around. They are aliases,
not validation — `Session` is a plain dict at runtime. Their value is that a
signature reading `(session: Session, case: Case) -> DetectorResult` says what a
function does, where `(dict, dict) -> dict` says nothing.

NOTE (BUILD_PLAN T-013): `Session` becomes a reconstruction from an append-only
event log. Naming the shape here means that change has one place to start.
"""

from typing import Any, TypedDict

# A clinical case definition from nidan.domain.content.cases.
Case = dict[str, Any]

# The short {id, title, intro} form used for case listings.
CaseSummary = dict[str, str]

# Live consultation state: questions asked, topics covered, exams, diagnosis.
Session = dict[str, Any]


class DetectorResult(TypedDict):
    """
    What every bias detector returns.

    `evidence` carries the learner's own questions (or the topics they missed).
    It is not optional: property P2 requires that a flag can always be traced
    back to what the learner actually did (ADR-0004).

    `rule_fired` and `counters` were added in T-016 (`DATA_MODEL` §8.5).
    `counters` holds the intermediate values a score was computed from, and it
    is the addition that makes replay verifiable: a recomputation mismatch can
    be localised to a specific counter rather than merely observed as a
    different number. `rule_fired` records which of the two OR-ed rules
    triggered, which the threshold-impact preview needs.

    Both are required, not optional. A detector that omitted them would produce
    a result that cannot be explained or replayed — and it would do so
    silently, since nothing downstream would raise.
    """

    detected: bool
    score: float
    rule_fired: str | None
    reason: str
    evidence: list[str]
    counters: dict[str, float]


# {"anchoring": DetectorResult, "premature_closure": ..., "confirmation_bias": ...}
BiasResults = dict[str, DetectorResult]

# Output of nidan.domain.assessment.clinical.evaluate_clinical.
ClinicalEval = dict[str, Any]
