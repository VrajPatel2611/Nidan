"""
Profiles (BUILD_PLAN T-012).

Thin on purpose. The interesting property is not in any method here -- it is
that none of them says `WHERE id = :user_id`. The `own_profile` policy from
migration 016 does that, and leaving it out of the SQL is what makes these
tests meaningful: if the policy were inert, `get()` would return the first
profile in the table and the test would say so immediately.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository


class ProfileRepository(Repository):

    def get(self) -> Mapping[str, Any] | None:
        """The actor's own profile. Deliberately unfiltered -- see the module docstring."""
        row = self._conn.execute(sa.text("""
            SELECT id, display_name, professional_role, platform_role, year_of_training,
                   country, timezone, research_pid, subscription_tier,
                   subscription_ends, onboarded_at, consent_research,
                   platform_role
            FROM profiles
        """)).mappings().first()
        return row

    def ensure(self, **fields: Any) -> Mapping[str, Any]:
        """
        Create the actor's profile if it does not exist, then return it.

        Idempotent because `POST /me` is retried by clients and replayed by
        Supabase Auth webhooks (API_CONTRACT §3, T-014). ON CONFLICT DO NOTHING
        rather than a SELECT-then-INSERT: two concurrent first requests would
        both see nothing and the second would violate the primary key.

        The id is taken from the actor, never from a caller argument. A caller
        that could name the id could create a profile for someone else -- and
        while `own_profile` would refuse the INSERT, an application should not
        be relying on the last line of defence for its first.
        """
        user_id: UUID = self._user_id()
        allowed = {"display_name", "professional_role", "year_of_training",
                   "country", "timezone", "consent_research", "consent_version"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"not a profile column: {sorted(unknown)}")

        cols = ["id", *fields]
        params: dict[str, Any] = {"id": user_id, **fields}
        placeholders = [":id", *(f":{k}" for k in fields)]

        # `consent_recorded_together` (migration 004) requires a version and a
        # timestamp whenever consent is true. The timestamp is stamped here
        # rather than accepted as an argument: it is a record of when the user
        # actually agreed, and a caller that can choose it can backdate it.
        if fields.get("consent_research"):
            if not fields.get("consent_version"):
                raise ValueError(
                    "consent_research=True needs the consent_version the user "
                    "was shown; consent to an unnamed document is not consent")
            cols.append("consent_at")
            placeholders.append("now()")
        # professional_role is an enum; psycopg sends a plain string, which
        # Postgres will not implicitly cast in a parameterised INSERT.
        if "professional_role" in fields:
            placeholders[cols.index("professional_role")] = (
                "CAST(:professional_role AS professional_role)")

        self._conn.execute(sa.text(
            f"INSERT INTO profiles ({', '.join(cols)}) "
            f"VALUES ({', '.join(placeholders)}) ON CONFLICT (id) DO NOTHING"
        ), params)

        row = self.get()
        if row is None:                          # pragma: no cover - see below
            # Reachable only if the INSERT was silently refused by RLS, which
            # would mean the actor's id and auth.uid() disagree -- a bug in the
            # scope, not in this method. Saying so beats returning None.
            raise PermissionError(
                "profile was neither found nor created; the transaction's "
                "auth.uid() does not match the actor")
        return row

    def touch_last_active(self) -> None:
        self._conn.execute(sa.text(
            "UPDATE profiles SET last_active_at = now()"))
