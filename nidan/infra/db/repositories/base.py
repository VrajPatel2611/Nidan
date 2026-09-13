"""
Turning an actor into a transaction (BUILD_PLAN T-012, criterion 1).

Two statements run before any repository method gets a chance to do anything,
and between them they are the entire tenant-isolation mechanism:

    SET LOCAL ROLE nidan_app;
    SELECT set_config('request.jwt.claim.sub', '<user id>', true);

**Why `SET LOCAL ROLE` and not simply a dedicated login user.** Postgres skips
RLS for superusers and for the table owner, and Supabase's direct connection
string authenticates as `postgres`, a superuser. Assuming a role per transaction
demotes that connection for the duration, so the policies apply even when the
credentials in `DATABASE_URL` would otherwise be exempt. It also means one pool
serves both roles instead of two.

**Why `SET LOCAL` and `set_config(..., true)` rather than plain `SET`.** Both
forms are legal and only one is survivable. Plain `SET` persists for the life of
the *connection*, and a pooled connection is handed to whichever request asks
next -- so user A's identity would be inherited by user B, and the bug would
appear as one learner seeing another's consultation under load and never in
development. The `LOCAL` forms are unwound when the transaction ends.
`tests/db/test_repository_scope.py` borrows a connection as one user, returns it
to the pool and takes it again as another; it fails against the plain form.

**Why the claim is a bind parameter.** Its value comes from a JWT. Interpolating
it would be SQL injection through the authentication path -- the one input an
attacker most directly influences.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from nidan.infra.db.actor import (
    ALLOWED_ROLES,
    Actor,
    AnonymousVisitor,
    AuthenticatedUser,
)
from nidan.infra.db.engine import get_engine


class Repository:
    """
    Base for every repository. Holds a transaction and the actor that opened it.

    Constructing one requires both. There is no default actor, no `None`
    fallback and no class-level connection -- a repository that could be built
    without an actor is one that can be used without one.
    """

    def __init__(self, conn: Connection, actor: Actor) -> None:
        if actor is None:                       # pragma: no cover - type-guarded
            raise ValueError("a repository cannot be opened without an actor")
        self._conn = conn
        self._actor = actor

    @property
    def actor(self) -> Actor:
        return self._actor

    def _user_id(self) -> UUID:
        """
        The owning user, for writes that must stamp one.

        Raises rather than returning None for a service actor: a row written
        with a NULL owner by a background job is invisible to RLS forever
        afterwards, and nothing later can work out who it belonged to.
        """
        if isinstance(self._actor, AuthenticatedUser):
            return self._actor.user_id
        raise PermissionError(
            f"{type(self._actor).__name__} has no user_id; this write needs an "
            f"owner. If it is genuinely ownerless, say so in the query.")


def assume(conn: Connection, actor: Actor) -> None:
    """
    Apply the actor to an open transaction. Public only so tests can prove it.
    """
    role = actor.db_role
    # SET ROLE accepts no bind parameter, so the name is interpolated. This
    # check -- against a frozenset of two literals defined in actor.py -- is
    # what keeps that from being an injection point. It can only fail if
    # someone invents a fourth actor, which is exactly when it should.
    if role not in ALLOWED_ROLES:
        raise ValueError(f"refusing to SET ROLE to an unknown role: {role!r}")
    conn.exec_driver_sql(f"SET LOCAL ROLE {role}")

    # Empty string, not NULL: the auth.uid() stub in migration 001 is
    # NULLIF(current_setting(...), '')::uuid, written for exactly this.
    uid = str(actor.user_id) if isinstance(actor, AuthenticatedUser) else ""
    conn.execute(
        sa.text("SELECT set_config('request.jwt.claim.sub', :uid, true)"),
        {"uid": uid},
    )


@contextmanager
def _transaction(actor: Actor) -> Iterator[Connection]:
    """One transaction, with the actor applied before anything else runs."""
    with get_engine().connect() as conn:
        with conn.begin():
            assume(conn, actor)
            yield conn


class Repositories:
    """
    Every repository, sharing one transaction.

    A container rather than free functions so that a unit of work is a unit of
    work: writing a session and its events in one scope either both commit or
    neither does.
    """

    def __init__(self, conn: Connection, actor: Actor) -> None:
        from nidan.infra.db.repositories.cases import CaseRepository
        from nidan.infra.db.repositories.events import EventRepository
        from nidan.infra.db.repositories.feedback import FeedbackRepository
        from nidan.infra.db.repositories.profiles import ProfileRepository
        from nidan.infra.db.repositories.results import (
            EngineVersionRepository,
            ResultRepository,
        )
        from nidan.infra.db.repositories.sessions import SessionRepository

        self.conn = conn
        self.actor = actor
        self.profiles = ProfileRepository(conn, actor)
        self.sessions = SessionRepository(conn, actor)
        self.events = EventRepository(conn, actor)
        self.feedback = FeedbackRepository(conn, actor)
        self.results = ResultRepository(conn, actor)
        self.engines = EngineVersionRepository(conn, actor)
        self.cases = CaseRepository(conn, actor)


@contextmanager
def repo_scope(actor: Actor) -> Iterator[Repositories]:
    """
    The only way into the database.

    Commits on a clean exit, rolls back on an exception.

    Rejects `AnonymousVisitor` deliberately. The trial path runs with RLS
    bypassed, so its protection is an `anonymous_id` filter that no query may
    omit -- a guarantee that survives only while the code carrying it is four
    methods long. Letting a visitor open the general repositories would put
    that filter's correctness into every query anyone writes from here on.
    Use `anonymous_scope` (`repositories/anonymous.py`).
    """
    if isinstance(actor, AnonymousVisitor):
        raise PermissionError(
            "an AnonymousVisitor cannot open the general repositories -- RLS "
            "does not cover the trial path. Use anonymous_scope()."
        )
    with _transaction(actor) as conn:
        yield Repositories(conn, actor)
