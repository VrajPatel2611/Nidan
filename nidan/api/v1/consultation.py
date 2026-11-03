"""
`/v1` consultation write path — asking, examining, investigating
(`API_CONTRACT` §6).

The three endpoints a learner spends a whole session in, and the ones where
`ADR-0003` earns its keep: every request replays the event log, acts, appends
what happened, and returns. Nothing is held in the process between requests,
which is why the app runs on two gunicorn workers and why killing it
mid-consultation loses nothing.

**No assessment state leaves here.** `matched_topics` is computed and stored on
every `patient_reply` event — T-016 compares a recomputation against it to
detect drift — and it is never returned. That is contract test CT-2 and `PRD`
FR-4.7: a learner who can see which topics they have covered optimises for the
meter instead of the history.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from flask import jsonify, request

from nidan.api.auth import current_actor, require_auth
from nidan.api.errors import error
from nidan.api.v1.blueprint import bp
from nidan.domain.assessment.topics import extract_topics
from nidan.domain.session import conversation_from, mentions_early_diagnosis
from nidan.infra.clock import utc_now
from nidan.infra.db.repositories import repo_scope
from nidan.infra.llm.gateway import call_llm

# `API_CONTRACT` §2.9. The per-session cap is pedagogical — a consultation
# that runs past forty questions is not a consultation any more. The hourly
# one is per USER across all their sessions, and protects the LLM bill and the
# provider's own rate limit, which do not care which session a question was in.
QUESTIONS_PER_SESSION = 40
QUESTIONS_PER_HOUR = 60

# §6: "> 500 characters". A limit on the question, not on the answer.
MAX_QUESTION_CHARS = 500


def _conclusion_refusal(row: Mapping[str, Any]):
    """
    None if the consultation is still open, otherwise the refusal.

    Shared by all three endpoints because all three mean the same thing by it:
    §6 gives them one code, `session_concluded`, and a diagnosis is
    irreversible.
    """
    if row["status"] != "active":
        return error("session_concluded",
                     "This consultation has already been submitted.")
    return None


@bp.post("/sessions/<uuid:session_id>/questions")
@require_auth
def ask_question(session_id: UUID):
    """
    `POST /v1/sessions/{id}/questions` — ask the patient. §6 calls it "the
    highest-volume endpoint".

    **The question is appended only after the reply comes back**, which is the
    opposite of orthodox event sourcing and deliberate. §6: "`patient_unavailable`
    must not consume the question… consuming it on failure would lose the
    user's work." There is a second reason the prototype found first and that
    matters more: `question_count` feeds the premature-closure detector
    (`P1: q < q_min`), so a question logged with no answer inflates the count
    and **suppresses a flag the learner should have seen**. Losing a question
    nobody answered is the cheaper mistake.

    **The database connection is not held across the model call.** It takes
    seconds; a pooled connection held that long is one nobody else can use.
    Two short transactions, with nothing written in the first.
    """
    body = request.get_json(silent=True) or {}
    text = str(body.get("text") or "").strip()

    if not text:
        return error("validation_failed", "A question needs some text.")
    if len(text) > MAX_QUESTION_CHARS:
        return error(
            "question_too_long",
            f"Questions are limited to {MAX_QUESTION_CHARS} characters; that "
            f"one is {len(text)}.",
            details={"limit": MAX_QUESTION_CHARS, "length": len(text)})

    now = utc_now()

    with repo_scope(current_actor()) as db:
        row = db.sessions.get(session_id)
        if row is None:
            return error("not_found", "No such consultation.")
        refusal = _conclusion_refusal(row)
        if refusal is not None:
            return refusal

        asked = db.events.count_of_type(session_id, "question")
        if asked >= QUESTIONS_PER_SESSION:
            return error(
                "question_limit_reached",
                "You have reached the limit of questions for this "
                "consultation. Submit your diagnosis to see your feedback.",
                details={"limit": QUESTIONS_PER_SESSION})

        recent = db.events.questions_since(now - timedelta(hours=1))
        if recent >= QUESTIONS_PER_HOUR:
            # §2.9: "429 responses carry `Retry-After` in seconds." Without it
            # a client either gives up or hammers; neither is what we want.
            response, status = error(
                "rate_limited",
                "You are asking questions faster than we can keep up. Try "
                "again in a few minutes.",
                details={"limit": QUESTIONS_PER_HOUR, "window": "1 hour"})
            response.headers["Retry-After"] = "300"
            return response, status

        events = db.events.all_for(session_id)
        content = db.cases.content(row["case_version_id"])
        early_already_noted = any(e.type == "early_diagnosis" for e in events)

    # Stored roles are "user"/"model"; the provider expects "user"/"assistant".
    messages = [
        {"role": "user" if m["role"] == "user" else "assistant",
         "content": m["content"]}
        for m in conversation_from(events)
    ]
    messages.append({"role": "user", "content": text})

    try:
        reply = call_llm(
            messages=messages,
            system_instruction=(content or {}).get("system_prompt", ""),
            purpose="patient",
        )
    except Exception:
        # 503, not 500: the request was fine and a dependency was not. The
        # reason is deliberately not echoed — a provider's error string can
        # carry prompt fragments, and the prompt is the patient's chart.
        # Nothing has been written, so the question is genuinely not consumed.
        return error(
            "patient_unavailable",
            "The patient could not respond just now. Your question has been "
            "kept — try sending it again.")

    with repo_scope(current_actor()) as db:
        question = db.events.append(session_id, "question", {
            "text": text, "char_count": len(text),
        })
        patient = db.events.append(session_id, "patient_reply", {
            "text": reply,
            # Stored, never returned. `DATA_MODEL` §8.2 — what the system
            # understood at the time, which T-016 recomputes against to detect
            # drift. Returning it is the CT-2 violation.
            "matched_topics": extract_topics(text),
        })
        if not early_already_noted and mentions_early_diagnosis(text):
            db.events.append(session_id, "early_diagnosis", {"text": text})
        db.sessions.touch(session_id)

    # `questions_remaining` is in §6's example for this endpoint and is NOT
    # returned. The spec contradicts itself about it and API-6 logs the
    # conflict; the 429 above carries the limit in `details`, so a learner who
    # runs out is told why without a counter running all session.
    return jsonify({
        "seq": patient.seq,
        "question": {"text": text, "at": _iso(question.created_at)},
        "reply": {"text": reply, "at": _iso(patient.created_at)},
    }), 201


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _order(session_id: UUID, *, kind: str, event_type: str,
           content_key: str, finding_key: str):
    """
    One implementation for examinations and investigations.

    §6 gives the two endpoints a single request shape, a single response shape
    and a single error table, so they are one function with two bindings
    rather than two functions that must be kept in step. They differ only in
    which master list validates the key and which part of the case content
    holds the abnormal answer.

    **The master list is the authority on what may be ordered**, and the case
    content only on what is found. That ordering is `PRD` FR-5.1: the menu is
    universal, so a key being absent from this case is not an error — it is a
    normal result, and that is the whole universal-panel design.
    """
    body = request.get_json(silent=True) or {}
    key = str(body.get("key") or "").strip()
    if not key:
        return error("validation_failed", f"Name the {kind} to order.")

    with repo_scope(current_actor()) as db:
        row = db.sessions.get(session_id)
        if row is None:
            return error("not_found", "No such consultation.")
        refusal = _conclusion_refusal(row)
        if refusal is not None:
            return refusal

        entry = db.catalog.master_entry(content_key, key)
        if entry is None:
            return error("unknown_key", f"There is no {kind} called {key!r}.",
                         details={"key": key})

        # Already ordered? §6: "returns the stored result without creating a
        # duplicate event (`PRD` FR-5.3, FR-6.3)." The event log is the record
        # of what the learner did, and ordering the same test twice is one
        # decision, not two — a duplicate would also inflate the
        # investigation count the scorecard divides by.
        for event in db.events.all_for(session_id):
            if event.type == event_type and event.payload.get("key") == key:
                return jsonify({
                    "key": key,
                    "label": event.payload["label"],
                    "result": event.payload[finding_key],
                    "at": _iso(event.created_at),
                    "already_ordered": True,
                }), 200

        content = db.cases.content(row["case_version_id"]) or {}
        case_specific = (content.get(content_key_for_case(content_key)) or {})
        was_case_specific = key in case_specific
        result = (case_specific[key][finding_key] if was_case_specific
                  else entry["normal_result"])
        # The master label always, so the same test reads the same on every
        # case even when a case author phrased its own label differently.
        label = entry["label"]

        event = db.events.append(session_id, event_type, {
            "key": key, "label": label, finding_key: result,
            # Stored for the scorecard, never returned: whether a result was
            # the case's own is a relevance signal, and §6 forbids `category`
            # and `is_key` here for exactly that reason (`PRD` FR-6.6).
            "was_case_specific": was_case_specific,
        })
        db.sessions.touch(session_id)

    return jsonify({
        "key": key, "label": label, "result": result,
        "at": _iso(event.created_at), "already_ordered": False,
    }), 201


def content_key_for_case(catalog_key: str) -> str:
    """
    `DATA_MODEL` §8.1 names the case's own blocks `examination` (singular) and
    `investigations` (plural), while the master tables are both plural. The
    asymmetry is in the stored content and not worth a migration to tidy, so
    it is mapped in one place instead of remembered in two.
    """
    return {"examinations": "examination",
            "investigations": "investigations"}[catalog_key]


@bp.post("/sessions/<uuid:session_id>/examinations")
@require_auth
def order_examination(session_id: UUID):
    """`POST /v1/sessions/{id}/examinations` — examine a system (§6)."""
    return _order(session_id, kind="examination", event_type="examination",
                  content_key="examinations", finding_key="finding")


@bp.post("/sessions/<uuid:session_id>/investigations")
@require_auth
def order_investigation(session_id: UUID):
    """`POST /v1/sessions/{id}/investigations` — order a test (§6)."""
    return _order(session_id, kind="investigation", event_type="investigation",
                  content_key="investigations", finding_key="result")
