"""
`/v1` catalogue endpoints — the universal menus (`API_CONTRACT` §5).

**The whole point of these two endpoints is what they do not say.** Every
learner sees the same 27 examinations and 91 investigations on every case, so
the menu cannot be read as a hint: a learner facing the chest-pain case still
sees Anti-GAD antibodies and an OGTT. `PRD` FR-5.1 and FR-6.1 call this the
universal panel, and §5 states the consequence in bold — the response "must
never include `category`, `is_key`, or any case-specific field".

That is contract test CT-3, and it is honoured twice: the repository's SELECT
does not name a column that could leak relevance, and the test asserts the
serialised body. Neither alone would be enough — the repository could grow a
column, and the test only sees what it provokes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from flask import jsonify

from nidan.api.v1.blueprint import bp
from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories import repo_scope

# §5: "Cacheable, `Cache-Control: public, max-age=3600`". The menus change
# only when an admin edits a master list (T-044), which is rare and never
# urgent — an hour of staleness costs a learner nothing, and these two
# responses are requested on every page load of the consultation screen.
_CACHE: dict[str, str] = {"Cache-Control": "public, max-age=3600"}

# §5 serves these to anonymous callers, and `repo_scope` needs an actor.
# `AuthenticatedUser` has no id to offer and `AnonymousVisitor` is rejected by
# `repo_scope` on purpose (`ADR-0016`) — it exists only for the one path in
# `repositories/anonymous.py`.
#
# So: a `ServiceActor`, which runs with RLS bypassed. That is defensible here
# and nowhere near as alarming as it sounds, for reasons worth stating rather
# than assuming: `examinations` and `investigations` carry **no RLS policies
# at all** (migrations 016 and 021 never gave them any) because they hold
# reference data with no owner, so there is nothing for a scope to exempt. The
# repository is read-only and four methods long, and its SELECT names four
# columns by hand.
_REASON = (
    "the universal examination and investigation menus are reference data "
    "with no owner, and API_CONTRACT §5 serves them to anonymous callers who "
    "have no auth.uid() to scope by"
)


def _menu(rows: Sequence[Mapping[str, object]]):
    """
    §5's shape, built field by field.

    Explicit rather than `dict(row)`. A `SELECT *` or a row dump is how a
    column added for the admin console — `normal_result`, or anything
    `is_key`-shaped — reaches a learner the week after it is added, and CT-3
    would only catch it if a test happened to run against a case where it
    mattered.
    """
    return jsonify({"data": [
        {
            "key": r["key"],
            "label": r["label"],
            "group": r["group_name"],
            "display_order": r["display_order"],
        }
        for r in rows
    ]}), 200, _CACHE


@bp.get("/catalog/examinations")
def catalog_examinations():
    """
    The examination menu. **No authentication** (§5: "anonymous or user").

    Open because the anonymous trial needs it before anyone has an account
    (`PRD` FR-2), and because it is the same list for everyone — there is
    nothing here to scope to a caller.
    """
    with repo_scope(ServiceActor(_REASON)) as db:
        return _menu(db.catalog.examinations())


@bp.get("/catalog/investigations")
def catalog_investigations():
    """The investigation menu. No authentication, for the same reasons."""
    with repo_scope(ServiceActor(_REASON)) as db:
        return _menu(db.catalog.investigations())
