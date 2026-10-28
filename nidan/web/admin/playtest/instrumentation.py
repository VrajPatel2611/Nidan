"""
What the right-hand panel of Playtest shows (BUILD_PLAN T-022, UX_SPEC §12.5).

**The numbers come from the engine, not from here.** Every counter, flag, score
and rule is read off the `AssessmentResult` that `assess()` returns for the
events so far. This module adds only what the engine does not report and an
author needs in order to understand it:

- *why* a question matched a topic — the keyword, found by the same scan
  `extract_topics` performs over the same lexicon;
- *which* contradictory clues were explored — the engine reports the count `k`,
  and the per-clue breakdown is checked against it (`clue_mismatch`) so the
  panel can never quietly disagree with the detector;
- possible persona leakage — a heuristic, labelled as one.

Nothing here writes anything, anywhere.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from nidan.domain.assessment.bias import clue_keywords
from nidan.domain.assessment.engine import AssessmentResult, EngineVersion, assess
from nidan.domain.assessment.topics import TOPIC_KEYWORDS, extract_topics
from nidan.domain.events import Event

# The keys `assess()` reads from a case. A draft missing one would raise a
# KeyError deep inside a detector; the panel names the gap instead.
ENGINE_KEYS: tuple[str, ...] = (
    "required_topics", "anchor_topic", "anchor_keywords",
    "alternative_topics", "contradictory_clues", "minimum_questions",
)

# Display order and plain-language headings for the three detectors. The
# technical name stays visible beside it: this is an authoring tool, and the
# rule labels (A1, P2, ...) only make sense against it.
DETECTORS: tuple[tuple[str, str, str], ...] = (
    ("anchoring", "Diagnostic focus", "anchoring"),
    ("premature_closure", "History completeness", "premature closure"),
    ("confirmation_bias", "Evidence exploration", "confirmation"),
)


def missing_engine_keys(case: Mapping[str, Any]) -> list[str]:
    return [key for key in ENGINE_KEYS if key not in case]


def topic_reasons(text: str) -> list[tuple[str, str]]:
    """
    Each topic `extract_topics` finds in `text`, with the keyword that matched.

    The topics are `extract_topics`'s own answer; the keyword is the first one
    in that topic's lexicon entry present in the text, which is the one its loop
    stops at.
    """
    lowered = text.lower()
    reasons = []
    for topic in extract_topics(text):
        keyword = next(kw for kw in TOPIC_KEYWORDS[topic] if kw in lowered)
        reasons.append((topic, keyword))
    return reasons


def _turns(events: Sequence[Event], required: set[str]) -> list[dict[str, Any]]:
    """One entry per question: matched topics with reasons, and any leakage."""
    turns: list[dict[str, Any]] = []
    for i, event in enumerate(events):
        if event.type != "question":
            continue
        question = event.payload["text"]
        matched = [
            {"topic": t, "keyword": kw, "required": t in required}
            for t, kw in topic_reasons(question)
        ]
        reply = next(
            (e.payload["text"] for e in events[i + 1:i + 2]
             if e.type == "patient_reply"), None)
        asked = {m["topic"] for m in matched}
        leaks = []
        if reply is not None:
            leaks = [
                {"topic": t, "keyword": kw}
                for t, kw in topic_reasons(reply)
                if t in required and t not in asked
            ]
        turns.append({
            "number": len(turns) + 1,
            "question": question,
            "matched": matched,
            "leaks": leaks,
        })
    return turns


def _clues(case: Mapping[str, Any], questions: Sequence[str]) -> list[dict[str, Any]]:
    """Each contradictory clue, whether a question touched it, and with what."""
    lowered = [q.lower() for q in questions]
    clues = []
    for clue in case["contradictory_clues"]:
        keywords = clue_keywords(clue)
        hit = next((kw for kw in keywords for q in lowered if kw in q), None)
        clues.append({
            "label": keywords[0] if keywords else "(empty clue)",
            "keywords": keywords,
            "explored_by": hit,
        })
    return clues


def build(events: Sequence[Event], case: Mapping[str, Any],
          engine: EngineVersion | None = None) -> dict[str, Any]:
    """Everything `_instrumentation.html` renders, for the events so far."""
    missing = missing_engine_keys(case)
    if missing:
        return {"missing": missing}

    result: AssessmentResult = assess(events, dict(case), engine)
    bias = result.bias_detail
    required = list(case["required_topics"])

    questions = [e.payload["text"] for e in events if e.type == "question"]
    clues = _clues(case, questions)
    explored = sum(1 for c in clues if c["explored_by"])
    k = int(bias["confirmation_bias"]["counters"]["k"])

    turns = _turns(events, set(required))

    return {
        "missing": [],
        "engine_version": result.engine_version.version,
        "turns": turns,
        "counters": {
            "q": result.question_count,
            "a": bias["anchoring"]["counters"]["a"],
            "m": bias["anchoring"]["counters"]["m"],
            "c_hit": len(result.topics_hit),
            "c_total": len(required),
            "c_pct": result.coverage_pct,
            "k": k,
            "K": int(bias["confirmation_bias"]["counters"]["K"]),
            "key_done": result.key_investigations_done,
            "key_total": result.key_investigations_total,
        },
        "detectors": [
            {
                "key": key,
                "heading": heading,
                "technical": technical,
                "detected": bool(bias[key]["detected"]),
                "score": float(bias[key]["score"]),
                "rule": bias[key]["rule_fired"],
                "reason": bias[key]["reason"],
            }
            for key, heading, technical in DETECTORS
        ],
        "clues": clues,
        "clues_explored": explored,
        # The breakdown above is this module's; `k` is the detector's. If they
        # ever differ, the panel says so rather than showing either silently.
        "clue_mismatch": explored != k,
        "topics_missed": result.topics_missed,
        "leak_count": sum(len(t["leaks"]) for t in turns),
        "diagnosis": result.diagnosis_submitted or None,
        "diagnosis_verdict": result.diagnosis_verdict
        if result.diagnosis_submitted else None,
    }
