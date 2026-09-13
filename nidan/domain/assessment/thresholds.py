"""
The constants every detector decision is made against (BUILD_PLAN T-016).

**These are data, not code.** `DATA_MODEL` §6.4 makes `engine_versions` the
place they live, and every row in `session_results` records which engine
version produced it. That is what makes a past result interpretable: a score of
0.75 means nothing unless you know the concentration threshold was 0.60 at the
time.

It is also what turns threshold calibration into a data operation — replay
stored events under a candidate row and measure the delta — rather than an edit
to `bias.py` that silently invalidates every historical result at once.
`DATA_MODEL` §6.4 puts it exactly: it is "the mechanism that would have made the
pilot's stale 0.88 confirmation scores a query rather than a forensic exercise."

`PILOT` below is the fallback for callers that have no database — the detector
unit tests, the validation harness, and the server-rendered prototype. The path
that *writes* a result never uses it: `assess()` takes an `EngineVersion` loaded
from the table. `tests/db/test_seed.py` compares the two by value, so the
fallback cannot drift from the row it stands in for.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Thresholds:
    """
    One engine's constants. Frozen: a detector that could change a threshold
    mid-assessment would produce a result no version number describes.

    Field names mirror `DATA_MODEL` §8.7's JSON exactly, so the mapping between
    the row and this object is readable rather than remembered.
    """

    # anchoring
    anchoring_concentration: float      # A1 fires above this share of questions
    anchoring_min_questions: int        # A1 needs at least this many questions
    anchoring_a2_min_anchor: int        # A2 needs at least this many anchor hits
    anchoring_a2_score: float           # and scores a flat value

    # premature closure
    premature_coverage: float           # P2 fires below this coverage ratio
    premature_score_floor: float        # a detection never scores below this

    # confirmation bias
    confirmation_clue_ratio: float      # C2 fires below this exploration ratio
    confirmation_min_questions: int     # C2 needs at least this many questions
    confirmation_c1_score: float        # C1 scores a flat value

    # topic matching
    topic_matching_mode: str = "keyword"
    similarity_threshold: float | None = None

    @classmethod
    def from_row(cls, thresholds: dict[str, Any]) -> Thresholds:
        """
        Build from an `engine_versions.thresholds` document.

        Every key is required. A missing one would otherwise fall back to a
        default nobody chose, and the result would be attributed to an engine
        version that does not describe it — which is the exact failure this
        table exists to prevent.
        """
        try:
            anchoring = thresholds["anchoring"]
            premature = thresholds["premature_closure"]
            confirmation = thresholds["confirmation_bias"]
            topics = thresholds.get("topic_matching", {})
            return cls(
                anchoring_concentration=float(anchoring["concentration"]),
                anchoring_min_questions=int(anchoring["min_questions"]),
                anchoring_a2_min_anchor=int(anchoring["a2_min_anchor"]),
                anchoring_a2_score=float(anchoring["a2_score"]),
                premature_coverage=float(premature["coverage"]),
                premature_score_floor=float(premature["score_floor"]),
                confirmation_clue_ratio=float(confirmation["clue_ratio"]),
                confirmation_min_questions=int(confirmation["min_questions"]),
                confirmation_c1_score=float(confirmation["c1_score"]),
                topic_matching_mode=topics.get("mode", "keyword"),
                similarity_threshold=topics.get("similarity_threshold"),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(
                f"engine_versions.thresholds is not a complete threshold "
                f"document (DATA_MODEL §8.7): {e}") from e

    def to_row(self) -> dict[str, Any]:
        """The inverse, for writing a new engine version."""
        return {
            "anchoring": {
                "concentration": self.anchoring_concentration,
                "min_questions": self.anchoring_min_questions,
                "a2_min_anchor": self.anchoring_a2_min_anchor,
                "a2_score": self.anchoring_a2_score,
            },
            "premature_closure": {
                "coverage": self.premature_coverage,
                "score_floor": self.premature_score_floor,
            },
            "confirmation_bias": {
                "clue_ratio": self.confirmation_clue_ratio,
                "min_questions": self.confirmation_min_questions,
                "c1_score": self.confirmation_c1_score,
            },
            "topic_matching": {
                "mode": self.topic_matching_mode,
                "similarity_threshold": self.similarity_threshold,
            },
        }


# The values validated in the pilot: 51/54 detector decisions correct across 18
# labelled transcripts. Seeded into `engine_versions` as version 1.0.0 by
# migration 018, and compared against this object by value in tests/db.
#
# Used only where no database is available. Anything that writes a
# `session_results` row goes through `assess()` with a loaded EngineVersion.
PILOT = Thresholds(
    anchoring_concentration=0.60,
    anchoring_min_questions=4,
    anchoring_a2_min_anchor=3,
    anchoring_a2_score=0.85,
    premature_coverage=0.60,
    premature_score_floor=0.10,
    confirmation_clue_ratio=0.25,
    confirmation_min_questions=5,
    confirmation_c1_score=0.90,
    topic_matching_mode="keyword",
    similarity_threshold=None,
)
