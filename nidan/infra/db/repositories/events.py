"""
The append-only event log (BUILD_PLAN T-013, ADR-0003).

Two operations and no others. `session_events` carries the
`session_events_append_only` trigger (migration 010), which refuses every
UPDATE and DELETE at the database — so "append-only" is not a description of
how this module happens to be written, it is a property nothing in the
application can violate.

**On `seq` and the retry.** `DATA_MODEL` §6.2 makes `UNIQUE (session_id, seq)`
the concurrency control:

> Two simultaneous requests computing the same next sequence number will
> collide, and one fails cleanly rather than silently interleaving. The
> application retries with a fresh sequence.

The trap is what a collision does to the transaction. In PostgreSQL a unique
violation aborts **the whole transaction**, not just the statement: every
subsequent command fails with *"current transaction is aborted"*. A naive
`try / except / retry` therefore turns one collision into a dead scope, and it
looks correct in every single-threaded test.

So the INSERT runs inside a SAVEPOINT (`begin_nested`). A violation rolls back
to the savepoint, the surrounding transaction survives, and the retry computes
a fresh `max(seq) + 1`. Retrying the whole scope would work too, but would also
redo whatever else the caller had already done in that unit of work.

The alternative -- `pg_advisory_xact_lock` per session, which removes the race
entirely -- was rejected: BUILD_PLAN specifies the retry, and a lock adds a
failure mode (one stuck transaction blocks every append for that session) that
a retry does not have.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from nidan.domain.events import Event, validate_payload
from nidan.infra.db.repositories.base import Repository

# How many collisions to absorb before giving up.
#
# Five was not enough, and the way it failed is the interesting part: with ten
# threads appending at once, nine landed and one starved. Every loser of a
# collision recomputes `max(seq) + 1` and retries *immediately*, so the
# contenders stay in lockstep and keep colliding as a group — the unluckiest
# thread loses repeatedly through no growing improbability of its own.
#
# The backoff below is what breaks the lockstep; the higher ceiling is slack
# on top of it. Real usage never approaches this — one learner clicks one
# button at a time — but a limit that fails a stress test is a limit that will
# fail a burst in production, at the moment of most traffic and least attention.
MAX_APPEND_ATTEMPTS = 8

# Randomised backoff between attempts. Randomised, not fixed: a fixed delay
# reschedules every loser at the same instant and reproduces the lockstep it
# was meant to fix.
_BACKOFF_MIN_S = 0.002
_BACKOFF_MAX_S = 0.012


class EventRepository(Repository):
    """
    Events for sessions the actor owns.

    Ownership is enforced by RLS (`own_session_events`, migration 016), so the
    queries below carry no `user_id` clause -- adding one would make the tests
    that prove the policy fires pass whether or not it does.
    """

    # Appended inside the EXISTS that guards every write. Empty here because
    # RLS already restricts which `sessions` rows this role can see; the
    # anonymous subclass, which runs with RLS bypassed, supplies a real one.
    _OWNERSHIP = ""

    def _ownership_params(self) -> dict[str, Any]:
        return {}

    def all_for(self, session_id: UUID) -> list[Event]:
        """Every event for a session, in sequence order."""
        rows = self._conn.execute(sa.text(f"""
            SELECT e.seq, e.type, e.payload, e.created_at
            FROM session_events e
            WHERE e.session_id = :sid
              AND EXISTS (SELECT 1 FROM sessions s
                          WHERE s.id = :sid {self._OWNERSHIP})
            ORDER BY e.seq
        """), {"sid": session_id, **self._ownership_params()}).mappings().all()
        return [Event(seq=r["seq"], type=r["type"], payload=r["payload"],
                      created_at=r["created_at"]) for r in rows]

    def append(self, session_id: UUID, event_type: str,
               payload: Mapping[str, Any]) -> Event:
        """
        Append one event. Returns it, including the `seq` it was given.

        Raises `PermissionError` if the session is not the actor's -- the
        INSERT then matches no row rather than writing into someone else's
        consultation.
        """
        validate_payload(event_type, payload)

        params = {
            "sid": session_id,
            "type": event_type,
            # json.dumps rather than passing the dict: psycopg adapts a Python
            # dict to a composite type, not to jsonb.
            "payload": json.dumps(payload),
            **self._ownership_params(),
        }

        last_error: IntegrityError | None = None
        for attempt in range(MAX_APPEND_ATTEMPTS):
            try:
                # The savepoint. Without it a collision poisons the whole
                # transaction and the retry below cannot run at all.
                with self._conn.begin_nested():
                    row = self._conn.execute(sa.text(f"""
                        INSERT INTO session_events (session_id, seq, type, payload)
                        SELECT :sid,
                               COALESCE((SELECT max(seq) FROM session_events
                                         WHERE session_id = :sid), 0) + 1,
                               CAST(:type AS event_type),
                               CAST(:payload AS jsonb)
                        WHERE EXISTS (SELECT 1 FROM sessions s
                                      WHERE s.id = :sid {self._OWNERSHIP})
                        RETURNING seq, type, payload, created_at
                    """), params).mappings().first()
            except IntegrityError as e:
                # Another request took this seq. Wait a random moment so the
                # losers of this collision do not all retry together, then
                # recompute and try again.
                last_error = e
                time.sleep(random.uniform(_BACKOFF_MIN_S, _BACKOFF_MAX_S)
                           * (attempt + 1))
                continue

            if row is None:
                raise PermissionError(
                    f"session {session_id} is not this actor's, or does not "
                    f"exist; no event was appended")
            return Event(seq=row["seq"], type=row["type"],
                         payload=row["payload"], created_at=row["created_at"])

        raise RuntimeError(
            f"could not append a {event_type} event after "
            f"{MAX_APPEND_ATTEMPTS} sequence collisions"
        ) from last_error

    def count_for(self, session_id: UUID) -> int:
        """Event count, for callers that need it without replaying."""
        return self._conn.execute(sa.text(f"""
            SELECT count(*) FROM session_events e
            WHERE e.session_id = :sid
              AND EXISTS (SELECT 1 FROM sessions s
                          WHERE s.id = :sid {self._OWNERSHIP})
        """), {"sid": session_id, **self._ownership_params()}).scalar_one()


    def count_of_type(self, session_id: UUID, event_type: str) -> int:
        """
        How many events of one type this session holds.

        `API_CONTRACT` §2.9's per-session cap is 40 **questions**, not 40
        events — a learner who examined eight systems and ordered six tests
        has not used up a third of their questions. Counting the type is the
        difference between a cap and a penalty for being thorough.
        """
        return self._conn.execute(sa.text(f"""
            SELECT count(*) FROM session_events e
            WHERE e.session_id = :sid
              AND e.type = CAST(:type AS event_type)
              AND EXISTS (SELECT 1 FROM sessions s
                          WHERE s.id = :sid {self._OWNERSHIP})
        """), {"sid": session_id, "type": event_type,
               **self._ownership_params()}).scalar_one()

    def questions_since(self, since: datetime) -> int:
        """
        The actor's questions across ALL their sessions since `since`.

        `API_CONTRACT` §2.9's second limit — 60 questions per hour per user —
        and the reason it is per user rather than per session: the per-session
        cap of 40 is a pedagogical limit, while this one protects the LLM bill
        and the provider's rate limit, which do not care which consultation a
        question belonged to.

        No `WHERE user_id`. The join to `sessions` is filtered by migration
        016's `own_sessions` policy, so this counts the actor's questions and
        a mistake here returns too few rather than someone else's (`ADR-0016`).

        **Backfilled events are included deliberately**, unlike in timing
        analysis (`DATA_MODEL` §9.3). Their timestamps are synthetic but they
        are three months old, so they fall outside any window this is asked
        about; excluding them would be a filter that never fires and that a
        reader would have to stop and verify.
        """
        return self._conn.execute(sa.text("""
            SELECT count(*)
            FROM session_events e
            JOIN sessions s ON s.id = e.session_id
            WHERE e.type = 'question'
              AND e.created_at >= :since
        """), {"since": since}).scalar_one()


def events_are_contiguous(events: Sequence[Event]) -> bool:
    """
    Whether a log runs 1..n with no gaps or duplicates.

    Used by the concurrency test, and worth having in one place: a gap means an
    append was lost, a duplicate means the unique index is not doing its job,
    and either one invalidates every result derived from the log.
    """
    return [e.seq for e in events] == list(range(1, len(events) + 1))
