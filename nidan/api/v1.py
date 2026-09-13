"""
The v1 JSON API (BUILD_PLAN T-014).

The first slice: identity. `openapi.yaml` declares the whole surface and T-030
implements the rest; everything not implemented here still answers 501, which
is what lets the frontend build against the contract (sync point S-1).

These routes are the JSON API the Next.js client will use (`ADR-0006`). The
server-rendered blueprint in `routes.py` is the prototype and is replaced at
T-030 — they coexist deliberately rather than one being half-migrated into the
other.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Blueprint, jsonify, make_response, request

from nidan.api.auth import current_actor, current_user_id, error, require_auth
from nidan.api.trial import clear_trial_cookie, start_trial, visitor_id
from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.trial import CLAIM_WINDOW_DAYS, TrialRepository

bp = Blueprint("v1", __name__)

# Fields a user may set on themselves. The repository has its own allow-list;
# this one exists so the API rejects an unknown field with a 422 naming it,
# rather than a 500 from a layer the client cannot see.
_WRITABLE = frozenset({
    "display_name", "professional_role", "year_of_training", "country",
    "timezone", "consent_research", "consent_version",
})


def _profile_json(row: Mapping[str, Any]) -> dict[str, Any]:
    """
    A profile as the contract describes it (`openapi.yaml` → `Profile`).

    Built explicitly rather than by dumping the row. A `SELECT *` reaching the
    client is how `research_pid` — the pseudonym that keeps analyses
    unlinkable — ends up in a response next to an email, which is exactly what
    `DATA_MODEL` §4.1 says must never happen.

    `sessions_remaining_this_month` is absent until T-017 owns the allowance.
    It is free-tier only and belongs on the dashboard, NEVER in a consultation
    (`PRD` P2).
    """
    return {
        "id": str(row["id"]),
        "display_name": row["display_name"],
        "professional_role": row["professional_role"],
        "year_of_training": row["year_of_training"],
        "country": row["country"],
        "timezone": row["timezone"],
        "subscription_tier": row["subscription_tier"],
        "consent_research": row["consent_research"],
        "onboarded_at": row["onboarded_at"].isoformat() if row["onboarded_at"] else None,
    }


@bp.post("/me")
@require_auth
def create_profile():
    """
    Create the authenticated user's profile. Idempotent (`API_CONTRACT` §3.1).

    The profile row is created here rather than by a database trigger, because
    creation needs `research_pid` generation, timezone capture and — from
    T-015 — trial claiming. Those are application concerns.

    Idempotent because clients retry and Supabase replays webhooks: the
    repository's INSERT is `ON CONFLICT DO NOTHING`, so two concurrent first
    requests both succeed instead of the second hitting a primary-key
    violation.
    """
    body = request.get_json(silent=True) or {}

    unknown = set(body) - _WRITABLE - {"anonymous_id"}
    if unknown:
        return error("validation_failed",
                     f"Unexpected field(s): {', '.join(sorted(unknown))}.", 422)

    fields = {k: v for k, v in body.items() if k in _WRITABLE}

    # The trial to claim, from the body or the cookie the browser is carrying
    # (PRD FR-2.4). The body wins, so a client that knows the id can claim one
    # without relying on the cookie surviving an OAuth round trip.
    anonymous_id = body.get("anonymous_id") or visitor_id()

    # Validated BEFORE the profile is created, so the common failure — a trial
    # older than the window — returns 422 having changed nothing. Creating the
    # profile first and then refusing would leave the user half-signed-up with
    # a 422 they cannot act on.
    if anonymous_id:
        refusal = _refuse_unclaimable_trial(anonymous_id)
        if refusal is not None:
            return refusal

    try:
        with repo_scope(current_actor()) as db:
            existed = db.profiles.get() is not None
            row = db.profiles.ensure(**fields)
    except ValueError as e:
        return error("validation_failed", str(e), 422)

    claimed: list = []
    if anonymous_id:
        # After the profile exists: sessions.user_id references profiles(id),
        # so claiming first would violate the foreign key.
        with repo_scope(ServiceActor(
            "claiming a trial session into the account that just signed up "
            "(PRD FR-2.4); the row is anonymous, so RLS cannot see it as the "
            "new owner"
        )) as db:
            claimed = TrialRepository(db.conn, db.actor).claim(
                anonymous_id, current_user_id())

    # 200 on a repeat, 201 on creation. Both are success — the criterion is
    # idempotency, not a fixed status — and the difference tells a client
    # whether onboarding still needs showing.
    payload = _profile_json(row)
    if claimed:
        # So the client can do what UX_SPEC §6.1.5 requires: send them to that
        # session's feedback page, and show them what they saved.
        payload["claimed_session_ids"] = [str(i) for i in claimed]

    response = jsonify(payload), (200 if existed else 201)
    if claimed:
        # The trial is over: the work belongs to an account now. Leaving the
        # cookie would make the next POST /trial/sessions answer 409 to
        # somebody who has already signed up.
        return clear_trial_cookie(make_response(*response))
    return response


def _refuse_unclaimable_trial(anonymous_id: str):
    """
    None if the trial can be claimed, otherwise the error to return.

    The three outcomes are deliberately distinct. "Nothing here" and "here, but
    too old" are different facts about the user's own work, and telling them
    the wrong one is worse than telling them nothing.
    """
    with repo_scope(ServiceActor(
        "checking whether a trial session is still within its claim window "
        "before creating the profile"
    )) as db:
        sessions = TrialRepository(db.conn, db.actor).sessions_for(anonymous_id)

    if not sessions:
        # Already claimed, or an identifier we have never seen. Not an error:
        # a client that always sends its cookie should not be blocked from
        # signing up because the cookie is stale.
        return None

    if not any(s["claimable"] for s in sessions):
        return error(
            "trial_expired",
            f"That trial is more than {CLAIM_WINDOW_DAYS} days old, so it can "
            f"no longer be added to an account.", 422)
    return None


@bp.get("/me")
@require_auth
def read_profile():
    """The authenticated user's profile."""
    with repo_scope(current_actor()) as db:
        row = db.profiles.get()

    if row is None:
        return error("not_found", "No profile yet. Create one with POST /me.", 404)
    return jsonify(_profile_json(row)), 200


@bp.post("/trial/sessions")
def trial_sessions():
    """
    `POST /v1/trial/sessions` — start the anonymous trial (`PRD` FR-2).

    No authentication: this is the endpoint a stranger hits. The handler lives
    in `api/trial.py` with the cookie helpers it shares with the claim path.
    """
    return start_trial()
