"""
`/v1` progress and account lifecycle (`API_CONTRACT` §4, §7).

Three endpoints, and all three ship. `DELETE /me` was a 501 until API-9 was
settled on 22 Nov 2026: migration 033 gives `session_events` a single
permitted mutation, so `DATA_MODEL` §10.2's erasure can finally run. See
`ADR-0018` for why that exception is narrower than it sounds.
"""

from __future__ import annotations

from datetime import timedelta

from flask import jsonify, request

from nidan.api.auth import current_actor, current_user_id, require_auth
from nidan.api.errors import error
from nidan.api.v1.blueprint import bp
from nidan.api.v1.pagination import iso
from nidan.api.v1.reasoning import reasoning_trends_json
from nidan.infra.clock import utc_now
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.progress import MIN_SESSIONS_FOR_TRENDS

# §4: "Generates a JSON export, emailed within 24 h" (`PRD` FR-11.3).
EXPORT_SLA_HOURS = 24

# `UX_SPEC` S-20: "Your name, email and profile are removed within 24 h".
# The same number as the export SLA today and deliberately not the same
# constant: they are promises about different things, and one of them
# moving should not move the other by accident.
ERASURE_SLA_HOURS = 24

# Every verdict `session_results` allows, so the distribution has all four
# keys at zero rather than omitting them. A client that must handle a missing
# key renders differently for a learner who has never been wrong, and that is
# the one learner you least want a layout bug for.
VERDICTS = ("correct", "partial", "anchored", "other")


@bp.get("/progress")
@require_auth
def read_progress():
    """
    `GET /v1/progress` — trends over the learner's own history (§7).

    **`has_sufficient_data` drives an empty state rather than an empty
    screen** (`UX_SPEC` S-16). Below three sessions the figures are still
    returned — they are true — but the flag tells the client to say "not yet"
    instead of drawing a two-point line and calling it a trend.

    Computed on read. `user_progress` exists and has never been written to;
    `ProgressRepository` says why, and `DATA_MODEL` §11.5 is the query if a
    cache is ever justified.
    """
    with repo_scope(current_actor()) as db:
        profile = db.profiles.get()
        if profile is None:
            return error("not_found", "No profile yet. Create one with POST /me.")

        summary = db.progress.summary()
        series = db.progress.coverage_series()
        verdicts = db.progress.verdict_distribution()
        streaks = db.progress.streaks(profile["timezone"])

    completed = summary["sessions_completed"] or 0
    mean_coverage = summary["mean_coverage_last10"]

    return jsonify({
        "sessions_completed": completed,
        "current_streak_days": streaks["current_streak_days"],
        "longest_streak_days": streaks["longest_streak_days"],
        # NUMERIC arrives as Decimal, which json cannot serialise. None with
        # no completed sessions, rather than 0.0 — a learner who has done
        # nothing has no mean coverage, and 0% would read as a bad score.
        "mean_coverage_last10": (round(float(mean_coverage), 1)
                                 if mean_coverage is not None else None),
        "has_sufficient_data": completed >= MIN_SESSIONS_FOR_TRENDS,
        "coverage_series": [
            {
                "session_index": row["session_index"],
                "coverage_pct": float(row["coverage_pct"]),
                "at": iso(row["ended_at"]),
            }
            for row in series
        ],
        # The CT-4/CT-5 boundary again: the repository's columns are named
        # `anchoring_last10` and friends, and a progress payload built from
        # them would carry the banned word in a field name.
        "reasoning_trends": reasoning_trends_json(summary),
        "verdict_distribution": {v: verdicts.get(v, 0) for v in VERDICTS},
    }), 200


@bp.post("/me/export")
@require_auth
def request_export():
    """
    `POST /v1/me/export` → **202 Accepted** (§4, `PRD` FR-11.3).

    202 is the whole contract here: it means "accepted, not done". So an
    implementation that durably records the request and reports when it should
    be ready IS the endpoint — and since T-038 the work behind it happens.
    `python -m nidan.jobs run` builds the JSON and emails it; API-10 is
    closed.

    Recorded in `audit_log`, which is append-only and already the record of
    things done to an account. A data-subject access request is exactly the
    kind of event you want to be able to prove you received — **and it is also
    the queue.** `audit_log` refuses UPDATE, so the worker cannot mark this
    row done; it appends `export.built` and `export.emailed`, and
    `AuditRepository.pending()` is the difference between the two sets. This
    row is therefore the only durable record of the request, which is what
    T-038 criterion 3 means by "a crash loses nothing".
    """
    now = utc_now()
    ready_at = now + timedelta(hours=EXPORT_SLA_HOURS)

    with repo_scope(current_actor()) as db:
        if db.profiles.get() is None:
            return error("not_found", "No profile yet. Create one with POST /me.")
        db.audit.record(
            action="profile.export_requested",
            entity_type="profile",
            entity_id=current_user_id(),
            reason="data subject access request (PRD FR-11.3)",
            metadata={"sla_hours": EXPORT_SLA_HOURS,
                      "estimated_ready_at": ready_at.isoformat()},
        )

    return jsonify({"status": "queued",
                    "estimated_ready_at": iso(ready_at)}), 202


@bp.delete("/me")
@require_auth
def delete_account():
    """
    `DELETE /v1/me` → **202 Accepted** (§4, `DATA_MODEL` §10.2). Irreversible.

    **202, not 204 — and that is the change API-9 forced.** §4 said 204, which
    claims the erasure finished inside the request. Three of its steps are
    outbound calls we do not own: deleting the credential through the Supabase
    admin API (`ADR-0002`), cancelling at the payment provider, and the
    confirmation email S-20 promises. A handler that attempted them would
    answer 500 on a partial failure, with no retry and an account in an
    unknown state. `UX_SPEC` S-20 already told the user "within 24 h"; the
    contract was the thing out of step.

    Since T-038 those three steps are performed by `python -m nidan.jobs run`,
    in S-20's order — the confirmation email first, because the address lives
    in `auth.users` and after the credential is deleted there is nothing left
    to fetch.

    **What does happen before this returns is everything in the database**,
    in one transaction: billing cancelled, the profile anonymised and stamped
    `deleted_at`, every `payload->'text'` redacted, feedback prose replaced.
    So 202 here means "your data is erased; the external cleanup follows",
    not "queued, nothing done yet" — which is the honest reading of the
    status and the opposite of what `/me/export` can currently claim.

    The confirmation is checked before anything else. §4 requires
    `{"confirmation": "DELETE"}` and S-20 disables the button until the word
    is typed exactly; a destructive endpoint should not depend on the client
    having implemented that.
    """
    body = request.get_json(silent=True) or {}
    if body.get("confirmation") != "DELETE":
        return error(
            "confirmation_required",
            'Deleting an account requires {"confirmation": "DELETE"}. '
            'This cannot be undone.')

    user_id = current_user_id()

    # One transaction, as the user themselves. Three reasons, and the first is
    # the one that decided it:
    #
    # `AuditRepository.record` takes the actor from the scope and refuses to be
    # told who acted — "an audit log that can be made to lie about who acted is
    # worse than none". Under a service actor there is no `user_id` to record,
    # and splitting the audit row into a second scope would mean either logging
    # an intention before the work (a lie if it then fails) or committing the
    # erasure and the proof of it separately.
    #
    # It also makes the whole erasure atomic: billing, profile, events and
    # feedback either all go or none do. And RLS applies on top of the explicit
    # `WHERE user_id = :uid` in the repository, so the statements are scoped
    # twice — which is what `ADR-0016` means by defence in depth.
    with repo_scope(current_actor()) as db:
        if db.profiles.get() is None:
            # Already erased, or never created. The same 404 either way: §2.7
            # declines to confirm the existence of things, and "you have
            # already been deleted" is a fact about an account we have just
            # been asked to forget.
            return error("not_found", "No profile yet. Create one with POST /me.")

        result = db.erasure.erase(user_id)

        # Append-only, and the only record that survives the erasure. Counts,
        # never content — an audit row naming what was redacted would be the
        # erasure keeping what it erased (`domain/guard.py` has the same rule).
        #
        # Written last, inside the same transaction, so it cannot exist unless
        # the erasure it attests to also committed.
        db.audit.record(
            action="profile.erased",
            entity_type="profile",
            entity_id=user_id,
            reason="account deletion requested by the user (DATA_MODEL §10.2)",
            metadata={
                "events_redacted": result.events_redacted,
                "feedback_redacted": result.feedback_redacted,
                "subscriptions_cancelled": result.subscriptions_cancelled,
                # What is left, named so the worker's job is legible from the
                # record rather than only from this docstring.
                "pending": ["auth.users", "payment_provider",
                            "confirmation_email"],
                "sla_hours": ERASURE_SLA_HOURS,
            },
        )

    return jsonify({
        "status": "erased",
        # S-20's "what we keep, and why", in the response as well as on the
        # screen. A user has a right to know what does not disappear, and a
        # client built from the schema should not have to go and read §10.2.
        "retained": ["anonymised results", "research pseudonym"],
        "completes_within_hours": ERASURE_SLA_HOURS,
    }), 202
