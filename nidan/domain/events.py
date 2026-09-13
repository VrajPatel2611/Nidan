"""
Consultation events (BUILD_PLAN T-013, ADR-0003).

Every action a learner takes during a consultation becomes one append-only row
in `session_events`. Session state is not stored anywhere: it is **replayed**
from these rows (`domain/session.py`). That is the third of the three
properties in CLAUDE.md — the event log is the source of truth, and derived
state is reproducible from it.

This module is pure data and validation. It holds no SQL and no I/O, so the
same definitions serve the writer (`infra/db/repositories/events.py`), the
replayer, and the assessment engine T-016 builds on top of them.

`DATA_MODEL` §8.2 calls the payload a "discriminated union, validated on
write", and `validate_payload` is that validation. It runs before the INSERT
rather than trusting a JSONB column to accept anything, because a malformed
payload is not discovered by the database at all — it is discovered months
later by a replay that quietly produces the wrong session.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# The `event_type` enum, migration 003. Kept in this order deliberately: it is
# the order a consultation produces them.
EVENT_TYPES: tuple[str, ...] = (
    "question",
    "patient_reply",
    "examination",
    "investigation",
    "early_diagnosis",
    "diagnosis",
    "feedback_viewed",
    "input_blocked",
)

# Payload shapes, DATA_MODEL §8.2. Required keys must be present; optional ones
# may be; anything else is refused.
#
# Refusing unknown keys is the point of validating at all. A typo'd key in a
# JSONB column is accepted silently, survives every test, and is found when a
# replay months later cannot see the field it expects.
# Allowed on every event type, never required.
#
# `provenance` marks an event that was not produced by a live consultation.
# `DATA_MODEL` §9.3 requires it on the 16 pilot sessions imported by T-018:
# their JSON preserved questions, examinations and investigations as separate
# blocks but not their interleaving, so the synthesised log is block-ordered and
# its timestamps are invented.
#
#     ⚠️ Backfilled events must be excluded from any timing analysis.
#
# Widening the contract here rather than letting the backfill skip validation:
# a script that bypasses the validator is a script that can write malformed
# events into an append-only table.
_UNIVERSAL_OPTIONAL: frozenset[str] = frozenset({"provenance"})

_SHAPES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    #                      required                          optional
    "question":        (frozenset({"text", "char_count"}), frozenset()),
    "patient_reply":   (frozenset({"text"}),
                        frozenset({"model", "prompt_version", "latency_ms",
                                   "matched_topics"})),
    "examination":     (frozenset({"key", "label", "finding"}),
                        frozenset({"was_case_specific"})),
    "investigation":   (frozenset({"key", "label", "result"}),
                        frozenset({"was_case_specific"})),
    "early_diagnosis": (frozenset({"text"}), frozenset()),
    "diagnosis":       (frozenset({"text"}), frozenset()),
    "feedback_viewed": (frozenset(), frozenset()),
    "input_blocked":   (frozenset({"reason"}), frozenset()),
}


@dataclass(frozen=True)
class Event:
    """
    One row of `session_events`.

    Frozen because the table is append-only — `session_events_append_only`
    (migration 010) refuses any UPDATE or DELETE. An object that could be
    mutated after the fact would misrepresent a row that genuinely cannot be.
    """

    seq: int
    type: str
    payload: Mapping[str, Any]
    created_at: datetime | None = None


def validate_payload(event_type: str, payload: Mapping[str, Any]) -> None:
    """
    Refuse a payload that does not match its type. Raises ValueError.

    Called before every append. The database will not do this for us: a JSONB
    column accepts any object at all.
    """
    if event_type not in _SHAPES:
        raise ValueError(
            f"unknown event type {event_type!r}; the enum has {list(EVENT_TYPES)}")

    required, optional = _SHAPES[event_type]
    optional = optional | _UNIVERSAL_OPTIONAL
    keys = set(payload)

    missing = required - keys
    if missing:
        raise ValueError(
            f"{event_type} payload is missing {sorted(missing)} "
            f"(DATA_MODEL §8.2)")

    # A rule the shape table cannot express, and the one worth stating loudly.
    #
    # `input_blocked` records that suspected real patient data was refused
    # (PRD FR-4, UX_SPEC S-10). DATA_MODEL §8.2: "never the offending text".
    # Storing the text would put the very thing we blocked into the table we
    # keep forever, which would make the block worse than useless.
    if event_type == "input_blocked":
        for key in ("text", "content", "message", "input"):
            if key in payload:
                raise ValueError(
                    "input_blocked must record only the reason, never the "
                    "blocked text — storing it would defeat the block")

    unknown = keys - required - optional
    if unknown:
        raise ValueError(
            f"{event_type} payload has unexpected {sorted(unknown)}; a key the "
            f"replayer does not read is a key that silently does nothing")
