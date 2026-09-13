"""
Which case, and whether they may start it (BUILD_PLAN T-017).

Two rules that together decide what happens when someone clicks "Start a case".

**The system chooses the case; the learner does not browse.** `PRD` FR-3 gives
three reasons, and the third is the commercial one:

> free choice lets users avoid uncomfortable specialties, repeat familiar cases,
> and — once answers circulate — pick the one they have been told about.

**Free users get a fixed number of cases a month**, and abandoning one still
spends it (`PRD` FR-3 edge cases). That is deliberate and it is the rule most
likely to produce a support email, so the message that reports it says so.

This module is pure: it decides given a list of candidates and a history, and
knows nothing about SQL, requests or the clock. The queries live in
`infra/db/repositories/selection.py`, and `now` is passed in.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Ordered worst to best. `user_case_history.best_verdict` keeps the best attempt,
# and "best" needs a real ordering: a naive comparison on the text sorts
# alphabetically, which puts 'anchored' above 'correct' and quietly records a
# learner's worst attempt as their best.
VERDICT_ORDER: tuple[str, ...] = ("other", "anchored", "partial", "correct")


@dataclass(frozen=True)
class Selection:
    """A chosen case, and whether the learner has seen it before."""

    case_version_id: UUID
    case_id: UUID
    slug: str
    title: str
    is_repeat: bool


@dataclass(frozen=True)
class Allowance:
    """
    How much of this month a learner has left.

    `resets_at` is part of the answer, not a nicety: `PRD` FR-10 blocks at case
    start, and a block with no date is a dead end. `API_CONTRACT`'s `Error`
    schema carries it in `details`.
    """

    limit: int | None            # None means unlimited (Pro)
    used: int
    resets_at: datetime

    @property
    def remaining(self) -> int | None:
        if self.limit is None:
            return None
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.limit is not None and self.used >= self.limit


def choose_case(candidates: Sequence[Mapping[str, Any]],
                *, rng: random.Random | None = None) -> Selection | None:
    """
    Pick a case from the candidates a repository found.

    `DATA_MODEL` §11.1 selects unseen published cases at random and falls back
    to the least-recently attempted. The repository supplies both lists; the
    choice between them is here, where it can be tested without a database.

    `rng` is injectable so a test can pin the choice. Randomness is the one
    thing in this module that is not a pure function of its inputs, so it is
    the one thing passed in.
    """
    unseen = [c for c in candidates if c.get("last_attempt") is None]
    if unseen:
        chooser = rng or random
        return _to_selection(chooser.choice(list(unseen)), is_repeat=False)

    if not candidates:
        return None

    # Every case attempted: offer the least-recently seen, marked as a repeat.
    # FR-3.2 requires the marking — a learner who is not told it is a repeat
    # will read their own memory of the answer as clinical reasoning.
    oldest = min(candidates, key=lambda c: c["last_attempt"])
    return _to_selection(oldest, is_repeat=True)


def month_start(now: datetime, timezone_name: str) -> datetime:
    """
    The first instant of the learner's current month, as an aware UTC datetime.

    **The timezone is the learner's**, from `profiles.timezone`, and getting
    this wrong is subtle: the month boundary moves by the UTC offset, so a
    learner in Asia/Kolkata would have their allowance reset five and a half
    hours late — visible on exactly one day a month, which is the hardest kind
    of bug to catch.

    Computed as a real zone-aware datetime rather than with Postgres's
    `AT TIME ZONE`, which returns a naive timestamp that then compares wrongly
    against a `TIMESTAMPTZ` column.
    """
    zone = _zone(timezone_name)
    local = now.astimezone(zone)
    return local.replace(day=1, hour=0, minute=0, second=0,
                         microsecond=0).astimezone(now.tzinfo or zone)


def next_month_start(now: datetime, timezone_name: str) -> datetime:
    """When the allowance resets — the first instant of the learner's next month."""
    zone = _zone(timezone_name)
    local = now.astimezone(zone)
    year, month = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
    first = local.replace(year=year, month=month, day=1, hour=0, minute=0,
                          second=0, microsecond=0)
    return first.astimezone(now.tzinfo or zone)


def allowance_for(tier: str, used: int, *, now: datetime,
                  timezone_name: str, free_limit: int) -> Allowance:
    """
    What this learner has left.

    Pro is unlimited — expressed as `None` rather than a large number, so a
    caller cannot accidentally render "999,997 remaining".
    """
    limit = None if tier == "pro" else free_limit
    return Allowance(limit=limit, used=used,
                     resets_at=next_month_start(now, timezone_name))


def better_verdict(current: str | None, candidate: str) -> str:
    """
    The better of two verdicts, for `user_case_history.best_verdict`.

    Ranked by `VERDICT_ORDER`, never by string comparison. Alphabetically
    'anchored' precedes 'correct', so the obvious implementation records a
    learner's worst attempt as their best and does it silently.
    """
    if current is None or current not in VERDICT_ORDER:
        return candidate
    if candidate not in VERDICT_ORDER:
        return current
    return max(current, candidate, key=VERDICT_ORDER.index)


def _to_selection(row: Mapping[str, Any], *, is_repeat: bool) -> Selection:
    return Selection(
        case_version_id=row["case_version_id"],
        case_id=row["case_id"],
        slug=row["slug"],
        title=row["title"],
        is_repeat=is_repeat,
    )


def _zone(timezone_name: str) -> ZoneInfo:
    """
    The learner's zone, falling back to UTC.

    A bad value in `profiles.timezone` must not stop someone starting a case.
    They would be blocked by a field they may never have set, and the worst
    consequence of the fallback is a reset at the wrong hour.
    """
    try:
        return ZoneInfo(timezone_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")
