"""
`leakage_flags` — the persona-leakage queue (`DATA_MODEL` §7.2, T-040).

The rule that decides a leak lives in `domain/leakage.py`. This file only
stores its answer, lists what nobody has looked at yet, and records the
administrator's verdict.

**Recorded on a best-effort basis, like `llm_calls`.** `record()` runs inside
a scope the caller already opened for a question and its reply. A consultation
must not fail because leak accounting did: if the row is lost the queue is
short one item, whereas a propagating exception costs a learner a reply they
have already been given. `TECH_SPEC` §5.3's defence is a queue plus adversarial
CI, and the CI half does not depend on this row existing.

**Only `confirmed = true` excludes a session from research.** `reviewed` alone
does not, and neither does `severity = 'high'` — §11.7's query filters on
`confirmed`, because a detector that could discard sessions on its own would be
the LLM marking by proxy (`ADR-0005`). The default is that a flagged session
still counts.

**The review is an UPDATE, which is why this task needed migration 034.**
`nidan_admin` had `GRANT SELECT ON ALL TABLES` and INSERT/UPDATE on
`cases`/`case_versions` only, so `review()` failed with a permission error
against a table the console was built to triage.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError

from nidan.infra.db.actor import AdminUser
from nidan.infra.db.repositories.base import Repository
from nidan.infra.db.repositories.leakage_columns import COLUMNS

logger = logging.getLogger(__name__)


class LeakageRepository(Repository):
    """
    Flags written during a consultation, read and resolved by an administrator.

    `_OWNERSHIP` is empty here and set by the trial subclass, exactly as
    `EventRepository` does it: the INSERT is an `INSERT ... SELECT` guarded by
    an EXISTS over `sessions`, so a session that is not the actor's writes no
    row instead of writing into someone else's consultation.
    """

    _OWNERSHIP = ""

    def _ownership_params(self) -> dict[str, Any]:
        return {}

    # ── written during a consultation ────────────────────────────────

    def record(self, session_id: UUID, *, event_seq: int,
               topics: Sequence[str], severity: str) -> bool:
        """
        Store one flag. True if a row was written.

        False rather than an exception when the session is not the actor's:
        the caller is mid-consultation and there is nothing useful it could do
        with the failure. `tests/db/test_leakage.py` asserts the refusal.
        """
        if severity not in ("low", "high"):
            # Migration 015's CHECK, refused in Python for the same reason
            # `llm_calls` mirrors its own: a CheckViolation would abort a
            # transaction opened for the question and the reply.
            raise ValueError(
                f"severity must be 'low' or 'high', not {severity!r}")
        if not topics:
            raise ValueError("a leakage flag with no topics records nothing")

        # The savepoint is what makes "best effort" true rather than merely
        # intended. Without it a failing INSERT poisons the whole transaction
        # in Postgres, so the question and the reply appended moments earlier
        # would roll back too and the learner would lose a reply they have
        # already read. With it, only this statement is discarded.
        try:
            with self._conn.begin_nested():
                result = self._conn.execute(sa.text(f"""
                    INSERT INTO leakage_flags (session_id, event_seq,
                                               leaked_topics, severity)
                    SELECT :sid, :seq, :topics, :severity
                     WHERE EXISTS (SELECT 1 FROM sessions s
                                   WHERE s.id = :sid {self._OWNERSHIP})
                """), {"sid": session_id, "seq": event_seq,
                       "topics": list(topics), "severity": severity,
                       **self._ownership_params()})
        except SQLAlchemyError:
            # Logged, not swallowed in silence: a queue that is quietly short
            # of items looks like a persona that has stopped leaking, which is
            # the one wrong conclusion this task exists to prevent. No session
            # id in the line -- the message goes to logs that outlive an
            # erasure.
            logger.warning(
                "leakage flag not recorded (severity=%s, topics=%d)",
                severity, len(topics), exc_info=True)
            return False
        return result.rowcount == 1

    # ── read by the admin console ────────────────────────────────────

    def unreviewed_count(self) -> dict[str, int]:
        """
        How many flags nobody has looked at, by severity.

        Returns both keys always, zero included — A-01's "needs attention"
        panel renders the number it is given, and a missing key there reads as
        "nothing to do" rather than as a bug.
        """
        rows = self._conn.execute(sa.text("""
            SELECT severity, count(*) AS n
              FROM leakage_flags
             WHERE reviewed = false
          GROUP BY severity
        """)).mappings().all()
        counts = {"low": 0, "high": 0}
        for row in rows:
            counts[row["severity"]] = row["n"]
        return counts

    def queue(self, *, limit: int = 50,
              include_reviewed: bool = False) -> list[Mapping[str, Any]]:
        """
        The queue, highest severity first and oldest first within it.

        Oldest first within a severity on purpose: the point of the queue is
        that a persona which started leaking gets noticed, and newest-first
        buries the first occurrence under its own repetitions.
        """
        where = "" if include_reviewed else "WHERE f.reviewed = false"
        return list(self._conn.execute(sa.text(f"""
            SELECT {COLUMNS}
              FROM leakage_flags f
              JOIN sessions s       ON s.id = f.session_id
              JOIN case_versions cv ON cv.id = s.case_version_id
              JOIN cases c          ON c.id = cv.case_id
              {where}
          ORDER BY (f.severity = 'high') DESC, f.created_at
             LIMIT :limit
        """), {"limit": limit}).mappings().all())

    def get(self, flag_id: UUID) -> Mapping[str, Any] | None:
        return self._conn.execute(sa.text(f"""
            SELECT {COLUMNS}
              FROM leakage_flags f
              JOIN sessions s       ON s.id = f.session_id
              JOIN case_versions cv ON cv.id = s.case_version_id
              JOIN cases c          ON c.id = cv.case_id
             WHERE f.id = :id
        """), {"id": flag_id}).mappings().first()

    def reply_text(self, session_id: UUID, event_seq: int) -> str | None:
        """
        The reply the flag points at, so the queue can show what was said.

        Read live from `session_events` rather than copied into the flag. The
        erasure redacts `payload->'text'` to `"[redacted]"` (migration 033),
        and a copy here would survive it — a learner's consultation preserved
        in a table the erasure never looks at, which is exactly the mistake
        `feedback_texts.lines` already cost us once.
        """
        return self._conn.execute(sa.text("""
            SELECT payload->>'text'
              FROM session_events
             WHERE session_id = :sid AND seq = :seq AND type = 'patient_reply'
        """), {"sid": session_id, "seq": event_seq}).scalar()

    # ── resolved by an administrator ─────────────────────────────────

    def review(self, flag_id: UUID, *, confirmed: bool) -> bool:
        """
        Confirm or dismiss. True if this call was the one that decided it.

        `AdminUser` only: `TECH_SPEC` §5.3 says "flag to an admin queue", and
        confirming excludes a session from the research export, which is a
        decision about the dataset rather than about clinical content. The
        reviewer role deliberately cannot — it reads drafts and writes
        `clinical_reviews`, and nothing else (migration 024).

        `AND reviewed = false` makes it idempotent in the way that matters:
        two administrators opening the same queue cannot overwrite each
        other's verdict, and the second gets False rather than silently
        winning.
        """
        if not isinstance(self._actor, AdminUser):
            raise PermissionError(
                f"only an AdminUser may review a leakage flag, not "
                f"{type(self._actor).__name__}")
        result = self._conn.execute(sa.text("""
            UPDATE leakage_flags
               SET reviewed = true,
                   confirmed = :confirmed,
                   reviewed_by = :by,
                   reviewed_at = now()
             WHERE id = :id AND reviewed = false
        """), {"id": flag_id, "confirmed": confirmed,
               "by": self._actor.user_id})
        return result.rowcount == 1
