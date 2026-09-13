"""
Case selection and allowance arithmetic (BUILD_PLAN T-017).

Pure functions, so no database. The two things worth testing hard are the ones
that fail quietly: the month boundary in a learner's own timezone, which is
wrong on exactly one day a month, and the verdict ordering, which a string
comparison gets backwards without complaint.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from nidan.domain.selection import (
    VERDICT_ORDER,
    allowance_for,
    better_verdict,
    choose_case,
    month_start,
    next_month_start,
)

UTC = UTC


def _case(slug: str, last_attempt=None) -> dict:
    return {"case_version_id": uuid4(), "case_id": uuid4(), "slug": slug,
            "title": slug.title(), "last_attempt": last_attempt}


# ── choosing a case ──────────────────────────────────────────────────

def test_an_unseen_case_is_preferred():
    seen = _case("seen", datetime(2026, 1, 1, tzinfo=UTC))
    unseen = _case("unseen")
    for _ in range(20):
        assert choose_case([seen, unseen]).slug == "unseen"


def test_the_choice_among_unseen_cases_is_random():
    """
    FR-3.1 says at random, and it matters: a deterministic order means every
    learner meets the cases in the same sequence, so answers circulate in that
    order too.
    """
    cases = [_case(f"case-{i}") for i in range(5)]
    chosen = {choose_case(cases, rng=random.Random(seed)).slug
              for seed in range(40)}
    assert len(chosen) > 1, "selection is not varying across seeds"


def test_a_pinned_rng_makes_the_choice_reproducible():
    cases = [_case(f"case-{i}") for i in range(5)]
    first = choose_case(cases, rng=random.Random(7)).slug
    assert choose_case(cases, rng=random.Random(7)).slug == first


def test_when_everything_is_seen_the_least_recent_is_offered_as_a_repeat():
    """
    FR-3.2. The repeat flag is not decoration: a learner who is not told they
    have seen the case before will read their own memory of the answer as
    clinical reasoning.
    """
    old = _case("oldest", datetime(2026, 1, 1, tzinfo=UTC))
    recent = _case("recent", datetime(2026, 6, 1, tzinfo=UTC))

    selection = choose_case([recent, old])
    assert selection.slug == "oldest"
    assert selection.is_repeat is True


def test_an_unseen_case_is_never_marked_a_repeat():
    assert choose_case([_case("fresh")]).is_repeat is False


def test_no_candidates_yields_nothing():
    """
    FR-3's edge case: no published cases means a friendly error, not a crash.
    Expected until T-023 publishes the five seeded cases, which are drafts
    pending clinical review.
    """
    assert choose_case([]) is None


# ── the month boundary ───────────────────────────────────────────────

def test_the_month_starts_in_the_learners_timezone():
    """
    The trap. `now() AT TIME ZONE tz` in SQL returns a NAIVE timestamp, which
    then compares wrongly against a TIMESTAMPTZ column — the allowance resets
    at the wrong instant, visible on exactly one day a month.

    For a learner in Kolkata (UTC+5:30), September begins at 18:30 UTC on
    31 August. A UTC-based boundary would give them five and a half extra
    hours of August's allowance, and take the same from September.
    """
    now = datetime(2026, 9, 13, 2, 0, tzinfo=UTC)

    assert month_start(now, "UTC") == datetime(2026, 9, 1, tzinfo=UTC)
    assert month_start(now, "Asia/Kolkata") == datetime(2026, 8, 31, 18, 30, tzinfo=UTC)


def test_a_learner_west_of_utc_gets_a_later_boundary():
    now = datetime(2026, 9, 13, 2, 0, tzinfo=UTC)
    assert month_start(now, "America/New_York") > month_start(now, "UTC")


def test_the_boundary_is_stable_just_either_side_of_it():
    """
    A session started one second before the learner's month begins belongs to
    the previous month, and one second after belongs to this one. Getting this
    backwards gives somebody a free case or takes one away.
    """
    boundary = month_start(datetime(2026, 9, 13, tzinfo=UTC), "Asia/Kolkata")
    assert month_start(boundary + timedelta(seconds=1), "Asia/Kolkata") == boundary
    assert month_start(boundary - timedelta(seconds=1), "Asia/Kolkata") < boundary


def test_december_rolls_over_into_the_next_year():
    """The off-by-one that only appears once a year."""
    assert next_month_start(datetime(2026, 12, 5, tzinfo=UTC), "UTC") == \
        datetime(2027, 1, 1, tzinfo=UTC)


def test_an_unknown_timezone_falls_back_to_utc_rather_than_failing():
    """
    A bad value in `profiles.timezone` must not stop someone starting a case.
    They would be blocked by a field they may never have set, and the worst
    consequence of the fallback is a reset at the wrong hour.
    """
    assert month_start(datetime(2026, 9, 13, tzinfo=UTC), "Mars/Olympus") == \
        datetime(2026, 9, 1, tzinfo=UTC)
    assert month_start(datetime(2026, 9, 13, tzinfo=UTC), "") == \
        datetime(2026, 9, 1, tzinfo=UTC)


# ── the allowance ────────────────────────────────────────────────────

@pytest.mark.parametrize("used,remaining,exhausted", [
    (0, 3, False), (2, 1, False), (3, 0, True), (5, 0, True),
])
def test_a_free_learner_is_capped(used, remaining, exhausted):
    a = allowance_for("free", used, now=datetime(2026, 9, 13, tzinfo=UTC),
                      timezone_name="UTC", free_limit=3)
    assert a.remaining == remaining
    assert a.exhausted is exhausted


def test_remaining_never_goes_negative():
    """A negative count would render as "-2 remaining" on the dashboard."""
    a = allowance_for("free", 99, now=datetime(2026, 9, 13, tzinfo=UTC),
                      timezone_name="UTC", free_limit=3)
    assert a.remaining == 0


def test_pro_is_unlimited_and_says_so_with_none():
    """
    None rather than a large number, so no client renders
    "999,997 remaining" and no comparison accidentally exhausts it.
    """
    a = allowance_for("pro", 500, now=datetime(2026, 9, 13, tzinfo=UTC),
                      timezone_name="UTC", free_limit=3)
    assert a.limit is None
    assert a.remaining is None
    assert a.exhausted is False


def test_the_allowance_reports_when_it_resets():
    """A block with no date is a dead end; a client cannot compute one."""
    a = allowance_for("free", 3, now=datetime(2026, 9, 13, tzinfo=UTC),
                      timezone_name="UTC", free_limit=3)
    assert a.resets_at == datetime(2026, 10, 1, tzinfo=UTC)


# ── verdict ranking ──────────────────────────────────────────────────

def test_the_best_verdict_is_ranked_not_compared_as_text():
    """
    Alphabetically 'anchored' < 'correct', so a GREATEST() or a max() on the
    strings records a learner's worst attempt as their best — silently, and
    only for the learners who improved.
    """
    assert better_verdict("correct", "anchored") == "correct"
    assert better_verdict("anchored", "correct") == "correct"
    assert better_verdict("other", "partial") == "partial"
    assert better_verdict("partial", "other") == "partial"


def test_the_first_attempt_sets_the_verdict():
    assert better_verdict(None, "anchored") == "anchored"


def test_an_unrecognised_verdict_does_not_overwrite_a_known_one():
    assert better_verdict("correct", "nonsense") == "correct"
    assert better_verdict("nonsense", "partial") == "partial"


def test_the_ranking_covers_every_verdict_the_schema_allows():
    """
    `session_results.diagnosis_verdict` is CHECK-constrained to these four. One
    missing from the ordering would be treated as unrecognised and silently
    ignored when ranking.
    """
    assert set(VERDICT_ORDER) == {"correct", "partial", "anchored", "other"}
