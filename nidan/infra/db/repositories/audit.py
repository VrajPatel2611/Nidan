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
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository

# Actions are dotted `entity.verb` strings — 'case_version.published',
# 'review.recorded', 'profile.viewed'. Free text rather than an enum because
# the set grows with every admin screen, and a migration per new button would
# be a tax on exactly the work this table is meant to encourage.
#
# Kept sortable and greppable by convention instead: lower case, one dot, verb
# in the past tense.


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
