"""
The actor and the engine, without a database (BUILD_PLAN T-012).

Everything else about T-012 is tested against real PostgreSQL in `tests/db/`,
and rightly so -- RLS is not a property you can check anywhere else. But those
tests skip when Docker is unavailable, which is a normal state on a laptop and
a possible one in CI. The guards below would then be untested on exactly the
runs where nobody noticed.

These need no container because none of them gets as far as a connection.
"""

from __future__ import annotations

import dataclasses
import uuid

import pytest

from nidan.infra.db import engine as engine_mod
from nidan.infra.db.actor import (
    ALLOWED_ROLES,
    AdminUser,
    AnonymousVisitor,
    AuthenticatedUser,
    ServiceActor,
)
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.base import assume


def test_each_actor_maps_to_its_role() -> None:
    assert AuthenticatedUser(uuid.uuid4()).db_role == "nidan_app"
    assert AdminUser(uuid.uuid4()).db_role == "nidan_admin"
    assert AnonymousVisitor("v1").db_role == "nidan_service"
    assert ServiceActor("the nightly session expiry sweep").db_role == "nidan_service"
    assert ALLOWED_ROLES == {"nidan_app", "nidan_service", "nidan_admin"}


def test_an_admin_is_an_authenticated_user() -> None:
    """
    The subclassing is load-bearing, not tidiness.

    `base.assume()` sets `request.jwt.claim.sub` for an `AuthenticatedUser`, and
    `Repository._user_id()` returns one for the same test. Both are asking "is
    there a person behind this transaction", and `audit_log.actor_id` is the
    answer. An `AdminUser` that failed this check would write audit rows with no
    actor, which is the thing `UX_SPEC` §12 exists to prevent.
    """
    admin = AdminUser(uuid.uuid4())
    assert isinstance(admin, AuthenticatedUser)
    assert admin.user_id is not None


def test_a_role_cannot_be_chosen_per_instance() -> None:
    """
    `db_role` is a ClassVar, so it is not a constructor argument.

    It used to be annotated `Final`, which dataclasses treat as an ordinary
    field with a default — `AuthenticatedUser(uid, "postgres")` was accepted and
    built an actor claiming a superuser role. `assume()`'s ALLOWED_ROLES check
    still refused it at the SET ROLE, so nothing was reachable; but the guard
    reads as "the role comes from the type", and until now it did not.
    """
    with pytest.raises(TypeError):
        AuthenticatedUser(uuid.uuid4(), "postgres")     # type: ignore[call-arg]
    assert "db_role" not in {f.name for f in dataclasses.fields(AuthenticatedUser)}


def test_a_user_id_must_be_a_uuid() -> None:
    """
    A string is accepted by psycopg and compared as text against a uuid column,
    which errors at the database rather than where the mistake was made.
    """
    with pytest.raises(TypeError, match="must be a UUID"):
        AuthenticatedUser("3f7c…")                      # type: ignore[arg-type]


def test_an_empty_anonymous_id_is_refused() -> None:
    """
    It would filter `anonymous_id = ''`: no rows today, every badly-inserted
    row tomorrow, visible to every visitor at once.
    """
    for bad in ("", "  ", "\t"):
        with pytest.raises(ValueError, match="non-empty"):
            AnonymousVisitor(bad)


def test_a_service_actor_must_say_why() -> None:
    """
    It is switching RLS off. The reason is never read by the database; it
    exists so that every bypass in the codebase is greppable and explains
    itself, and so that the constructor is not one anybody reaches for casually.
    """
    with pytest.raises(ValueError, match="turning RLS off"):
        ServiceActor("jobs")
    assert ServiceActor("recomputing results after a threshold change").reason


def test_actors_are_frozen() -> None:
    """A mutable actor could be changed after the scope applied it."""
    actor = AuthenticatedUser(uuid.uuid4())
    with pytest.raises(dataclasses.FrozenInstanceError):
        actor.user_id = uuid.uuid4()                    # type: ignore[misc]


def test_an_anonymous_visitor_cannot_open_the_general_repositories() -> None:
    """Checked before any connection is opened, which is why this needs no database."""
    with pytest.raises(PermissionError, match="anonymous_scope"):
        with repo_scope(AnonymousVisitor("v1")):
            pass


def test_assume_refuses_an_unrecognised_role() -> None:
    """
    `SET ROLE` takes no bind parameter, so the role name is interpolated. This
    check is what keeps that from being an injection point, and it can only be
    reached by inventing a fourth actor -- which is exactly when someone should
    be made to think about it.
    """
    class Rogue:
        db_role = "postgres; DROP TABLE sessions"

    with pytest.raises(ValueError, match="unknown role"):
        assume(None, Rogue())                           # type: ignore[arg-type]


def test_a_missing_database_url_says_what_to_do(monkeypatch) -> None:
    from nidan.config import settings
    monkeypatch.setattr(settings, "DATABASE_URL", "")
    engine_mod.dispose_engine()
    with pytest.raises(RuntimeError, match="docker compose up -d db"):
        engine_mod.get_engine()


def test_the_bare_postgres_scheme_is_normalised(monkeypatch) -> None:
    """
    docker-compose and Supabase both hand out `postgresql://`, which SQLAlchemy
    resolves to psycopg2 -- not a dependency here. Failing on the driver name
    would be a confusing first experience of a correctly configured stack.
    """
    from nidan.config import settings
    monkeypatch.setattr(
        settings, "DATABASE_URL", "postgresql://u:p@db:5432/nidan")
    assert engine_mod._url() == "postgresql+psycopg://u:p@db:5432/nidan"

    monkeypatch.setattr(
        settings, "DATABASE_URL", "postgresql+psycopg://u:p@db:5432/nidan")
    assert engine_mod._url() == "postgresql+psycopg://u:p@db:5432/nidan"
