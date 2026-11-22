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


class AccountErased(Exception):
    """
    `POST /me` was called by someone whose account has been erased.

    Its own exception rather than a `ValueError`, because the two mean
    different things to the route: a `ValueError` from this module is a bad
    field and belongs in a 422 naming it, while this is a conflict with the
    account's state and maps to `account_deleted` (409).

    It exists because `ensure()` is an INSERT with `ON CONFLICT DO NOTHING`.
    Against a soft-deleted row that does nothing at all, and the caller would
    get whichever answer the following SELECT happened to give -- a 500 once
    `get()` started hiding erased profiles. An erasure that a retried sign-up
    could undo is not an erasure.
    """


class ProfileRepository(Repository):

    def get(self) -> Mapping[str, Any] | None:
        """
        The actor's own profile, unless it has been erased.

        Deliberately unfiltered by id -- see the module docstring. The one
        `WHERE` is `deleted_at IS NULL`, and it is the exception that proves
        the rule: RLS can say "yours", but it cannot say "still exists".

        **An erased account keeps a valid token until Supabase deletes the
        credential** (`ADR-0002`: we do not own `auth.users`, so that is an
        admin-API call the erasure worker makes, inside S-20's 24 hours).
        Without this filter the window between the two is an account that
        answers `GET /me` with an anonymised profile and can start a new
        consultation. Every learner route reaches the profile through this
        method, so one filter closes all of them; the 404 they get is the
        same 404 as a profile that was never created, which §2.7 prefers to
        a status that distinguishes the two.
        """
        row = self._conn.execute(sa.text("""
            SELECT id, display_name, professional_role, platform_role, year_of_training,
                   country, timezone, research_pid, subscription_tier,
                   subscription_ends, onboarded_at, consent_research,
                   platform_role
            FROM profiles
            WHERE deleted_at IS NULL
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

        # Before the INSERT, because `ON CONFLICT DO NOTHING` would make a
        # resurrection attempt indistinguishable from an ordinary retry.
        # `get()` hides erased profiles, so this is the only place left that
        # can see one.
        erased = self._conn.execute(sa.text(
            "SELECT 1 FROM profiles WHERE deleted_at IS NOT NULL"
        )).first()
        if erased is not None:
            raise AccountErased(
                "this account has been deleted and cannot be recreated")

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

    def update(self, **fields: Any) -> Mapping[str, Any] | None:
        """
        Change the actor's own profile (`API_CONTRACT` §4 `PATCH /v1/me`).

        Separate from `ensure`, which is an INSERT with `ON CONFLICT DO
        NOTHING` and would silently do nothing here — exactly the failure a
        PATCH must not have, because the response would echo the old values
        and look like success.

        Returns None when there is no profile, so the route can answer 404
        rather than create one by surprise. `PATCH` on something absent is not
        a request to bring it into existence; §4 gives `POST /me` that job.

        Empty `fields` is a no-op that still returns the row. A PATCH with
        nothing in it is odd but not wrong, and 422 for it would mean a client
        has to special-case "the user changed nothing".
        """
        user_id: UUID = self._user_id()
        allowed = {"display_name", "professional_role", "year_of_training",
                   "country", "timezone", "consent_research", "consent_version",
                   "onboarded"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"not a profile column: {sorted(unknown)}")

        # `onboarded` is a flag, not a column (T-033). Answering or skipping
        # S-07 both end onboarding (`PRD` FR-2.7: skipping never blocks), so
        # the server stamps `onboarded_at` -- once, keeping the first time --
        # for the same reason it stamps `consent_at`: a caller who could choose
        # the time could rewrite when someone joined. There is no un-onboarding.
        onboarded = fields.pop("onboarded", None)
        if onboarded is not None and onboarded is not True:
            raise ValueError("onboarded can only be true")

        if not fields and not onboarded:
            return self.get()

        assignments = []
        params: dict[str, Any] = {"id": user_id}
        if onboarded:
            assignments.append("onboarded_at = COALESCE(onboarded_at, now())")
        for key, value in fields.items():
            # professional_role is an enum; psycopg sends a plain string and
            # Postgres will not implicitly cast one in a parameterised UPDATE.
            placeholder = (f"CAST(:{key} AS professional_role)"
                           if key == "professional_role" else f":{key}")
            assignments.append(f"{key} = {placeholder}")
            params[key] = value

        # Same rule as `ensure`, for the same reason: migration 004's
        # `consent_recorded_together` requires a version and a timestamp
        # whenever consent is true, and the timestamp records when the user
        # actually agreed. A caller that can choose it can backdate it.
        if fields.get("consent_research"):
            if not fields.get("consent_version"):
                raise ValueError(
                    "consent_research=True needs the consent_version the user "
                    "was shown; consent to an unnamed document is not consent")
            assignments.append("consent_at = now()")

        # `AND deleted_at IS NULL`: without it a PATCH would write to an
        # erased row and then return 404 because `get()` hides it -- so the
        # caller sees a refusal while the display name they sent is back in
        # the table. rowcount then being 0 is what makes the 404 true.
        result = self._conn.execute(sa.text(
            f"UPDATE profiles SET {', '.join(assignments)} "  # noqa: S608
            f"WHERE id = :id AND deleted_at IS NULL"
        ), params)
        if result.rowcount == 0:
            return None
        return self.get()

    def touch_last_active(self) -> None:
        """Activity on an erased profile is not activity -- see `update()`."""
        self._conn.execute(sa.text(
            "UPDATE profiles SET last_active_at = now() "
            "WHERE deleted_at IS NULL"))
