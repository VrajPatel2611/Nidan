"""
The audit log (BUILD_PLAN T-020, `DATA_MODEL` §7.2).

`UX_SPEC` §12 requires that **every** admin action writes an `audit_log` row.
The table is append-only by intent and carries a `forbid_mutation` trigger
(migration 015), so a record cannot be quietly revised afterwards — which is
the only property that makes an audit log worth keeping.

**One writer, not a call at every site.** A rule that depends on each handler
remembering to log is not a rule; it is a hope. Admin mutations go through
`record()`, and the decorator in `api/auth.py` makes the actor implicit so the
caller cannot attribute an action to the wrong person by passing the wrong id.

**Why this lives here and not in the admin module.** `tests/test_db_access.py`
forbids SQL anywhere outside this package — a query written elsewhere would run
with whatever role and whatever `auth.uid()` the connection happened to carry,
which is exactly what `ADR-0016` exists to prevent.

`SECURITY_SPEC` §8 on why `reason` matters: a shared admin account destroys the
log's value because `actor_id` stops identifying a person. Support access to a
learner's data must say why, in words, at the moment it happens.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories.base import Repository

# Actions are dotted `entity.verb` strings — 'case_version.published',
# 'review.recorded', 'profile.viewed'. Free text rather than an enum because
# the set grows with every admin screen, and a migration per new button would
# be a tax on exactly the work this table is meant to encourage.
#
# Kept sortable and greppable by convention instead: lower case, one dot, verb
# in the past tense.

# T-038. The account jobs worker's queue, as pairs: a request action, and the
# action that marks one of its steps finished.
#
# **This table cannot be updated** — migration 015's `forbid_mutation` trigger
# refuses UPDATE even to the owner, and `ADR-0018` kept it that way when it
# narrowed the one on `session_events`, because the record of an erasure must
# not be editable by the thing performing one. So a job cannot be *marked*
# done. It is done when a second row says so, and `pending()` is the
# difference between the two sets.
#
# That constraint turns out to be the feature: a step whose completion row
# exists is skipped, and a call that timed out after succeeding is recovered on
# the next run rather than repeated blindly (T-038 criterion 4).
REQUEST_ACTIONS: Final[frozenset[str]] = frozenset({
    "profile.export_requested",
    "profile.erased",
})

# Each request's steps. One completion row per step, so a partial run is a
# recorded state rather than a lost one -- the confirmation email can have been
# sent while the credential deletion has not, which is the normal case given
# S-20 requires that order.
STEPS: Final[dict[str, tuple[str, ...]]] = {
    "profile.export_requested": ("export.built", "export.emailed"),
    "profile.erased": ("erasure.email_sent", "erasure.billing_cancelled",
                       "erasure.credential_deleted"),
}

COMPLETION_ACTIONS: Final[frozenset[str]] = frozenset(
    step for steps in STEPS.values() for step in steps)

# A step that has failed enough times to stop retrying it. Recorded, never
# updated -- so `attempts` is a COUNT of failure rows, not a column.
FAILED_ACTION: Final[str] = "job.step_failed"
MAX_ATTEMPTS: Final[int] = 5


class AuditRepository(Repository):
    """Append-only record of what an administrator did."""

    def record(self, action: str, *, entity_type: str,
               entity_id: UUID | None = None, reason: str | None = None,
               metadata: Mapping[str, Any] | None = None,
               ip_address: str | None = None) -> None:
        """
        Write one audit row.

        The actor is taken from the scope, never from an argument. A caller
        that could name the actor could attribute an action to someone else,
        and an audit log that can be made to lie about who acted is worse than
        none — it is evidence that supports the wrong conclusion.
        """
        if not action or "." not in action:
            raise ValueError(
                f"audit action must be a dotted entity.verb string, not "
                f"{action!r} — 'case_version.published', not 'published'")
        if not entity_type:
            raise ValueError("audit rows must name the entity type they concern")

        self._conn.execute(sa.text("""
            INSERT INTO audit_log
                (actor_id, action, entity_type, entity_id, reason,
                 metadata, ip_address)
            VALUES (:actor, :action, :entity_type, :entity_id, :reason,
                    CAST(:metadata AS jsonb), CAST(:ip AS inet))
        """), {
            "actor": self._user_id(),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "reason": reason,
            "metadata": json.dumps(dict(metadata)) if metadata else None,
            # NULL rather than a placeholder when absent: an invented address
            # is a false fact in a record whose whole purpose is being true.
            "ip": ip_address or None,
        })

    def record_system_step(self, action: str, *, entity_id: UUID,
                           reason: str | None = None,
                           metadata: Mapping[str, Any] | None = None) -> None:
        """
        One row written by the account jobs worker, not by a person (T-038).

        `actor_id` is **NULL**, and that is the honest value. `record()` takes
        the actor from the scope precisely so an action cannot be attributed to
        the wrong person, and the worker is not a person: attributing
        `erasure.credential_deleted` to the user who asked would say they
        deleted their own Supabase credential, which they did not and could
        not. A NULL actor with an `entity_id` naming the profile reads as what
        happened -- the system did this, to this account.

        **Only a `ServiceActor` may call it.** Without that check this method
        is a way for any route to write an audit row with no actor, which is
        the one thing `record()`'s whole docstring is about. The worker is the
        only caller, it is the only thing that runs as a service, and a route
        that reached for this would fail immediately rather than subtly.

        No `ip_address`: there is no request, and `record()` says why an
        invented one is worse than none.
        """
        if not isinstance(self._actor, ServiceActor):
            raise PermissionError(
                f"record_system_step is for the jobs worker; "
                f"{type(self._actor).__name__} must use record(), which "
                f"attributes the action to the actor that opened the scope")
        if action not in COMPLETION_ACTIONS and action != FAILED_ACTION:
            raise ValueError(
                f"{action!r} is not a step this worker can complete. "
                f"Known: {sorted(COMPLETION_ACTIONS | {FAILED_ACTION})}")

        self._conn.execute(sa.text("""
            INSERT INTO audit_log
                (actor_id, action, entity_type, entity_id, reason, metadata)
            VALUES (NULL, :action, 'profile', :entity_id, :reason,
                    CAST(:metadata AS jsonb))
        """), {
            "action": action,
            "entity_id": entity_id,
            "reason": reason,
            "metadata": json.dumps(dict(metadata)) if metadata else None,
        })

    def pending(self, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        """
        Requests with at least one step not yet recorded as done (T-038).

        **The queue is a difference between two sets, because this table
        refuses UPDATE.** There is no `status` column to flip and no row to
        claim; a request is outstanding exactly while some step of it has no
        completion row. Three consequences worth knowing before relying on it:

        * It is **idempotent by construction**. Re-running the worker re-derives
          the same answer from the same rows, so a crash between a remote call
          and its completion row costs one retry, not a lost job (criterion 4).
        * It is **self-healing**. Add a step to `STEPS` and every past request
          becomes pending again for that step alone — which is what you want
          when the step is new, and is why the worker must treat each step as
          separately skippable rather than keying off the request.
        * It **cannot be claimed**, so two workers would both pick up the same
          job. One process is the design (`COMMANDS.md`); the per-step
          completion rows mean the damage from a double run is a duplicate
          email, not a double erasure. If that ever needs to be exact, the lock
          belongs in a separate table, not here.

        `steps_done` comes back as a list so the caller does not need a second
        query per request, and `attempts` counts recorded failures so a step
        that cannot succeed stops being retried for ever.
        """
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        # The expected step list per request action, as rows, so the
        # "is it finished" test happens in SQL. Filtering in Python after a
        # LIMIT would be subtly wrong and would get worse with time: completed
        # requests are never removed, so the oldest rows — which are the ones
        # most likely to be finished — would fill the limit and starve the new
        # ones behind them. The bug would appear as a worker that stops
        # processing anything, months in, with nothing failing.
        #
        # The action is a bind parameter; the count is interpolated. That is
        # not a shortcut — `:n0::int` silently does not bind, because
        # SQLAlchemy's `text()` parser takes the `::` cast as part of the
        # parameter name and leaves `:n0` in the SQL for Postgres to reject.
        # `len(steps)` of a module constant has no injection surface, and
        # `CAST(:n0 AS int)` would work too; this reads better and the values
        # are literally `2` and `3`.
        params: dict[str, Any] = {"limit": limit,
                                  "failed_action": FAILED_ACTION}
        clauses = []
        for i, (action, steps) in enumerate(sorted(STEPS.items())):
            params[f"a{i}"] = action
            clauses.append(f"SELECT :a{i} AS action, {len(steps)} AS step_count")
        expected_sql = " UNION ALL ".join(clauses)

        return self._conn.execute(sa.text(f"""
            WITH expected AS ({expected_sql}),
            requests AS (
                SELECT a.id, a.action, a.entity_id, a.created_at, a.metadata,
                       e.step_count
                FROM audit_log a
                JOIN expected e ON e.action = a.action
                WHERE a.entity_id IS NOT NULL
            ),
            done AS (
                SELECT entity_id, array_agg(DISTINCT action) AS actions,
                       count(DISTINCT action) AS n
                FROM audit_log
                WHERE action = ANY(:completion_actions)
                GROUP BY entity_id
            ),
            failures AS (
                SELECT entity_id, metadata->>'step' AS step, count(*) AS n
                FROM audit_log
                WHERE action = :failed_action AND metadata ? 'step'
                GROUP BY entity_id, metadata->>'step'
            )
            SELECT r.id, r.action, r.entity_id, r.created_at, r.metadata,
                   COALESCE(d.actions, ARRAY[]::text[]) AS steps_done,
                   COALESCE(
                     (SELECT jsonb_object_agg(f.step, f.n)
                      FROM failures f WHERE f.entity_id = r.entity_id),
                     '{{}}'::jsonb) AS attempts
            FROM requests r
            LEFT JOIN done d ON d.entity_id = r.entity_id
            -- The whole point: a request is outstanding while it has fewer
            -- distinct completion rows than its action has steps. DISTINCT
            -- because a step recorded twice (a double run) must not make an
            -- unfinished request look finished.
            WHERE COALESCE(d.n, 0) < r.step_count
            ORDER BY r.created_at ASC, r.id ASC
            LIMIT :limit
        """), {**params,
               "completion_actions": sorted(COMPLETION_ACTIONS)}).mappings().all()

    def for_entity(self, entity_type: str, entity_id: UUID,
                   limit: int = 50) -> Sequence[Mapping[str, Any]]:
        """
        What has been done to one thing, newest first.

        This is the query the case editor needs for "who changed this and
        when", and it uses the index migration 015 created for it.
        """
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        return self._conn.execute(sa.text("""
            SELECT id, actor_id, action, entity_type, entity_id, reason,
                   metadata, created_at
            FROM audit_log
            WHERE entity_type = :entity_type AND entity_id = :entity_id
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
        """), {"entity_type": entity_type, "entity_id": entity_id,
               "limit": limit}).mappings().all()

    def recent(self, limit: int = 50) -> Sequence[Mapping[str, Any]]:
        """The latest activity, for the admin dashboard."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        return self._conn.execute(sa.text("""
            SELECT id, actor_id, action, entity_type, entity_id, reason,
                   metadata, created_at
            FROM audit_log ORDER BY created_at DESC, id DESC LIMIT :limit
        """), {"limit": limit}).mappings().all()
