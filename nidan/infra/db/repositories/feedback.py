"""
Stored feedback prose (BUILD_PLAN T-013).

**Only the prose is stored.** Every flag, score, verdict and scorecard on the
feedback screen is recomputed from the event log when the page is rendered —
they are deterministic functions of what the learner did, so storing them would
be storing a cache that can silently disagree with the log it came from.

The lines here are the one part that cannot be recomputed: a language model
wrote them, at a temperature, on a day. Replaying the same events would produce
different words. That asymmetry is exactly `ADR-0005` — the model writes prose
and never marks — turned into a storage decision, and it is why `/feedback`
can be re-opened a year later and still show the same reasoning next to the
same words.

`generator` records whether the model or the deterministic fallback produced
them (`infra/feedback.py`). The fallback fires on a timeout or a rate limit,
silently and by design, so this column is the only durable evidence of how
often the model was actually unavailable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository


class FeedbackRepository(Repository):
    """
    Feedback for sessions the actor owns.

    `own_feedback_texts` (migration 021) inherits ownership through the parent
    session, so these queries carry no owner clause of their own. That policy
    was missing until T-013 — the table had RLS enabled with no policy, which
    denies everything rather than allowing everything.
    """

    _OWNERSHIP = ""

    def _ownership_params(self) -> dict[str, Any]:
        return {}

    def save(self, session_id: UUID, lines: Sequence[str], *,
             generator: str, prompt_version: str | None = None) -> UUID:
        """Store one set of feedback lines. Returns its id."""
        if generator not in ("llm", "rule_fallback"):
            # The CHECK constraint would catch this, mid-request, as an
            # IntegrityError naming a constraint rather than the mistake.
            raise ValueError(
                f"generator must be 'llm' or 'rule_fallback', not {generator!r}")
        if not lines:
            raise ValueError("refusing to store empty feedback")

        row = self._conn.execute(sa.text(f"""
            INSERT INTO feedback_texts (session_id, lines, generator, prompt_version)
            SELECT :sid, :lines, :generator, :prompt_version
            WHERE EXISTS (SELECT 1 FROM sessions s
                          WHERE s.id = :sid {self._OWNERSHIP})
            RETURNING id
        """), {"sid": session_id, "lines": list(lines), "generator": generator,
               "prompt_version": prompt_version,
               **self._ownership_params()}).mappings().first()
        if row is None:
            raise PermissionError(
                f"session {session_id} is not this actor's; no feedback stored")
        return row["id"]

    def rate(self, session_id: UUID, *, was_helpful: bool) -> bool:
        """
        Record whether the prose helped. False if there is nothing to rate.

        Applied to the NEWEST row, matching `latest()`: a retry that got as
        far as generating prose leaves a second row, and the learner rated
        what they read. `rated_at` is stamped here rather than accepted, for
        the same reason `consent_at` is.

        Re-rating overwrites. `UX_SPEC` UX-3 is one control with two states,
        so a learner changing their mind is a correction and not a second
        data point.
        """
        return self._conn.execute(sa.text("""
            UPDATE feedback_texts SET was_helpful = :helpful, rated_at = now()
            WHERE id = (
                SELECT f.id FROM feedback_texts f
                WHERE f.session_id = :sid
                ORDER BY f.created_at DESC LIMIT 1
            )
        """), {"sid": session_id, "helpful": was_helpful}).rowcount > 0

    def latest(self, session_id: UUID) -> Mapping[str, Any] | None:
        """
        The most recent feedback for a session.

        Most recent rather than the only one: `/conclude` is idempotent at the
        session level (`diagnosis_submitted_at`), but a retry that got as far
        as generating prose leaves a second row, and the newest is the one the
        learner saw.
        """
        return self._conn.execute(sa.text(f"""
            SELECT f.id, f.lines, f.generator, f.prompt_version,
                   f.was_helpful, f.created_at
            FROM feedback_texts f
            WHERE f.session_id = :sid
              AND EXISTS (SELECT 1 FROM sessions s
                          WHERE s.id = :sid {self._OWNERSHIP})
            ORDER BY f.created_at DESC LIMIT 1
        """), {"sid": session_id, **self._ownership_params()}).mappings().first()
