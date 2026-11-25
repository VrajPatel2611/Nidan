"""
`python -m nidan.jobs lexicon`: the phrase match counts behind A-07's
dead-phrase report (T-044 criterion 4).

Migration 005 promised "a nightly job" that fills `topic_phrases.match_count`
and `last_matched_at`. It was never built, so every phrase read as never having
matched anything. This is that job.

**It recomputes from scratch each run.** It reads every learner question still
on the log, matches it in memory with the engine's own rule (a lowercase
substring, exactly as `extract_topics` does), and overwrites both counters.
That makes it idempotent and crash-safe without any bookkeeping. It also means
a question erased under `ADR-0018` stops counting on the next run, which an
incremental counter would never forget.

**Only counts leave this process.** The question text is held in memory long
enough to match it, and is never logged, stored or returned. That is the
same rule `domain/guard.py` follows for refused input.

Runs as a `ServiceActor` because it reads across every learner's sessions.
Kept separate from `run`, the account jobs, so that a failure here never makes
an export or an erasure report failure, and a stuck erasure never hides a
lexicon run.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories import repo_scope

log = logging.getLogger("nidan.jobs.lexicon")

ACTOR = ServiceActor(
    reason="the lexicon match-count job reads every learner's questions to "
           "count which phrases match; only the counts are written")


@dataclass(frozen=True)
class CountReport:
    questions: int
    phrases: int
    matched: int        # phrases with at least one match

    def summary(self) -> str:
        return (f"{self.questions} question(s) read · {self.matched} of "
                f"{self.phrases} phrase(s) matched at least once")


def tally(questions: Iterable[tuple[str, datetime, bool]],
          phrases: Iterable[tuple[str, str]],
          ) -> tuple[dict[tuple[str, str], tuple[int, datetime | None]], int]:
    """
    Pure: `{(topic, phrase): (count, last_matched_at)}`, and the question count.

    `count` includes the backfilled pilot sessions, since they are real
    questions a real learner typed. `last_matched_at` excludes them, because
    their timestamps are synthetic (`DATA_MODEL` §9.3) and recency is the one
    thing the dead-phrase report reads.
    """
    keys = list(phrases)
    counts: dict[tuple[str, str], list] = {k: [0, None] for k in keys}
    n = 0
    for text, at, backfilled in questions:
        n += 1
        lowered = text.lower()
        for key in keys:
            if key[1] in lowered:
                slot = counts[key]
                slot[0] += 1
                if not backfilled and (slot[1] is None or at > slot[1]):
                    slot[1] = at
    return {k: (c, last) for k, (c, last) in counts.items()}, n


def count_matches() -> CountReport:
    """Read, tally, store, and record that it happened, all in one transaction."""
    with repo_scope(ACTOR) as db:
        phrases = db.lexicon.phrase_list()
        result, n = tally(db.lexicon.question_texts(), phrases)
        db.lexicon.store_counts(
            (topic, phrase, c, last) for (topic, phrase), (c, last) in result.items())
        matched = sum(1 for c, _ in result.values() if c)
        db.lexicon.record_counted(
            {"questions": n, "phrases": len(phrases), "matched": matched})
    report = CountReport(questions=n, phrases=len(phrases), matched=matched)
    log.info("lexicon counts stored: %s", report.summary())
    return report
