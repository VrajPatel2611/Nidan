"""
The anonymous trial (BUILD_PLAN T-015, `PRD` FR-2).

A visitor completes one full case — including feedback — before creating an
account. `PRD` FR-2 gives the reason plainly: *requiring registration before
the user has experienced the product is the largest avoidable drop-off in a
consumer funnel*, and FR-2.2 requires the trial be a complete case, not a
truncated one. The product's argument is that feedback on reasoning differs
from a score, and that argument cannot be made behind a signup wall.

**The cookie is a bearer credential.** There is no `auth.uid()` on this path,
so whoever holds the `anonymous_id` can read that consultation. Its protection
is that it is unguessable (uuid4, 122 bits) and unreadable by JavaScript. Hence
`httpOnly`, and hence `Secure` everywhere except local http development, where
the browser would otherwise drop it silently and the trial would appear broken
for reasons no error message explains.

**One trial per browser is enforced here and not in the prototype's
server-rendered routes.** Those are a development surface with a deletion date
(T-030), and the limit protects revenue rather than data — it is cookie-based,
so clearing cookies defeats it, which `PRD` FR-2.5 accepts by saying "per
browser" rather than "per person". Enforcing it in the prototype would cost a
cookie-clear per case while authoring content and buy nothing.
"""

from __future__ import annotations

import uuid

from flask import jsonify, make_response, request

from nidan.config import settings
from nidan.domain.content.cases import CASE_SLUGS, get_case
from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.anonymous import anonymous_scope
from nidan.infra.db.repositories.trial import TrialRepository

COOKIE_NAME = "anonymous_id"
COOKIE_MAX_AGE_S = 30 * 24 * 60 * 60      # the claim window, PRD FR-2.4


def visitor_id() -> str | None:
    """The trial identifier this request carries, if any."""
    value = request.cookies.get(COOKIE_NAME, "").strip()
    return value or None


def new_visitor_id() -> str:
    """
    A fresh trial identifier.

    uuid4, not a counter or a hash of anything about the visitor: it is the
    only thing standing between one trial session and another, and it must be
    unguessable and carry no information about who holds it.
    """
    return str(uuid.uuid4())


def set_trial_cookie(response, value: str):
    """Attach the trial cookie. `PRD` FR-2.3 requires httpOnly."""
    response.set_cookie(
        COOKIE_NAME, value,
        max_age=COOKIE_MAX_AGE_S,
        httponly=True,
        # Off for local http, or the browser drops it and the trial looks
        # broken with nothing in the response to say why.
        secure=settings.is_production,
        # Lax rather than Strict: Strict breaks the return from the OAuth
        # callback, which arrives from an external origin (SECURITY_SPEC L2).
        samesite="Lax",
        path="/",
    )
    return response


def clear_trial_cookie(response):
    """
    Drop the cookie once its session has been claimed.

    Leaving it would tell the browser it is still mid-trial when the work now
    belongs to an account, and the next `POST /trial/sessions` would answer 409
    to someone who has since signed up.
    """
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


def _service(reason: str):
    """A service scope, with the reason spelled out (`ADR-0016`)."""
    return repo_scope(ServiceActor(reason))


def trial_case_version_id(case_id: str) -> uuid.UUID | None:
    """
    Resolve the case a trial runs. Transitional, as in `api/routes.py`.

    The seeded cases are drafts pending clinical review (T-023), so there is no
    published version to select yet. T-017 owns real case selection.
    """
    slug = CASE_SLUGS.get(case_id)
    if slug is None:
        return None
    with _service(
        "resolving the trial's case_versions row; the seeded cases are drafts "
        "pending clinical review (T-023), so no published version exists"
    ) as db:
        return db.cases.prototype_version_id(slug)


def start_trial():
    """
    `POST /v1/trial/sessions` — criteria 1 and 2.

    201 with the new session and an httpOnly cookie, or 409 if this browser has
    already had its free case.
    """
    from nidan.api.auth import error

    body = request.get_json(silent=True) or {}
    case_id = body.get("case_id") or next(iter(CASE_SLUGS))
    case = get_case(case_id)
    if case is None:
        return error("not_found", f"No such case: {case_id}.", 404)

    existing = visitor_id()
    if existing:
        with _service("checking whether this browser has used its free trial") as db:
            if TrialRepository(db.conn, db.actor).has_used_trial(existing):
                # UX_SPEC S-01 has the matching state: the landing page's
                # primary action becomes "Create a free account".
                return error("trial_already_used",
                             "You have used your free case. Create an account "
                             "to continue.", 409)

    case_version_id = trial_case_version_id(case_id)
    if case_version_id is None:
        return error("not_found", f"No such case: {case_id}.", 404)

    anonymous_id = existing or new_visitor_id()
    with anonymous_scope(anonymous_id) as db:
        row = db.sessions.create(case_version_id,
                                 confidence_pre=body.get("confidence_pre"))

    response = make_response(jsonify({
        "id": str(row["id"]),
        "status": row["status"],
        "started_at": row["started_at"].isoformat(),
        "patient": {
            "intro": case["patient_intro"],
            "opening_line": case["opening_line"],
        },
        # Empty, and deliberately present: a client should not have to guess
        # whether a new session has a transcript. No assessment state appears
        # here or anywhere else during a consultation (PRD P2, CT-1).
        "transcript": [],
        "examinations_performed": [],
        "investigations_ordered": [],
    }), 201)
    return set_trial_cookie(response, anonymous_id)
