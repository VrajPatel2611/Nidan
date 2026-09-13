"""
Claiming a trial session into an account (BUILD_PLAN T-015, `PRD` FR-2).

A visitor completes a full case with no account. When they sign up within 30
days, that consultation becomes theirs and appears in their history — the
moment `UX_SPEC` describes as *"Your case result will be saved to your new
account."*

**Why this needs a `ServiceActor`.** Neither existing scope can do it. The row
is anonymous, so `own_sessions` (`user_id = auth.uid()`) cannot see it as the
new owner; and the trial scope has no business writing a `user_id`. Claiming
therefore runs with Row-Level Security bypassed, which is exactly why it lives
in one small module with its ownership checks written out by hand.

**The two constraints that make the UPDATE harder than it looks.**

`owner_is_exclusive` (migration 009) requires exactly one owner:

    (user_id IS NOT NULL AND anonymous_id IS NULL)
 OR (user_id IS NULL AND anonymous_id IS NOT NULL)

so `user_id` must be set and `anonymous_id` cleared **in the same statement**.
Written as two updates the row is briefly invalid and the CHECK fires.

`user_sequence_unique` is a *partial* index — `WHERE user_id IS NOT NULL` — so
it does not apply to a trial session at all. It begins applying at the instant
of claiming. Trial sessions are all created with `sequence_index = 1`, so
claiming one into an account that already has a session numbered 1 would
violate it. The claim renumbers, in the same statement, and does so per row:
one `anonymous_id` can carry several sessions, and giving them all the same
number would violate the index just as surely.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories.base import Repository

# PRD FR-2.4. Long enough that someone who tried a case and came back next
# month still has it; short enough that abandoned rows do not accumulate for
# ever against an identifier nobody holds any more.
CLAIM_WINDOW_DAYS = 30


class TrialRepository(Repository):
    """
    The trial lifecycle. Service-actor only.

    Every method states its own ownership condition, because the database is
    not stating it here.
    """

    def __init__(self, conn, actor) -> None:
        super().__init__(conn, actor)
        if not isinstance(actor, ServiceActor):
            raise PermissionError(
                "claiming a trial runs with RLS bypassed and needs a "
                "ServiceActor with a stated reason")

    def sessions_for(self, anonymous_id: str) -> Sequence[Mapping[str, Any]]:
        """
        Every unclaimed session for this visitor, newest first.

        Returned regardless of the claim window, so a caller can tell "there is
        nothing here" from "there is something, but it is too old" — which are
        different answers to the user and different error codes.
        """
        if not anonymous_id or not anonymous_id.strip():
            return []
        return self._conn.execute(sa.text("""
            SELECT id, started_at, status, case_version_id,
                   started_at > now() - make_interval(days => :days) AS claimable
            FROM sessions
            WHERE anonymous_id = :aid AND user_id IS NULL
            ORDER BY started_at DESC
        """), {"aid": anonymous_id, "days": CLAIM_WINDOW_DAYS}).mappings().all()

    def has_used_trial(self, anonymous_id: str) -> bool:
        """
        Whether this browser has already started its one trial (`PRD` FR-2.5).

        Counts claimed sessions too: signing up does not earn another free
        case, so the question is "has this identifier ever started one", not
        "does it still own one".
        """
        if not anonymous_id or not anonymous_id.strip():
            return False
        return bool(self._conn.execute(sa.text(
            "SELECT 1 FROM sessions WHERE anonymous_id = :aid LIMIT 1"),
            {"aid": anonymous_id}).first())

    def claim(self, anonymous_id: str, user_id: UUID) -> list[UUID]:
        """
        Transfer this visitor's sessions to a user. Returns the ids claimed.

        One statement, for the reasons in the module docstring. An empty list
        means nothing was claimable — expired, already claimed, or never
        existed — and the caller decides which of those the user is told.

        `WHERE user_id IS NULL` makes a double-claim a no-op rather than an
        error: two concurrent signups with the same cookie is a race the second
        one should lose quietly, not a 500.
        """
        if not anonymous_id or not anonymous_id.strip():
            return []

        rows = self._conn.execute(sa.text("""
            WITH highest AS (
                -- The user's current highest session number. Computed before
                -- the UPDATE, from the pre-statement snapshot.
                SELECT COALESCE(max(sequence_index), 0) AS n
                FROM sessions WHERE user_id = :uid
            ),
            claimable AS (
                SELECT id,
                       row_number() OVER (ORDER BY started_at) AS offset_in_batch
                FROM sessions
                WHERE anonymous_id = :aid
                  AND user_id IS NULL
                  AND started_at > now() - make_interval(days => :days)
            )
            UPDATE sessions s
               SET user_id = :uid,
                   -- Both halves of owner_is_exclusive, together.
                   anonymous_id = NULL,
                   -- Renumbered per row: several trials under one identifier
                   -- must not all become sequence_index = highest + 1.
                   sequence_index = highest.n + claimable.offset_in_batch
              FROM claimable, highest
             WHERE s.id = claimable.id
            RETURNING s.id
        """), {"aid": anonymous_id, "uid": user_id,
               "days": CLAIM_WINDOW_DAYS}).scalars().all()
        return list(rows)
