"""
Playtest routes (BUILD_PLAN T-022, UX_SPEC §12.5).

A split view: the consultation exactly as a learner sees it on the left, and on
the right everything the assessment engine concludes, recomputed after every
action.

**Ephemeral by construction.** A playtest has no `sessions` row and writes no
`session_events` or `session_results`. The event log lives in the browser: each
request carries the events so far, the server validates them, appends the new
ones, runs `assess()` and sends the whole list back. Nothing is stored between
requests, so there is nothing to clean up, nothing for analytics or the research
export to find, and Reset is just an empty list.

Why the browser rather than the Flask session: the session is a signed cookie,
capped at about 4 KB, and a dozen patient replies outgrow it. Why not server
memory: under gunicorn each worker has its own, so consecutive requests would
see different playtests. The event list is the author's own working state, and
the only thing it can mislead is the author's own panel.

Draft versions are playtestable — that is the point. The version is loaded with
`for_review`, which returns any status, behind `@require_reviewer`: clinical
reviewers open a version here to judge it (T-023), and administrators get the
same reviewer scope — playtesting reads, and never needs the right to author.
Opened with `?review=1`, the page carries the review form beside the panel.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from flask import Blueprint, jsonify, render_template, request

from nidan.api.auth import current_reviewer, error, require_reviewer
from nidan.domain.content.cases import MASTER_EXAMINATIONS, MASTER_INVESTIGATIONS
from nidan.domain.events import Event, validate_payload
from nidan.domain.session import conversation_from, mentions_early_diagnosis
from nidan.infra.db.repositories import repo_scope
from nidan.infra.llm import gateway
from nidan.web.admin.playtest import instrumentation
from nidan.web.admin.reviews.routes import form_context

playtest_bp = Blueprint("admin_playtest", __name__, url_prefix="/admin/cases")

# Event types a playtest can produce. `feedback_viewed` and `input_blocked`
# belong to the learner app and are refused if a client sends them.
_PLAYTEST_TYPES = frozenset({
    "question", "patient_reply", "examination", "investigation",
    "early_diagnosis", "diagnosis",
})

# Bounds on what a client may send back. Generous for an afternoon of tuning a
# persona; small enough that a runaway page cannot post megabytes per question.
MAX_EVENTS = 400
MAX_TEXT = 2000


class BadEvents(ValueError):
    """The posted event list is not one this page could have produced."""


def _not_found():
    # The same body `require_reviewer` returns, so a missing version and a missing
    # privilege cannot be told apart.
    return error("not_found", "Not found.", 404)


def _load_case(case_id: UUID, version_id: UUID) -> tuple[dict[str, Any] | None, Any]:
    """
    The version as the engine expects a case, plus the engine version in force.

    Returns (None, None) if the version does not exist or belongs to another
    case. `id` is added because `assess()` needs one and stored content has none.
    """
    with repo_scope(current_reviewer()) as db:
        row = db.cases.for_review(version_id)
        if row is None or row["case_id"] != case_id:
            return None, None
        engine = db.engines.current()

    case = dict(row["content"] or {})
    case["id"] = str(version_id)
    case["_meta"] = {
        "case_id": row["case_id"], "version_id": row["id"],
        "version": row["version"], "status": row["status"],
        "title": row["title"] or case.get("title") or row["slug"],
        "slug": row["slug"],
    }
    return case, engine


def _parse_events(raw: Any) -> list[Event]:
    """Validate the client's event list and rebuild it as `Event`s."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise BadEvents("events must be a list")
    if len(raw) > MAX_EVENTS:
        raise BadEvents(f"a playtest is limited to {MAX_EVENTS} events — reset to continue")

    events = []
    for seq, item in enumerate(raw, start=1):
        if not isinstance(item, Mapping):
            raise BadEvents("each event must be an object")
        event_type, payload = item.get("type"), item.get("payload")
        if event_type not in _PLAYTEST_TYPES or not isinstance(payload, Mapping):
            raise BadEvents(f"event {seq} is not a playtest event")
        try:
            validate_payload(event_type, payload)
        except ValueError as exc:
            raise BadEvents(f"event {seq}: {exc}") from exc
        for value in payload.values():
            if isinstance(value, str) and len(value) > MAX_TEXT:
                raise BadEvents(f"event {seq} is too long")
        events.append(Event(seq=seq, type=event_type, payload=dict(payload)))
    return events


def _append(events: list[Event], event_type: str, payload: dict[str, Any]) -> None:
    validate_payload(event_type, payload)
    events.append(Event(seq=len(events) + 1, type=event_type, payload=payload))


def _respond(case: dict[str, Any], engine, events: list[Event], **extra):
    """Both panels re-rendered from the events, plus the events themselves."""
    panel = instrumentation.build(events, case, engine)
    return jsonify({
        "events": [{"type": e.type, "payload": dict(e.payload)} for e in events],
        "student_html": render_template(
            "admin/playtest/_student.html", case=case, events=events),
        "instrumentation_html": render_template(
            "admin/playtest/_instrumentation.html", panel=panel),
        **extra,
    })


def _body() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _request_context(case_id: UUID, version_id: UUID):
    """Load the case and the posted events, or produce the error response."""
    case, engine = _load_case(case_id, version_id)
    if case is None:
        return None, None, None, _not_found()
    try:
        events = _parse_events(_body().get("events"))
    except BadEvents as exc:
        return None, None, None, (jsonify({"error": str(exc)}), 400)
    return case, engine, events, None


def _has_diagnosis(events: list[Event]) -> bool:
    return any(e.type == "diagnosis" for e in events)


def _grouped(master: Mapping[str, Mapping[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    groups: dict[str, list[tuple[str, str]]] = {}
    for key, entry in master.items():
        groups.setdefault(entry.get("group", "Other"), []).append((key, entry["label"]))
    return groups


# ── the page ─────────────────────────────────────────────────────────

@playtest_bp.get("/<uuid:case_id>/versions/<uuid:version_id>/playtest")
@require_reviewer
def index(case_id: UUID, version_id: UUID):
    """Playtest (A-04): an empty consultation and the panel for it."""
    case, engine = _load_case(case_id, version_id)
    if case is None:
        return _not_found()

    with repo_scope(current_reviewer()) as db:
        profile = db.profiles.get()
    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    reviewing = request.args.get("review") == "1"
    return render_template(
        "admin/playtest/index.html",
        active_nav="cases",
        active_section="review_queue" if reviewing else "case_bank",
        user_email=user_email,
        review=form_context(version_id) if reviewing else None,
        case=case,
        meta=case["_meta"],
        events=[],
        panel=instrumentation.build([], case, engine),
        examinations=_grouped(MASTER_EXAMINATIONS),
        investigations=_grouped(MASTER_INVESTIGATIONS),
    )


@playtest_bp.post("/<uuid:case_id>/versions/<uuid:version_id>/playtest/state")
@require_reviewer
def state(case_id: UUID, version_id: UUID):
    """Re-render both panels for the posted events. Reset posts an empty list."""
    case, engine, events, error = _request_context(case_id, version_id)
    if error:
        return error
    return _respond(case, engine, events)


@playtest_bp.post("/<uuid:case_id>/versions/<uuid:version_id>/playtest/ask")
@require_reviewer
def ask(case_id: UUID, version_id: UUID):
    """Put a question to the patient. The reply comes from the persona prompt."""
    case, engine, events, error = _request_context(case_id, version_id)
    if error:
        return error

    message = str(_body().get("message", "")).strip()
    if not message:
        return jsonify({"error": "Type a question first."}), 400
    if len(message) > MAX_TEXT:
        return jsonify({"error": "That question is too long."}), 400
    if _has_diagnosis(events):
        return jsonify({"error": "A diagnosis has been given. Reset to start again."}), 409
    if not case.get("system_prompt"):
        return jsonify({"error": "This version has no persona prompt, so the patient "
                                 "cannot reply. Add one in the case editor."}), 400

    messages = [
        {"role": "user" if m["role"] == "user" else "assistant",
         "content": m["content"]}
        for m in conversation_from(events)
    ]
    messages.append({"role": "user", "content": message})

    try:
        # purpose="playtest" keeps these calls out of cost-per-session
        # reporting (UX_SPEC §12.5) once T-031 starts logging by purpose.
        reply = gateway.call_llm(
            messages=messages,
            system_instruction=case["system_prompt"],
            purpose="playtest",
            max_tokens=200,
            temperature=0.7,
        )
    except Exception:
        return jsonify({"error": "The patient could not respond. Try again in a "
                                 "few seconds."}), 503

    early = (not any(e.type == "early_diagnosis" for e in events)
             and mentions_early_diagnosis(message))

    # The same three events, with the same payloads, that the live consultation
    # appends — so the engine sees a playtest exactly as it sees a learner.
    _append(events, "question", {"text": message, "char_count": len(message)})
    _append(events, "patient_reply", {
        "text": reply,
        "matched_topics": [t for t, _ in instrumentation.topic_reasons(message)],
    })
    if early:
        _append(events, "early_diagnosis", {"text": message})

    return _respond(case, engine, events)


def _order(case_id: UUID, version_id: UUID, kind: str):
    """An examination or an investigation — the same shape, two master lists."""
    case, engine, events, error = _request_context(case_id, version_id)
    if error:
        return error

    master = MASTER_EXAMINATIONS if kind == "examination" else MASTER_INVESTIGATIONS
    content_key = "examination" if kind == "examination" else "investigations"
    value_key = "finding" if kind == "examination" else "result"

    key = str(_body().get("key", ""))
    if key not in master:
        return jsonify({"error": f"Unknown {kind}."}), 400
    if _has_diagnosis(events):
        return jsonify({"error": "A diagnosis has been given. Reset to start again."}), 409

    specific = case.get(content_key) or {}
    was_case_specific = key in specific and value_key in (specific[key] or {})
    value = (specific[key][value_key] if was_case_specific
             else master[key]["normal_result"])

    _append(events, kind, {
        "key": key, "label": master[key]["label"], value_key: value,
        "was_case_specific": was_case_specific,
    })
    return _respond(case, engine, events)


@playtest_bp.post("/<uuid:case_id>/versions/<uuid:version_id>/playtest/examine")
@require_reviewer
def examine(case_id: UUID, version_id: UUID):
    return _order(case_id, version_id, "examination")


@playtest_bp.post("/<uuid:case_id>/versions/<uuid:version_id>/playtest/investigate")
@require_reviewer
def investigate(case_id: UUID, version_id: UUID):
    return _order(case_id, version_id, "investigation")


@playtest_bp.post("/<uuid:case_id>/versions/<uuid:version_id>/playtest/diagnose")
@require_reviewer
def diagnose(case_id: UUID, version_id: UUID):
    """Give a diagnosis. The panel then shows the verdict and the C1 rule."""
    case, engine, events, error = _request_context(case_id, version_id)
    if error:
        return error

    text = str(_body().get("text", "")).strip()
    if not text:
        return jsonify({"error": "Type a diagnosis first."}), 400
    if len(text) > MAX_TEXT:
        return jsonify({"error": "That diagnosis is too long."}), 400
    if _has_diagnosis(events):
        return jsonify({"error": "A diagnosis has already been given. Reset to "
                                 "start again."}), 409

    _append(events, "diagnosis", {"text": text})
    return _respond(case, engine, events)
