"""
Audit log repository (BUILD_PLAN T-020).

Provides append-only recording and querying of administrative and audit events.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository


class AuditRepository(Repository):

    def record(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID | str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> Mapping[str, Any]:
        """
        Record an action in the append-only audit_log table.

        The actor_id is taken from the scope actor (self._user_id() if authenticated).
        `action` is formatted as 'entity.verb' (e.g. 'case_version.published').
        """
        actor_id: UUID | None = None
        try:
            actor_id = self._user_id()
        except PermissionError:
            actor_id = None

        meta_json = json.dumps(metadata) if metadata is not None else None
        entity_id_str = str(entity_id) if entity_id is not None else None

        row = self._conn.execute(
            sa.text("""
                INSERT INTO audit_log (actor_id, action, entity_type, entity_id, reason, metadata, ip_address)
                VALUES (:actor_id, :action, :entity_type, :entity_id, :reason, CAST(:metadata AS JSONB), :ip_address)
                RETURNING id, actor_id, action, entity_type, entity_id, reason, metadata, ip_address, created_at
            """),
            {
                "actor_id": actor_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id_str,
                "reason": reason,
                "metadata": meta_json,
                "ip_address": ip_address,
            },
        ).mappings().one()

        return row

    def for_entity(self, entity_type: str, entity_id: UUID | str) -> list[Mapping[str, Any]]:
        """Fetch audit trail for a specific entity, newest first."""
        rows = self._conn.execute(
            sa.text("""
                SELECT id, actor_id, action, entity_type, entity_id, reason, metadata, ip_address, created_at
                FROM audit_log
                WHERE entity_type = :entity_type AND entity_id = :entity_id
                ORDER BY created_at DESC
            """),
            {
                "entity_type": entity_type,
                "entity_id": str(entity_id),
            },
        ).mappings().all()

        return list(rows)

    def recent(self, limit: int = 50) -> list[Mapping[str, Any]]:
        """Fetch recent audit log records, newest first."""
        rows = self._conn.execute(
            sa.text("""
                SELECT id, actor_id, action, entity_type, entity_id, reason, metadata, ip_address, created_at
                FROM audit_log
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

        return list(rows)
