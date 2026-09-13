"""
The anonymous trial path (BUILD_PLAN T-012, criterion 3).

**This is the one place in Nidan where Row-Level Security is off.** A trial
visitor has no account, so `auth.uid()` is NULL, so `own_sessions`
(`user_id = auth.uid()`) evaluates NULL and denies the visitor their own
session. `DATA_MODEL` §10.1 accepts that and names the compensating control:

> served through a service-role connection with an explicit `anonymous_id`
> filter in the query, and that code path is short, isolated, and separately
> tested.

All three words are load-bearing, and this module is what makes them true:

* **short** -- four methods, and none of them writes its own WHERE clause. The
  filter lives in `_scoped()`, so forgetting it means writing a query that does
  not compile rather than one that quietly returns every trial session on the
  platform. `tests/test_db_access.py` also asserts that every SQL literal in
  this file mentions `anonymous_id`.
* **isolated** -- `anonymous_scope` yields only these four methods and the
  read-only case repository. It cannot reach profiles, results, subscriptions
  or another visitor's anything, because no object here exposes them.
* **separately tested** -- `tests/db/test_anonymous_scope.py`.

`repo_scope` refuses an `AnonymousVisitor` for the same reason: were the general
repositories reachable from here, the correctness of that filter would become a
property of every query anyone writes from now on, rather than of one file.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.actor import AnonymousVisitor
from nidan.infra.db.repositories.base import Repository, _transaction
from nidan.infra.db.repositories.events import EventRepository
from nidan.infra.db.repositories.feedback import FeedbackRepository
from nidan.infra.db.repositories.results import (
    EngineVersionRepository,
    ResultRepository,
)

_COLUMNS = """
    id, anonymous_id, case_version_id, sequence_index, status, confidence_pre,
    started_at, ended_at, last_activity_at, diagnosis_submitted_at
"""


def _visitor_id(actor: object) -> str:
    """
    The visitor's id, or a refusal.

    Not an `assert`: python -O strips those, and this is the guard that keeps a
    non-visitor actor away from queries whose only tenant filter is the value
    it returns. Shared by both repositories in this module so they cannot
    disagree about whose events belong to whose session.
    """
    if not isinstance(actor, AnonymousVisitor):
        raise TypeError(
            f"the trial repositories need an AnonymousVisitor, not "
            f"{type(actor).__name__}")
    return actor.anonymous_id


class AnonymousSessionRepository(Repository):
    """Trial sessions, and nothing else."""

    def _aid(self) -> str:
        return _visitor_id(self._actor)

    def _scoped(self, tail: str) -> sa.TextClause:
        """
        Every statement in this class is built here, so every statement carries
        the filter. The one thing that must not be forgotten is therefore not
        something anyone has to remember.
        """
        return sa.text(
            f"SELECT {_COLUMNS} FROM sessions WHERE anonymous_id = :anonymous_id {tail}")

    def get(self, session_id: UUID) -> Mapping[str, Any] | None:
        return self._conn.execute(
            self._scoped("AND id = :id"),
            {"anonymous_id": self._aid(), "id": session_id},
        ).mappings().first()

    def active(self) -> Mapping[str, Any] | None:
        return self._conn.execute(
            self._scoped("AND status = 'active' ORDER BY started_at DESC LIMIT 1"),
            {"anonymous_id": self._aid()},
        ).mappings().first()

    def create(self, case_version_id: UUID,
               confidence_pre: int | None = None) -> Mapping[str, Any]:
        """
        Start the trial session.

        `user_id` is not passed and cannot be: `owner_is_exclusive` requires
        exactly one owner, and a trial row with both set would be claimable
        twice. `sequence_index` is 1 because a browser gets one trial (PRD
        FR-2); enforcing that limit is T-015's job, not this row's.
        """
        row = self._conn.execute(sa.text(f"""
            INSERT INTO sessions (anonymous_id, case_version_id, sequence_index,
                                  confidence_pre)
            VALUES (:anonymous_id, :case_version_id, 1, :confidence_pre)
            RETURNING {_COLUMNS}
        """), {"anonymous_id": self._aid(), "case_version_id": case_version_id,
               "confidence_pre": confidence_pre}).mappings().first()
        if row is None:                          # pragma: no cover
            raise RuntimeError("trial session insert returned no row")
        return row

    def touch(self, session_id: UUID) -> None:
        self._conn.execute(sa.text(
            "UPDATE sessions SET last_activity_at = now() "
            "WHERE anonymous_id = :anonymous_id AND id = :id"),
            {"anonymous_id": self._aid(), "id": session_id})

    def complete(self, session_id: UUID) -> bool:
        """As SessionRepository.complete, with the trial filter that RLS cannot give."""
        result = self._conn.execute(sa.text("""
            UPDATE sessions
               SET status = 'completed',
                   ended_at = now(),
                   diagnosis_submitted_at = now(),
                   last_activity_at = now()
             WHERE anonymous_id = :anonymous_id AND id = :id
               AND diagnosis_submitted_at IS NULL
        """), {"anonymous_id": self._aid(), "id": session_id})
        return result.rowcount == 1


class AnonymousEventRepository(EventRepository):
    """
    The trial visitor's event log.

    The only difference from `EventRepository` is that it cannot lean on RLS.
    `own_session_events` resolves through `sessions.user_id = auth.uid()`,
    which is NULL for a trial, and this scope runs as a bypassing role anyway
    -- so without the predicate below, one visitor could append to and read
    another's consultation by guessing a session id.
    """

    _OWNERSHIP = "AND s.anonymous_id = :anonymous_id"

    def _ownership_params(self) -> dict[str, object]:
        return {"anonymous_id": _visitor_id(self._actor)}


class AnonymousFeedbackRepository(FeedbackRepository):
    """Trial feedback. As with events, RLS cannot help here — see above."""

    _OWNERSHIP = "AND s.anonymous_id = :anonymous_id"

    def _ownership_params(self) -> dict[str, object]:
        return {"anonymous_id": _visitor_id(self._actor)}


class AnonymousResultRepository(ResultRepository):
    """Trial results. As with events and feedback, RLS cannot help here."""

    _OWNERSHIP = "AND s.anonymous_id = :anonymous_id"

    def _ownership_params(self) -> dict[str, object]:
        return {"anonymous_id": _visitor_id(self._actor)}


class AnonymousRepositories:
    """Exactly what a trial visitor may touch: their sessions, and published cases."""

    def __init__(self, conn: sa.engine.Connection, actor: AnonymousVisitor) -> None:
        from nidan.infra.db.repositories.cases import CaseRepository

        self.conn = conn
        self.actor = actor
        self.sessions = AnonymousSessionRepository(conn, actor)
        self.events = AnonymousEventRepository(conn, actor)
        self.feedback = AnonymousFeedbackRepository(conn, actor)
        self.results = AnonymousResultRepository(conn, actor)
        # Read-only, and not scoped to a visitor: an engine version
        # is shared configuration, not anyone's data.
        self.engines = EngineVersionRepository(conn, actor)
        # Safe under a bypassing role because every query in CaseRepository
        # filters `status = 'published'` itself rather than trusting the policy.
        self.cases = CaseRepository(conn, actor)


@contextmanager
def anonymous_scope(anonymous_id: str) -> Iterator[AnonymousRepositories]:
    """The trial path's only entry point."""
    actor = AnonymousVisitor(anonymous_id=anonymous_id)
    with _transaction(actor) as conn:
        yield AnonymousRepositories(conn, actor)
