"""
Persona leakage — did the patient volunteer what the learner did not ask?

`TECH_SPEC` §5.3 calls this "the most under-addressed risk in the project",
and the reason is Property 1 read backwards. The patient's *"only reveal when
directly asked"* rule is prompt engineering, which is soft. If the model
answers a question the learner never asked, history-coverage measures the
model's helpfulness rather than the learner's thoroughness — and every number
computed from that session is measuring the wrong thing.

**This module only decides. It never marks, writes or excludes anything.**
Deterministic Python over the same lexicon `extract_topics` uses for coverage,
so a flag can be recomputed from the event log years later and come out the
same (`ADR-0003`, `ADR-0005`).

## Only required topics count

A reply that volunteers something outside `required_topics` costs nothing:
coverage is scored over the required list, so an unrequired topic cannot
inflate it. Narrowing to the required set is therefore not a convenience, it
is the definition — the same reason `DATA_MODEL` §11.7 excludes a session
rather than discounting it.

## It is deliberately SENSITIVE — the opposite of the guard

`domain/guard.py` is deliberately conservative because a false block discards
the learner's question and teaches them the tool is broken. This is the
reverse. A false flag costs an administrator one click in the review queue; a
miss costs the validity of every measurement taken through that persona, and
nothing downstream would ever reveal it. So the rule here is broad, the
confirm/dismiss step is human, and **only `confirmed = true` excludes a
session** (`DATA_MODEL` §7.2).

That is also why the severity split exists rather than a single flag: the two
cases have genuinely different consequences, and an administrator triaging a
queue needs the difference up front.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from nidan.domain.assessment.topics import extract_topics
from nidan.domain.events import Event

Severity = Literal["low", "high"]


@dataclass(frozen=True)
class Leak:
    """
    One reply that revealed a required topic its question did not ask about.

    `topics` is sorted so that two runs over the same log produce the same
    `leaked_topics` array — a flag is evidence, and evidence whose field order
    moves between runs cannot be diffed against a recomputation.
    """

    topics: tuple[str, ...]
    severity: Severity


def topics_asked(events: Sequence[Event]) -> set[str]:
    """
    Every topic any question in the log has already asked about.

    Read from the questions themselves rather than from `patient_reply`'s
    stored `matched_topics`, so that a lexicon change moves the detector and
    the coverage score together instead of leaving the flag frozen against a
    lexicon nobody uses any more.
    """
    asked: set[str] = set()
    for event in events:
        if event.type != "question":
            continue
        text = event.payload.get("text")
        if isinstance(text, str):
            asked.update(extract_topics(text))
    return asked


def detect(
    *,
    reply: str,
    question: str,
    required_topics: Iterable[str],
    asked_before: Iterable[str] = (),
) -> Leak | None:
    """
    Whether this reply leaked, and how badly. `None` when it did not.

    `asked_before` is every topic the learner's EARLIER questions covered — it
    decides severity only, never whether there is a leak at all. `DATA_MODEL`
    §7.2's rule is per-turn: revealed, and not asked for *here*.

    * **`high`** — a required topic the learner has not asked about anywhere in
      the session. Coverage credits them for something they never did, so the
      session's numbers are wrong.
    * **`low`** — they had already asked about it in an earlier turn, so
      coverage had credited it regardless and the patient merely repeated
      itself. Worth seeing, not worth discarding a session for.
    """
    required = set(required_topics)
    if not required:
        return None

    asked_now = set(extract_topics(question))
    leaked = {t for t in extract_topics(reply) if t in required} - asked_now
    if not leaked:
        return None

    never_asked = leaked - set(asked_before)
    return Leak(
        topics=tuple(sorted(leaked)),
        severity="high" if never_asked else "low",
    )
