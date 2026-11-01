"""
`/v1` consultation lifecycle — starting a session (`API_CONTRACT` §6).

The server picks the case, from the published bank only: `db.selection
.candidates()` filters on `status = 'published'`, so a draft is unreachable
here however complete it looks in the admin console. That is the whole point of
the publication gate.

Moved from `nidan/api/v1.py` unchanged when T-030 made v1 a package.
"""

from __future__ import annotations

from flask import jsonify, request

from nidan.api.auth import current_actor, require_auth
from nidan.api.errors import error
from nidan.api.trial import start_trial
from nidan.api.v1.blueprint import bp
from nidan.config import settings
from nidan.domain.selection import allowance_for, choose_case, month_start
from nidan.infra.clock import utc_now
from nidan.infra.db.repositories import repo_scope


@bp.post("/sessions")
@require_auth
def start_session():
    """
    `POST /v1/sessions` — start a consultation (`PRD` FR-3, FR-10.1).

    The server picks the case. The learner does not choose, and the response
    carries nothing that would tell them what is being tested (FR-3.4).
    """
    body = request.get_json(silent=True) or {}
    confidence = body.get("confidence_pre")
    if confidence is not None and confidence not in (1, 2, 3, 4, 5):
        return error("validation_failed",
                     "confidence_pre must be between 1 and 5.", 422)

    now = utc_now()

    with repo_scope(current_actor()) as db:
        profile = db.profiles.get()
        if profile is None:
            return error("not_found", "Complete your profile to continue.", 404)

        # A started case is reserved (FR-3.5). The session row IS the
        # reservation: it pins a case_version_id, so refreshing cannot reroll
        # it. FR-3's edge cases want resume-or-abandon, which is the client's
        # decision, so this reports the conflict rather than resolving it.
        active = db.sessions.active()
        if active is not None:
            return error("session_already_active",
                         "You already have a consultation in progress.", 409,
                         details={"session_id": str(active["id"])})

        allowance = allowance_for(
            profile["subscription_tier"],
            db.selection.sessions_started_since(
                month_start(now, profile["timezone"])),
            now=now, timezone_name=profile["timezone"],
            free_limit=settings.FREE_TIER_SESSIONS_PER_MONTH)

        # Blocked at case start, never mid-consultation (PRD FR-10 edge cases).
        if allowance.exhausted:
            return error(
                "monthly_limit_reached",
                f"You have used all {allowance.limit} of this month's cases. "
                f"Sessions you started and did not finish count too.",
                403,
                details={"resets_at": allowance.resets_at.isoformat(),
                         "limit": allowance.limit, "used": allowance.used})

        selection = choose_case(db.selection.candidates())
        if selection is None:
            # FR-3 edge case: "No published cases available | Friendly error;
            # alert raised to admin." Expected until T-023 publishes the five
            # seeded cases, which are drafts pending clinical review.
            return error("no_cases_available",
                         "No cases are available right now. We have been "
                         "notified.", 503)

        row = db.sessions.create(selection.case_version_id,
                                 confidence_pre=confidence)

    return jsonify({
        "id": str(row["id"]),
        "status": row["status"],
        "started_at": row["started_at"].isoformat(),
        # FR-3.2: a repeat must be marked, or the learner reads their own
        # memory of the answer as clinical reasoning.
        "is_repeat": selection.is_repeat,
        "transcript": [],
        "examinations_performed": [],
        "investigations_ordered": [],
    }), 201


@bp.post("/trial/sessions")
def trial_sessions():
    """
    `POST /v1/trial/sessions` — start the anonymous trial (`PRD` FR-2).

    No authentication: this is the endpoint a stranger hits. The handler lives
    in `api/trial.py` with the cookie helpers it shares with the claim path.
    """
    return start_trial()
