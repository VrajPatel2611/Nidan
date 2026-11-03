"""
The only place a detector result becomes learner-facing text
(`PRD` P1, P3 · `UX_SPEC` U4 · contract tests CT-4, CT-5).

`API_CONTRACT` §6 states the rule: `reasoning[].id` uses **behavioural
identifiers** — `diagnostic_focus`, `history_completeness`,
`evidence_exploration` — "never `anchoring`, `premature_closure`,
`confirmation_bias`. The internal names never cross the API boundary."

**The detectors' own `reason` strings are not usable here, and finding out why
is the reason this module exists.** They read, in the engine today:

    "No significant anchoring pattern detected."
    "No premature closure detected — thorough workup completed."
    "Confirmation bias occurs when we seek only evidence that supports our
     first instinct."

Three of the six branches contain the exact vocabulary CT-5 forbids. Passing
`bias_detail[name]["reason"]` through — the obvious implementation, and the one
the server-rendered prototype uses — would ship the words "anchoring",
"premature closure" and "confirmation bias" to a learner.

So the text is rebuilt here from `counters`. That is what `counters` is for:
`DATA_MODEL` §8.5 added it in T-016 as "the intermediate values a score was
computed from", and those values are the learner's own actions — which is
exactly what `PRD` P3 and `ADR-0004` require a reason to cite. Nothing is
filtered or sanitised; the internal prose simply never reaches the boundary,
which is a stronger property than scrubbing it would be.

**Why the vocabulary is banned at all** (`PRD` P1): a learner told they
"anchored" learns the label. A learner told "6 of your 8 questions explored a
cardiac cause, and you asked 1 about other possibilities" learns what they
did. The second is also harder to argue with.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

# (internal detector key, API id, user-facing label).
#
# The API id is what a client branches on and is frozen by CT-4; the label is
# copy and may be reworded. The internal key appears only on the left of this
# table and nowhere in any response.
REASONING: Final[tuple[tuple[str, str, str], ...]] = (
    ("anchoring",         "diagnostic_focus",      "Diagnostic focus"),
    ("premature_closure", "history_completeness",  "History completeness"),
    ("confirmation_bias", "evidence_exploration",  "Evidence exploration"),
)

# CT-5's three terms, plus the snake_case forms that would arrive if a dict
# key were serialised instead of mapped.
#
# **`anchored` is deliberately NOT here**, and it was, briefly. It is a
# `diagnosis_verdict` enum value — `DATA_MODEL` §6.3 and `API_CONTRACT` §7's
# own `verdict_distribution` example both carry it — so banning it made the
# progress payload fail its own contract. `API_CONTRACT` §11 lists three
# terms and `CLAUDE.md` four; neither lists `anchored`, and widening the list
# past what the spec says is how a guard starts producing false positives
# that get it loosened for the wrong reason later.
#
# A verdict reaching a learner as the bare word "anchored" would be a P1
# problem — but it reaches them as a machine value a client maps to copy,
# exactly as `diagnostic_focus` maps to "Diagnostic focus". The wording is
# `UX_SPEC`'s to choose, and T-036 is where it gets chosen.
BANNED_VOCABULARY: Final[tuple[str, ...]] = (
    "anchoring", "premature closure", "premature_closure",
    "confirmation bias", "confirmation_bias",
)

# Shown beside a flagged dimension. Neutral, and deliberately an invitation
# rather than a verdict — `UX_SPEC` §11's tone: the learner is being coached,
# not marked.
_STATUS_LINE: Final[dict[str, str]] = {
    "diagnostic_focus":     "consider broadening",
    "history_completeness": "more ground to cover",
    "evidence_exploration": "look for what would change your mind",
}


def _diagnostic_focus_reason(c: Mapping[str, Any]) -> str:
    """
    Built from `counters` {q, a, m}: questions asked, questions on the trap
    topic, questions on alternatives.

    The anchor topic itself is NOT named. "6 of your 8 questions explored one
    line of enquiry" says what happened; "…explored a cardiac cause" would
    hand over `anchor_topic`, which is the field the detector watches and
    `PRD` FR-3.4 keeps away from a learner — and the feedback screen is
    exactly where a determined learner would go looking for it.
    """
    total, on_one, on_others = c.get("q", 0), c.get("a", 0), c.get("m", 0)
    if not total:
        return "You submitted a diagnosis without asking anything."
    return (f"{on_one} of your {total} questions followed a single line of "
            f"enquiry, and {on_others} explored other possibilities.")


def _history_completeness_reason(c: Mapping[str, Any]) -> str:
    """From `counters` {q, q_min, coverage}."""
    asked, expected = c.get("q", 0), c.get("q_min", 0)
    covered = c.get("coverage", 0.0)
    return (f"You asked {asked} questions and covered {round(covered * 100)}% "
            f"of the key history areas for this case. A thorough history here "
            f"usually takes around {expected}.")


def _evidence_exploration_reason(c: Mapping[str, Any]) -> str:
    """From `counters` {k, K}: findings explored, findings available."""
    explored, available = c.get("k", 0), c.get("K", 0)
    if not available:
        return "There was nothing recorded to weigh against your conclusion."
    return (f"You explored {explored} of {available} findings that pointed "
            f"away from your conclusion.")


_REASON_BUILDERS: Final[dict[str, Any]] = {
    "diagnostic_focus":     _diagnostic_focus_reason,
    "history_completeness": _history_completeness_reason,
    "evidence_exploration": _evidence_exploration_reason,
}


def reasoning_json(bias_detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    The `reasoning` array for `GET /v1/sessions/{id}/feedback`.

    Always all three dimensions, flagged or not. §6's point 2 — "always
    present and always cites the user's own actions" — and a product reason:
    showing only what went wrong turns the screen into a list of failures,
    while showing all three turns it into a description of how someone
    reasoned. `UX_SPEC` S-12 keeps the order fixed for the same reason.
    """
    out = []
    for internal_key, api_id, label in REASONING:
        detail = bias_detail.get(internal_key) or {}
        flagged = bool(detail.get("detected"))
        out.append({
            "id": api_id,
            "label": label,
            "flagged": flagged,
            "status_line": _STATUS_LINE[api_id] if flagged else None,
            "reason": _REASON_BUILDERS[api_id](detail.get("counters") or {}),
        })
    return out


def reasoning_trends_json(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    The `reasoning_trends` array for `GET /v1/progress` (`API_CONTRACT` §7).

    Same mapping, same three behavioural ids, for the same reason: CT-5 says
    "no response body **anywhere**", and a progress screen built from
    `anchoring_last10` would carry the word in a field name. The repository's
    column names are internal; this is the boundary.

    **`direction` is computed server-side**, which §7 states and gives the
    reason for: "so wording stays consistent." Two clients deriving it from
    two rates would eventually disagree about what 0.30 against 0.32 means,
    and a learner told "declining" by one screen and "stable" by another
    stops trusting both.

    **Fewer flags is better**, so a falling rate is `improving`. Worth saying
    out loud because the arithmetic reads backwards: `last10 < prev10` is good
    news.

    `direction` is None when there is no previous ten to compare against.
    Not "stable" — that would tell a learner with twelve sessions that their
    habits are unchanged, which is a claim about data that does not exist.
    """
    out = []
    for internal_key, api_id, label in REASONING:
        last10 = summary.get(f"{internal_key}_last10")
        prev10 = summary.get(f"{internal_key}_prev10")
        out.append({
            "id": api_id,
            "label": label,
            "last10_rate": round(float(last10), 3) if last10 is not None else None,
            "prev10_rate": round(float(prev10), 3) if prev10 is not None else None,
            "direction": _direction(last10, prev10),
        })
    return out


def _direction(last10: Any, prev10: Any) -> str | None:
    """`improving` when the flag fires less often than it used to."""
    if last10 is None or prev10 is None:
        return None
    last, prev = float(last10), float(prev10)
    # A tolerance, because these are averages of small integers: 3/10 against
    # 4/10 is one session, and calling that a trend would have a learner
    # chasing noise.
    if abs(last - prev) < 0.1:
        return "stable"
    return "improving" if last < prev else "declining"
