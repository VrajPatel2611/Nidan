"""
The repository layer (BUILD_PLAN T-012).

Two entry points, and no third:

    from nidan.infra.db.repositories import repo_scope, anonymous_scope

    with repo_scope(AuthenticatedUser(user_id)) as db:
        case = db.cases.by_slug("chest-pain-gerd")
        session = db.sessions.create(case["id"], confidence_pre=3)

    with anonymous_scope(cookie_value) as db:
        session = db.sessions.active()

Both open a transaction, apply the actor to it (`base.assume`), commit on a
clean exit and roll back on an exception. Neither can be opened without an
actor, and there is no other way to reach a connection: `engine.py` is private
to this package and `tests/test_db_access.py` fails the build if anything
outside it imports the engine or writes SQL.
"""

from nidan.infra.db.actor import (
    Actor,
    AdminUser,
    AnonymousVisitor,
    AuthenticatedUser,
    ServiceActor,
)
from nidan.infra.db.repositories.anonymous import anonymous_scope
from nidan.infra.db.repositories.base import Repositories, Repository, repo_scope

__all__ = [
    "Actor", "AuthenticatedUser", "AdminUser", "AnonymousVisitor",
    "ServiceActor",
    "repo_scope", "anonymous_scope", "Repositories", "Repository",
]
