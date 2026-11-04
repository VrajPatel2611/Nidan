"""
`/v1` conclusion — submitting, reading feedback, rating it, abandoning
(`API_CONTRACT` §6).

Where a consultation ends and the assessment becomes visible. Three product
rules meet here and all three are contract tests:

- **CT-4** — `reasoning[].id` is a behavioural identifier, never a detector
  name. Enforced in `reasoning.py`, which is the only place a detector result
  becomes text.
- **CT-5** — no response body anywhere contains "anchoring", "premature
  closure" or "confirmation bias". The detectors' own `reason` strings do
  contain them, which is why `reasoning.py` rebuilds the prose from
  `counters` rather than forwarding it.
- **§2.8 idempotency** — required on the diagnosis, because concluding is
  irreversible and a client that retries a timed-out submit must not be told
  its first attempt failed when it succeeded.
"""

from __future__ import annotations

from uuid import UUID

from flask import jsonify, request

from nidan.api.auth import current_actor, require_auth
from nidan.api.errors import error
from nidan.api.v1.blueprint import bp
from nidan.api.v1.pagination import iso
from nidan.api.v1.reasoning import reasoning_json
from nidan.domain.assessment.engine import assess
from nidan.domain.session import replay
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.idempotency import body_hash
from nidan.infra.feedback import generate_feedback_with_source

# §6: "> 200 characters".
MAX_DIAGNOSIS_CHARS = 200

# §6 on `feedback_ready: false` — "the client polls `GET /feedback`". A hint,
# not a contract: the prose takes one model call, so a second or two.
FEEDBACK_RETRY_MS = 1500


@bp.post("/sessions/<uuid:session_id>/diagnosis")
@require_auth
def submit_diagnosis(session_id: UUID):
    """
    `POST /v1/sessions/{id}/diagnosis` — conclude. **Irreversible** (§6).

    **The double-submit guard is `sessions.complete()` returning False**, not
    a status check. The prototype's comment says why and it is worth keeping:
    that "makes a double-submit idempotent at the database rather than in a
    check the second request could race past." The §2.8 key layered on top
    replays the *response*; this stops the second *conclusion*.

    **Zero questions is permitted** (`PRD` FR-7 edge cases). The assessment
    runs and flags history completeness, which is the correct outcome rather
    than an error — a learner who guesses immediately has done something the
    product has an opinion about.
    """
    body = request.get_json(silent=True) or {}
    text = str(body.get("text") or "").strip()
    key = request.headers.get("Idempotency-Key")
    endpoint = "POST /v1/sessions/{id}/diagnosis"

    if not text:
        return error("diagnosis_empty", "Enter a diagnosis to conclude.")
    if len(text) > MAX_DIAGNOSIS_CHARS:
        return error(
            "diagnosis_too_long",
            f"A diagnosis is limited to {MAX_DIAGNOSIS_CHARS} characters; "
            f"that one is {len(text)}.",
            details={"limit": MAX_DIAGNOSIS_CHARS, "length": len(text)})

    request_hash = body_hash(body)

    if key:
        with repo_scope(current_actor()) as db:
            seen = db.idempotency.find(key, endpoint)
        if seen is not None:
            if seen["request_hash"] != request_hash:
                return error(
                    "idempotency_key_reused",
                    "That Idempotency-Key was used with a different request "
                    "body. Use a new key for a new submission.")
            if seen["response"] is not None:
                # §2.8: "a repeat with the same key and the same body replays
                # the stored response." Byte-for-byte, including the status.
                return jsonify(seen["response"]), seen["status_code"]

    with repo_scope(current_actor()) as db:
        row = db.sessions.get(session_id)
        if row is None:
            return error("not_found", "No such consultation.")

        first = db.sessions.complete(session_id)
        if not first:
            # §10's code is `session_concluded`; §6's table at this endpoint
            # calls it `session_already_concluded`, which is not in the
            # catalogue. The catalogue wins — "once shipped, a code is never
            # renamed" — and the §6 mention is a typo, logged as API-7.
            return error(
                "session_concluded",
                "This consultation has already been submitted.",
                details={"submitted_at": iso(row["diagnosis_submitted_at"])})

        db.events.append(session_id, "diagnosis", {"text": text})
        events = db.events.all_for(session_id)
        content = db.cases.case_for_session(row["case_version_id"])
        engine = db.engines.current()

    # Assessed from the event log under the engine version in force, then
    # stored with its id (T-016). Everything the feedback screen renders is
    # recomputed from the log; this row is the durable analytical record for
    # progress trends, the research export and threshold calibration.
    if content is None:
        # The version was unpublished or retired between starting and
        # concluding. Nothing can be assessed against content that is gone,
        # and the learner's work is still in the log to assess later.
        return error("no_cases_available",
                     "This case is no longer available. Your consultation has "
                     "been saved.")

    case = dict(content)
    result = assess(events, case, engine)
    session_state = replay(events, case_id=case["id"],
                           started_at=_first_at(events))
    feedback = generate_feedback_with_source(
        result.bias_detail, result.clinical_eval, session_state, case)

    with repo_scope(current_actor()) as db:
        if engine is not None:
            db.results.save(session_id, result)
        db.feedback.save(session_id, feedback.lines,
                         generator=feedback.generator)
        # None when the model was unavailable and the rule-based fallback
        # produced the prose — there was no call to cost.
        if feedback.call is not None:
            db.llm_calls.record_call(feedback.call, session_id=session_id)
        if content is not None:
            db.selection.record_attempt(
                db.selection.case_id_for_version(row["case_version_id"]),
                result.clinical_eval["diagnosis"]["verdict"])

    payload = {
        "session_id": str(session_id),
        "status": "completed",
        # True because the prose is written synchronously above. §6 allows
        # false and a polling client; nothing here needs it yet, and a field
        # that is always true is cheaper to keep honest than a queue.
        "feedback_ready": True,
    }
    if key:
        with repo_scope(current_actor()) as db:
            db.idempotency.remember(key, endpoint, request_hash,
                                    response=payload, status_code=201)
    return jsonify(payload), 201


def _first_at(events) -> str:
    """
    When the consultation started, for `replay`.

    Taken from the first event rather than `sessions.started_at` because
    `replay` is the domain's reconstruction and `ADR-0003` makes the log its
    only input — a duration computed partly from a column the log cannot see
    would not be reproducible from the log.
    """
    first = events[0].created_at if events else None
    return first.isoformat() if first is not None else ""


@bp.get("/sessions/<uuid:session_id>/feedback")
@require_auth
def read_feedback(session_id: UUID):
    """
    `GET /v1/sessions/{id}/feedback` (§6).

    **Every number here is recomputed from the stored result, and the prose
    alone is read back.** `ADR-0005`: only the prose cannot be recomputed,
    because a model wrote it. The rest is derived state and `ADR-0003` makes
    the log its source.

    `answer` is returned, and that is not a CT-1 violation. FR-3.4 forbids
    those fields in the **case** object during a consultation; afterwards the
    answer is the point. `UX_SPEC` keeps it collapsed until the learner asks
    (`PRD` FR-8.8), which is a client concern.
    """
    with repo_scope(current_actor()) as db:
        row = db.sessions.get(session_id)
        if row is None:
            return error("not_found", "No such consultation.")
        if row["diagnosis_submitted_at"] is None:
            return error("session_not_concluded",
                         "Submit a diagnosis to see your feedback.")

        stored = db.results.get(session_id)
        prose = db.feedback.latest(session_id)
        content = db.cases.case_for_session(row["case_version_id"]) or {}
        if stored is None or prose is None:
            # §6: "retry after `details.retry_after_ms`". 404 and not 500 —
            # nothing is broken, the work is not finished.
            return error("feedback_not_ready",
                         "Your feedback is still being written.",
                         details={"retry_after_ms": FEEDBACK_RETRY_MS})
        db.events.append(session_id, "feedback_viewed", {})

    return jsonify({
        "session_id": str(session_id),
        "diagnosis_submitted": stored["diagnosis_submitted"],
        "verdict": stored["diagnosis_verdict"],
        "summary": {
            "question_count": stored["question_count"],
            "examination_count": stored["examination_count"],
            "investigation_count": stored["investigation_count"],
            "coverage_pct": float(stored["coverage_pct"]),
            "duration_seconds": stored["duration_seconds"],
        },
        "tutor_feedback": {
            "lines": list(prose["lines"]),
            "generator": prose["generator"],
        },
        "coverage": {
            "topics_hit": list(stored["topics_hit"]),
            "topics_missed": list(stored["topics_missed"]),
        },
        "examination_scorecard": stored["exam_scorecard"],
        "investigation_scorecard": stored["investigation_scorecard"],
        # The CT-4 and CT-5 choke point. Never `bias_detail` as stored: its
        # keys ARE the banned vocabulary and its `reason` strings contain it.
        "reasoning": reasoning_json(stored["bias_detail"]),
        "answer": {
            "correct_diagnosis": content.get("correct_diagnosis"),
            # §6 also shows `trap_explanation`. No such field exists in
            # `case_versions.content` (`DATA_MODEL` §8.1), in `cases.py`, or
            # anywhere else — so there is nothing to return and inventing the
            # prose server-side from `anchor_topic` would be worse than
            # omitting it. Logged as API-8.
            "anchor_topic": content.get("anchor_topic"),
        },
    }), 200


@bp.post("/sessions/<uuid:session_id>/feedback/rating")
@require_auth
def rate_feedback(session_id: UUID):
    """
    `POST /v1/sessions/{id}/feedback/rating` → 204 (§6, `UX_SPEC` UX-3).

    Stored on `feedback_texts`, which already has `was_helpful` and
    `rated_at` — the rating is about the prose a model wrote, not about the
    assessment, and keeping it on the same row is what makes "was the LLM
    feedback useful" answerable per generator.
    """
    body = request.get_json(silent=True) or {}
    was_helpful = body.get("was_helpful")
    if not isinstance(was_helpful, bool):
        return error("validation_failed", "was_helpful must be true or false.")

    with repo_scope(current_actor()) as db:
        row = db.sessions.get(session_id)
        if row is None:
            return error("not_found", "No such consultation.")
        if db.feedback.rate(session_id, was_helpful=was_helpful) is False:
            return error("feedback_not_ready",
                         "There is no feedback to rate yet.",
                         details={"retry_after_ms": FEEDBACK_RETRY_MS})
    return "", 204


@bp.post("/sessions/<uuid:session_id>/abandon")
@require_auth
def abandon_session(session_id: UUID):
    """
    `POST /v1/sessions/{id}/abandon` → 204 (§6).

    **Still counts toward the monthly allowance** (`PRD` FR-3 edge cases), and
    nothing here has to do anything about that: `sessions_started_since()`
    counts started sessions whatever their status, so abandoning is already
    not a way to get a free attempt.
    """
    with repo_scope(current_actor()) as db:
        row = db.sessions.get(session_id)
        if row is None:
            return error("not_found", "No such consultation.")
        refusal_needed = row["status"] != "active"
        if refusal_needed:
            return error("session_concluded",
                         "This consultation is no longer active.")
        db.sessions.abandon(session_id)
    return "", 204
