"""
Case selection and the monthly allowance (BUILD_PLAN T-017).

`DATA_MODEL` §11.1 and §11.2. The decisions live in `domain/selection.py`;
these are the queries that feed them.

As everywhere else in this layer, the queries carry **no owner clause**. RLS
does it: `own_case_history` and `own_sessions` (migrations 016 and 021) scope
both to the actor, and adding a `WHERE user_id = ...` by hand would make the
tests that prove the policies fire pass whether or not they do.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.domain.selection import better_verdict
from nidan.infra.db.repositories.base import Repository


class SelectionRepository(Repository):
    """What the learner may be given, and how much of the month they have used."""

    def candidates(self) -> Sequence[Mapping[str, Any]]:
        """
        Every published case, with when this learner last attempted it.

        `DISTINCT ON (cv.case_id) ... ORDER BY cv.version DESC` takes the
        newest published version of each case. A case may be republished, and
        both versions stay published so sessions already referencing the old
        one keep resolving (`DATA_MODEL` §5.2) — but a learner starting today
        should get the current one.

        `last_attempt` is NULL for a case they have never seen, which is what
        `choose_case` splits on.
        """
        return self._conn.execute(sa.text("""
            SELECT DISTINCT ON (cv.case_id)
                   cv.id AS case_version_id, cv.case_id, c.slug, cv.title,
                   h.last_attempt
            FROM case_versions cv
            JOIN cases c ON c.id = cv.case_id
            LEFT JOIN user_case_history h ON h.case_id = cv.case_id
            WHERE cv.status = 'published' AND cv.retired_at IS NULL
            ORDER BY cv.case_id, cv.version DESC
        """)).mappings().all()

    def sessions_started_since(self, since: datetime) -> int:
        """
        How many sessions this learner has started since a moment.

        **Every started session counts, whatever its status.** `PRD` FR-3's
        edge cases are explicit that abandoning one spends it — otherwise a
        free user could start, abandon and restart without limit, and the cap
        would mean nothing.
        """
        return self._conn.execute(sa.text(
            "SELECT count(*) FROM sessions WHERE started_at >= :since"),
            {"since": since}).scalar_one()

    def record_attempt(self, case_id: UUID, verdict: str) -> None:
        """
        Note that this learner has attempted a case, and how it went.

        `user_case_history` has had no writer until now — the table was created
        in T-010 and nothing populated it, which made "a case the user has not
        completed" unanswerable and criterion 1 unsatisfiable.

        `best_verdict` keeps the best attempt, ranked by
        `domain.selection.VERDICT_ORDER` and never by string comparison:
        alphabetically 'anchored' precedes 'correct', so a `GREATEST` here
        would silently record a learner's worst attempt as their best.
        """
        user_id = self._user_id()
        existing = self._conn.execute(sa.text(
            "SELECT best_verdict FROM user_case_history "
            "WHERE user_id = :uid AND case_id = :cid"),
            {"uid": user_id, "cid": case_id}).scalar()

        self._conn.execute(sa.text("""
            INSERT INTO user_case_history
                (user_id, case_id, times_attempted, first_attempt,
                 last_attempt, best_verdict)
            VALUES (:uid, :cid, 1, now(), now(), :verdict)
            ON CONFLICT (user_id, case_id) DO UPDATE SET
                times_attempted = user_case_history.times_attempted + 1,
                last_attempt = now(),
                best_verdict = :best
        """), {"uid": user_id, "cid": case_id, "verdict": verdict,
               "best": better_verdict(existing, verdict)})

    def case_id_for_version(self, case_version_id: UUID) -> UUID | None:
        """The case a session's pinned version belongs to."""
        return self._conn.execute(sa.text(
            "SELECT case_id FROM case_versions WHERE id = :id"),
            {"id": case_version_id}).scalar()
