"""
`/v1` progress and account lifecycle (`API_CONTRACT` §4, §7).

Three endpoints, and only two of them ship. `DELETE /me` is deliberately still
a 501 — see `nidan/api/v1/contract.py` and API-9 in `API_CONTRACT` §13 for why
that is an honest answer rather than unfinished work.
"""

from __future__ import annotations

from datetime import timedelta

from flask import jsonify

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
    be ready IS the endpoint — what is missing is the worker that builds the
    file and the mail that sends it, and neither has a task in `BUILD_PLAN`.
    Logged as API-10 so it is not mistaken for finished.

    Recorded in `audit_log`, which is append-only and already the record of
    things done to an account. A data-subject access request is exactly the
    kind of event you want to be able to prove you received.
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
