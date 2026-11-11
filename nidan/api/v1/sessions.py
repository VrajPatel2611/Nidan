"""
`/v1` consultation lifecycle — starting a session (`API_CONTRACT` §6).

The server picks the case, from the published bank only: `db.selection
.candidates()` filters on `status = 'published'`, so a draft is unreachable
here however complete it looks in the admin console. That is the whole point of
the publication gate.

Moved from `nidan/api/v1.py` unchanged when T-030 made v1 a package.
"""

from __future__ import annotations

from uuid import UUID

from flask import jsonify, request

from nidan.api.auth import current_actor, require_auth
from nidan.api.errors import error
from nidan.api.trial import start_trial
from nidan.api.v1.blueprint import bp
from nidan.api.v1.case_view import case_json
from nidan.api.v1.pagination import (
    InvalidCursor,
    decode_cursor,
    encode_cursor,
    iso,
    page,
    read_limit,
)
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

    with repo_scope(current_actor()) as db:
        content = db.cases.case_for_session(selection.case_version_id)

    return jsonify({
        "session_id": str(row["id"]),
        "sequence_index": row["sequence_index"],
        "status": row["status"],
        "started_at": iso(row["started_at"]),
        # FR-3.2: a repeat must be marked, or the learner reads their own
        # memory of the answer as clinical reasoning. Not in §6's example and
        # required by the functional spec, so it is in the schema too.
        "is_repeat": selection.is_repeat,
        # Presentation fields only, through the one serialiser that knows what
        # those are (`PRD` FR-3.4, CT-1).
        "case": case_json(content or {}),
        "transcript": [],
        "examinations_done": [],
        "investigations_done": [],
    }), 201


@bp.post("/trial/sessions")
def trial_sessions():
    """
    `POST /v1/trial/sessions` — start the anonymous trial (`PRD` FR-2).

    No authentication: this is the endpoint a stranger hits. The handler lives
    in `api/trial.py` with the cookie helpers it shares with the claim path.
    """
    return start_trial()


@bp.get("/sessions")
@require_auth
def list_sessions():
    """
    `GET /v1/sessions` — the learner's own history, newest first
    (`API_CONTRACT` §7).

    Cursor-paginated, because §2.5 rules out offsets: "it produces duplicates
    and gaps when rows are inserted mid-scroll." The learner who finishes a
    consultation and then pages back through their history is exactly the
    person that would bite.

    Ownership is the database's job, not this handler's. The query carries no
    `WHERE user_id = ...`; `repo_scope` has set `auth.uid()` and migration
    016's `own_sessions` policy does the filtering, so a forgotten clause
    returns nothing rather than someone else's consultations (`ADR-0016`).
    """
    try:
        limit = read_limit(request.args.get("limit"))
        raw = request.args.get("cursor")
        after = None
        if raw:
            payload = decode_cursor(raw)
            after = (payload["started_at"], UUID(payload["id"]))
    except (InvalidCursor, KeyError, TypeError, ValueError) as e:
        return error("validation_failed",
                     f"Could not read the pagination parameters: {e}")

    with repo_scope(current_actor()) as db:
        rows = list(db.sessions.page(limit=limit, after=after))

    def cursor_for(row) -> str:
        return encode_cursor({"started_at": iso(row["started_at"]),
                              "id": str(row["id"])})

    body = {
        "data": [
            {
                "session_id": str(r["id"]),
                "case_title": r["case_title"],
                "status": r["status"],
                # None for a session with no result yet — active, or
                # abandoned. Omitting those rows would hide the learner's own
                # unfinished work from their own history.
                "verdict": r["verdict"],
                # NUMERIC arrives as Decimal, which json cannot serialise.
                "coverage_pct": (float(r["coverage_pct"])
                                 if r["coverage_pct"] is not None else None),
                "started_at": iso(r["started_at"]),
                "ended_at": iso(r["ended_at"]),
            }
            for r in rows[:limit]
        ],
        **page(rows, limit, cursor_for=cursor_for),
    }
    return jsonify(body), 200


# `API_CONTRACT` §2.9: "Questions per session | 40 total". Enforcing it is
# slice 3.
#
# **Not reported in the response**, and settled as API-6 on 11 Nov 2026.
# §6 used to say it should be — "a hard cap, not a progress metric" — and
# justified that by citing `UX_SPEC` S-10 as surfacing it near zero. S-10's
# table of what is deliberately absent opens with "Question counter | U2", so
# §6 was misreading its own cited source; it has been corrected. `PRD` P2,
# CT-1/CT-2 and `tests/test_openapi.py` never disagreed, and `CLAUDE.md` reads
# the same way about the monthly allowance: "a visible counter teaches the
# counter."
#
# The cap stays a refusal: 429 `question_limit_reached` carries {"limit": 40}.
# A client needing the figure counts `transcript` entries of type "question",
# which the session response already returns — so this constant stays the one
# home for the 40. Reasoning in full at API_CONTRACT §13 API-6.
QUESTION_CAP = 40


@bp.get("/sessions/<uuid:session_id>")
@require_auth
def read_session(session_id: UUID):
    """
    `GET /v1/sessions/{id}` — full state, for resuming (`API_CONTRACT` §6).

    **404 for someone else's session, never 403** (§2.7): "Returning 403
    confirms the resource exists." Nothing in this handler implements that.
    `sessions.get()` carries no owner filter and migration 016's
    `own_sessions` policy returns no row, so the answer is 404 by the same
    path as a genuinely absent id — which is the only way the two can be
    indistinguishable. That is CT-9.

    **The transcript is built field by field, and that is load-bearing.** A
    `patient_reply` payload may carry `matched_topics` (`DATA_MODEL` §8.2),
    which is coverage state: returning the payload as stored would hand the
    learner the assessment mid-consultation and break CT-2 and `PRD` P2. The
    event log is the right place for it and the response is not.
    """
    with repo_scope(current_actor()) as db:
        row = db.sessions.get(session_id)
        if row is None:
            return error("not_found", "No such consultation.")
        events = db.events.all_for(session_id)
        content = db.cases.case_for_session(row["case_version_id"])

    transcript = []
    examinations, investigations = [], []
    for event in events:
        at = iso(event.created_at)
        if event.type == "question":
            transcript.append({"seq": event.seq, "type": "question",
                               "text": event.payload["text"], "at": at})
        elif event.type == "patient_reply":
            # Only `text`. See the docstring: the payload may also hold
            # `matched_topics`.
            transcript.append({"seq": event.seq, "type": "patient_reply",
                               "text": event.payload["text"], "at": at})
        elif event.type == "examination":
            examinations.append({"key": event.payload["key"],
                                 "label": event.payload["label"],
                                 "finding": event.payload["finding"], "at": at})
        elif event.type == "investigation":
            investigations.append({"key": event.payload["key"],
                                   "label": event.payload["label"],
                                   "result": event.payload["result"], "at": at})

    return jsonify({
        "session_id": str(row["id"]),
        "sequence_index": row["sequence_index"],
        "status": row["status"],
        "started_at": iso(row["started_at"]),
        "last_activity_at": iso(row["last_activity_at"]),
        "case": case_json(content or {}),
        "transcript": transcript,
        "examinations_done": examinations,
        "investigations_done": investigations,
    }), 200
