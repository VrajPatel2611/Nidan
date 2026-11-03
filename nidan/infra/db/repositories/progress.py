"""
Progress over a learner's own history (`API_CONTRACT` §7 · `UX_SPEC` S-16).

**Computed on read, not from `user_progress`.** That table exists, has an RLS
policy, and nothing has ever written to it — `DATA_MODEL` §11.5 describes the
query that would rebuild it. It stays empty for now, deliberately: a
denormalised cache with no invalidation is a drift surface, and at a dozen
completed sessions per learner these aggregates are a single indexed scan.
When there is a measured reason to cache them, §11.5 is the query and
`user_progress` is the table; adding it before then would be inventing a
consistency problem.

`ADR-0003` points the same way — derived state should be reproducible from the
log, and a figure recomputed on every read cannot disagree with the rows it
came from.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository

# `UX_SPEC` S-16: the progress screen needs three sessions before it says
# anything. Two points make a line and a line is not a trend, and a learner
# shown a "declining" arrow after two consultations would be reading noise.
MIN_SESSIONS_FOR_TRENDS = 3


class ProgressRepository(Repository):
    """
    Every query here is scoped by migration 016's `own_progress` and
    `own_sessions` policies rather than by a `WHERE user_id`, so a forgotten
    clause returns an empty history instead of somebody else's (`ADR-0016`).
    """

    def summary(self) -> Mapping[str, Any]:
        """
        Counts and rates, following `DATA_MODEL` §11.5's shape.

        `rn` windows the learner's completed sessions newest-first so "last
        10" and "previous 10" are one pass. The flag rates are **rates, not
        scores** (`DATA_MODEL` §8.3): the question a trend answers is "how
        often did this happen", and averaging a score would let one extreme
        session move a line that is supposed to describe a habit.
        """
        return self._conn.execute(sa.text("""
            WITH completed AS (
                SELECT r.coverage_pct,
                       r.anchoring_detected,
                       r.premature_closure_detected,
                       r.confirmation_bias_detected,
                       row_number() OVER (ORDER BY s.ended_at DESC) AS rn
                FROM sessions s
                JOIN session_results r ON r.session_id = s.id
                WHERE s.status = 'completed'
            )
            SELECT
                count(*)                                               AS sessions_completed,
                avg(coverage_pct)      FILTER (WHERE rn <= 10)         AS mean_coverage_last10,
                avg(anchoring_detected::int)         FILTER (WHERE rn <= 10)            AS anchoring_last10,
                avg(anchoring_detected::int)         FILTER (WHERE rn BETWEEN 11 AND 20) AS anchoring_prev10,
                avg(premature_closure_detected::int) FILTER (WHERE rn <= 10)            AS premature_closure_last10,
                avg(premature_closure_detected::int) FILTER (WHERE rn BETWEEN 11 AND 20) AS premature_closure_prev10,
                avg(confirmation_bias_detected::int) FILTER (WHERE rn <= 10)            AS confirmation_bias_last10,
                avg(confirmation_bias_detected::int) FILTER (WHERE rn BETWEEN 11 AND 20) AS confirmation_bias_prev10
            FROM completed
        """)).mappings().one()

    def coverage_series(self, limit: int = 50) -> Sequence[Mapping[str, Any]]:
        """
        Coverage per completed session, oldest first, for the sparkline.

        Oldest first because it is plotted left to right in time; the limit
        keeps a long history from making one response enormous, and takes the
        most RECENT `limit` before reversing — a trend screen that silently
        showed a learner their first fifty sessions and none of the last fifty
        would be describing a stranger.
        """
        return self._conn.execute(sa.text("""
            SELECT * FROM (
                SELECT s.sequence_index AS session_index,
                       r.coverage_pct,
                       s.ended_at
                FROM sessions s
                JOIN session_results r ON r.session_id = s.id
                WHERE s.status = 'completed'
                ORDER BY s.ended_at DESC
                LIMIT :limit
            ) recent
            ORDER BY ended_at ASC
        """), {"limit": limit}).mappings().all()

    def verdict_distribution(self) -> Mapping[str, int]:
        """
        How the learner's conclusions turned out.

        All four keys are returned even at zero, by the caller: a client that
        has to handle a missing key renders differently for a learner who has
        never been wrong, which is the one learner you least want a layout bug
        for.
        """
        rows = self._conn.execute(sa.text("""
            SELECT r.diagnosis_verdict AS verdict, count(*) AS n
            FROM sessions s
            JOIN session_results r ON r.session_id = s.id
            WHERE s.status = 'completed'
            GROUP BY r.diagnosis_verdict
        """)).mappings().all()
        return {row["verdict"]: row["n"] for row in rows}

    def streaks(self, timezone_name: str) -> Mapping[str, int]:
        """
        Consecutive days with a completed consultation, in the learner's own
        timezone.

        **The timezone is the learner's, not UTC**, and that is not a detail:
        a session finished at 01:00 in Kolkata is 19:30 the previous day in
        UTC, so a UTC streak would break for someone who studies late and
        never for someone who studies early. `profiles.timezone` exists for
        this.

        Computed by grouping distinct local dates and finding runs — the gap
        between a date and its row number is constant within a run, which is
        the standard trick and avoids a recursive walk.
        """
        return self._conn.execute(sa.text("""
            WITH days AS (
                SELECT DISTINCT (s.ended_at AT TIME ZONE :tz)::date AS day
                FROM sessions s
                WHERE s.status = 'completed' AND s.ended_at IS NOT NULL
            ),
            runs AS (
                SELECT day,
                       day - (row_number() OVER (ORDER BY day))::int AS grp
                FROM days
            ),
            lengths AS (
                SELECT grp, count(*) AS len, max(day) AS last_day
                FROM runs GROUP BY grp
            )
            SELECT
                COALESCE(max(len), 0) AS longest_streak_days,
                COALESCE(max(len) FILTER (
                    WHERE last_day >= (now() AT TIME ZONE :tz)::date - 1
                ), 0) AS current_streak_days
            FROM lengths
        """), {"tz": timezone_name}).mappings().one()
