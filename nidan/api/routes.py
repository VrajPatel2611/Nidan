"""
HTTP routes.

The web layer: parses requests, calls the domain, renders responses. It holds no
business logic of its own — anything that decides something belongs in
nidan.domain (ADR-0009).

**Session state lives in PostgreSQL as an append-only event log** (T-013,
ADR-0003). These handlers hold nothing between requests: each one replays the
log, acts, appends what happened, and returns. The consequence is that a
restart loses nothing and the app runs on as many workers as you like — the
blocker `TECH_SPEC` recorded as B1.

The browser cookie holds three things and no state: a visitor id, the current
session id, and the current case id. Everything else is derived.

NOTE (BUILD_PLAN T-030): these server-rendered routes are the prototype. They are
replaced by a JSON API under /v1 once the Next.js client exists (ADR-0006). The
admin console keeps server rendering.
"""

import uuid

from flask import (
    Blueprint,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from nidan.api import trial
from nidan.domain.assessment.bias import detect_all_biases
from nidan.domain.assessment.clinical import evaluate_clinical
from nidan.domain.assessment.engine import assess
from nidan.domain.assessment.topics import extract_topics
from nidan.domain.content.cases import (
    CASE_SLUGS,
    MASTER_EXAMINATIONS,
    MASTER_INVESTIGATIONS,
    get_all_cases,
    get_case,
)
from nidan.domain.feedback_view import build_feedback_view
from nidan.domain.session import (
    conversation_from,
    mentions_early_diagnosis,
    replay,
)
from nidan.infra.db.repositories import ServiceActor, repo_scope
from nidan.infra.db.repositories.anonymous import anonymous_scope
from nidan.infra.feedback import generate_feedback_with_source
from nidan.infra.llm.gateway import call_llm
from nidan.infra.storage import save_session_file

bp = Blueprint("web", __name__)


# ── Menus, grouped once at import ─────────────────────────────────────
# Insertion order (Python 3.7+) preserves the group order declared in
# MASTER_INVESTIGATIONS / MASTER_EXAMINATIONS.

def _group_by(master: dict) -> dict:
    grouped: dict = {}
    for key, item in master.items():
        grouped.setdefault(item["group"], {})[key] = item
    return grouped


_GROUPED_INVESTIGATIONS = _group_by(MASTER_INVESTIGATIONS)
_GROUPED_EXAMINATIONS = _group_by(MASTER_EXAMINATIONS)


# ── Session plumbing ──────────────────────────────────────────────────

def _visitor_id() -> str:
    """
    A stable id for this browser, in the `anonymous_id` cookie.

    Every consultation in the prototype is an anonymous one. That is not a
    workaround: `PRD` FR-2 makes the first case a trial anyone can take without
    an account, and T-015 added the step that claims it into a real account at
    signup.

    It reads the same cookie the `/v1` trial endpoint sets, so a consultation
    taken here is claimable in exactly the same way. It does **not** enforce
    one-trial-per-browser — that limit belongs to `POST /v1/trial/sessions`,
    the contract a real client uses. These routes are a development surface
    with a deletion date (T-030), and the limit protects revenue rather than
    data; applying it here would cost a cookie-clear per case while authoring
    content and buy nothing.
    """
    existing = trial.visitor_id()
    if existing:
        return existing

    # New visitor. The cookie is attached on the way out, once there is a
    # response to attach it to.
    issued = getattr(g, "_issued_visitor_id", None)
    if issued is None:
        issued = trial.new_visitor_id()
        g._issued_visitor_id = issued
    return issued


@bp.after_request
def _persist_visitor_cookie(response):
    """Set the trial cookie for a visitor who arrived without one."""
    issued = getattr(g, "_issued_visitor_id", None)
    if issued is not None:
        trial.set_trial_cookie(response, issued)
    return response


def _scope():
    """The database, as this visitor. The only way these handlers reach it."""
    return anonymous_scope(_visitor_id())


def _current_session_id() -> uuid.UUID | None:
    raw = session.get("session_id")
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        # A tampered or stale cookie. Treated as "no session" rather than a
        # 500: the learner gets the ordinary "start a case" path.
        return None


def _case_version_id(case_id: str) -> uuid.UUID | None:
    """
    The `case_versions` row this consultation belongs to.

    Transitional. The prototype runs its cases from `domain/content/cases.py`,
    but a `sessions` row needs a real `case_version_id`, and migration 019
    seeded all five as drafts pending clinical review (T-023). Until they are
    published there is no published version to point at, so this resolves one
    through the single method allowed to see unpublished cases — which returns
    an id and nothing else, and demands a reason for the bypass.
    """
    slug = CASE_SLUGS.get(case_id)
    if slug is None:
        return None
    with repo_scope(ServiceActor(
        "resolving the prototype's case_versions row; the seeded cases are "
        "drafts pending clinical review (T-023), so no published version exists"
    )) as db:
        return db.cases.prototype_version_id(slug)


def _start_consultation(case_id: str, *, confidence: int | None = None):
    """Create the session row and remember it in the cookie. Returns its id."""
    case_version_id = _case_version_id(case_id)
    if case_version_id is None:
        return None

    with _scope() as db:
        row = db.sessions.create(case_version_id, confidence_pre=confidence)

    session["session_id"] = str(row["id"])
    session["case_id"] = case_id
    return row["id"]


def _load(db, session_id: uuid.UUID, case_id: str):
    """
    Replay a session from its log. Returns (session_state, events) or (None, None).

    The one place state is reconstructed, so every handler sees the same thing
    and none of them can accidentally work from a partial view.
    """
    row = db.sessions.get(session_id)
    if row is None:
        return None, None
    events = db.events.all_for(session_id)
    state = replay(events, case_id=case_id,
                   started_at=row["started_at"].isoformat())
    return state, events


def _confidence(raw: str) -> int | None:
    """The pre-case confidence rating, 1-5, or None if not answered."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= 5 else None


# ── Pages ─────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    """Home page — case selection."""
    cases = get_all_cases()
    return render_template("index.html", cases=cases)


@bp.route("/pre_case/<case_id>", methods=["GET"])
def pre_case_get(case_id):
    """Pre-consultation questionnaire page."""
    case = get_case(case_id)
    if not case:
        return redirect(url_for(".index"))
    return render_template("pre_case.html", case=case)


@bp.route("/pre_case/<case_id>", methods=["POST"])
def pre_case_post(case_id):
    """Save pre-case form data, then redirect into the consultation."""
    case = get_case(case_id)
    if not case:
        return redirect(url_for(".index"))

    # participant_id and year_of_study are pilot-research fields consumed only
    # by the session JSON export. They have no column because they are not
    # product data — the profile owns year_of_training once accounts exist
    # (T-014). The signed cookie is the right size for them.
    session["pre_case_data"] = {
        "participant_id": request.form.get("participant_id", "").strip(),
        "year_of_study":  request.form.get("year_of_study", ""),
        "confidence":     request.form.get("confidence", ""),
    }

    if _start_consultation(
            case_id, confidence=_confidence(request.form.get("confidence"))) is None:
        return redirect(url_for(".index"))

    return render_template("chat.html", case=case,
                           grouped_investigations=_GROUPED_INVESTIGATIONS,
                           grouped_examinations=_GROUPED_EXAMINATIONS)


@bp.route("/start/<case_id>")
def start_case(case_id):
    """
    Direct start (bypasses pre-case form).
    Used by the 'Try this case again' button on the feedback page.
    """
    case = get_case(case_id)
    if not case:
        return "Case not found.", 404

    session["pre_case_data"] = {}
    if _start_consultation(case_id) is None:
        return "Case not found.", 404

    return render_template("chat.html", case=case,
                           grouped_investigations=_GROUPED_INVESTIGATIONS,
                           grouped_examinations=_GROUPED_EXAMINATIONS)


# ── The consultation ──────────────────────────────────────────────────

@bp.route("/chat", methods=["POST"])
def chat():
    """
    Receives a user question and returns the virtual patient's reply.

    Body:   {"message": "Does the pain go to your arm?"}
    Returns: {"response": "No, just in my chest.", "question_count": 3}
    """
    session_id = _current_session_id()
    case_id = session.get("case_id")
    if session_id is None or not case_id:
        return jsonify({"error": "No active session. Please go back and select a case."}), 400

    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message."}), 400

    # Read in one transaction and close it: the model call below takes seconds,
    # and a pooled connection held across it is a connection nobody else can
    # use. Nothing is written yet, so there is nothing to hold open for.
    with _scope() as db:
        state, events = _load(db, session_id, case_id)
        if state is None:
            return jsonify({"error": "No active session."}), 400
        conversation = conversation_from(events)

    case = get_case(case_id)

    # Stored roles are "user"/"model"; the API expects "user"/"assistant".
    messages = [
        {"role": "user" if m["role"] == "user" else "assistant",
         "content": m["content"]}
        for m in conversation
    ]
    messages.append({"role": "user", "content": user_message})

    try:
        patient_reply = call_llm(
            messages=messages,
            system_instruction=case["system_prompt"],
            max_tokens=200,
            temperature=0.7,
        )
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "rate limit" in err_str.lower():
            msg = ("The patient is taking a moment — please wait a few seconds "
                   "and try again.")
        else:
            msg = "The patient could not respond right now. Please try again."
        return jsonify({"error": msg}), 500

    # The question and the reply are appended together, in one transaction.
    #
    # Appending the question first would be the more orthodox event sourcing,
    # but a failed model call would then leave a question with no answer: the
    # learner sees an error, retypes, and the log holds the question twice.
    # question_count feeds premature closure (P1: q < q_min), so an inflated
    # count suppresses a flag the learner should have seen. Losing a question
    # nobody got an answer to is the cheaper mistake.
    with _scope() as db:
        db.events.append(session_id, "question", {
            "text": user_message,
            "char_count": len(user_message),
        })
        db.events.append(session_id, "patient_reply", {
            "text": patient_reply,
            # What the system understood, at the time — DATA_MODEL §8.2. T-016
            # compares a recomputation against this to detect drift, so it is
            # recorded here rather than re-derived during replay.
            "matched_topics": extract_topics(user_message),
        })
        if state["early_diagnosis"] is None and mentions_early_diagnosis(user_message):
            db.events.append(session_id, "early_diagnosis", {"text": user_message})

        db.sessions.touch(session_id)
        state, _ = _load(db, session_id, case_id)

    return jsonify({
        "response": patient_reply,
        "question_count": state["question_count"],
    })


@bp.route("/examine", methods=["POST"])
def examine():
    """
    Performs an examination from the universal MASTER_EXAMINATIONS list.

    If the system is one of this case's KEY/RELEVANT examinations, returns
    the case-specific finding from case["examination"].
    Otherwise returns the generic NORMAL finding from MASTER_EXAMINATIONS —
    so students cannot infer the diagnosis from which systems are available.

    Body:   {"system": "vitals"}
    Returns: {"label": "Vital Signs", "finding": "HR 76 ..."}
    """
    session_id = _current_session_id()
    case_id = session.get("case_id")
    if session_id is None or not case_id:
        return jsonify({"error": "No active session."}), 400

    data = request.get_json(silent=True) or {}
    system_key = data.get("system", "")

    # Validate against the master list (not the case-specific list)
    if system_key not in MASTER_EXAMINATIONS:
        return jsonify({"error": "Unknown examination."}), 400

    case = get_case(case_id)
    case_exam = case.get("examination", {})

    # Case-specific finding if relevant; normal finding otherwise
    was_case_specific = system_key in case_exam
    finding = (case_exam[system_key]["finding"] if was_case_specific
               else MASTER_EXAMINATIONS[system_key]["normal_result"])

    # Always use the master label for consistency across cases
    label = MASTER_EXAMINATIONS[system_key]["label"]

    with _scope() as db:
        if db.sessions.get(session_id) is None:
            return jsonify({"error": "No active session."}), 400
        db.events.append(session_id, "examination", {
            "key": system_key, "label": label, "finding": finding,
            "was_case_specific": was_case_specific,
        })
        db.sessions.touch(session_id)

    return jsonify({"label": label, "finding": finding})


@bp.route("/investigate", methods=["POST"])
def investigate():
    """
    Orders an investigation from the universal MASTER_INVESTIGATIONS list.

    If the test is one of this case's KEY/RELEVANT investigations, returns
    the case-specific (often abnormal) result from case["investigations"].
    Otherwise returns the generic NORMAL result from MASTER_INVESTIGATIONS —
    so students cannot infer the diagnosis from which tests are available.

    Body:   {"test": "ecg"}
    Returns: {"label": "ECG (12-lead)", "result": "Normal sinus rhythm ..."}
    """
    session_id = _current_session_id()
    case_id = session.get("case_id")
    if session_id is None or not case_id:
        return jsonify({"error": "No active session."}), 400

    data = request.get_json(silent=True) or {}
    test_key = data.get("test", "")

    # Validate against master list (not the case-specific list)
    if test_key not in MASTER_INVESTIGATIONS:
        return jsonify({"error": "Unknown investigation."}), 400

    case = get_case(case_id)
    case_inv = case.get("investigations", {})

    # Case-specific result if relevant; normal result otherwise
    was_case_specific = test_key in case_inv
    result = (case_inv[test_key]["result"] if was_case_specific
              else MASTER_INVESTIGATIONS[test_key]["normal_result"])

    # Always use the master label for consistency across cases
    label = MASTER_INVESTIGATIONS[test_key]["label"]

    with _scope() as db:
        if db.sessions.get(session_id) is None:
            return jsonify({"error": "No active session."}), 400
        db.events.append(session_id, "investigation", {
            "key": test_key, "label": label, "result": result,
            "was_case_specific": was_case_specific,
        })
        db.sessions.touch(session_id)

    return jsonify({"label": label, "result": result})


@bp.route("/conclude", methods=["POST"])
def conclude():
    """
    Receives the student's final diagnosis.

    Appends the diagnosis event, closes the session, runs the deterministic
    assessment, and stores the generated prose. It stores no scores: the
    feedback screen recomputes every one of them from the log (ADR-0003).

    Body:    {"diagnosis": "Myocardial infarction"}
    Returns: 200 OK (body ignored — JS redirects to /feedback)
    """
    session_id = _current_session_id()
    case_id = session.get("case_id")
    if session_id is None or not case_id:
        return jsonify({"error": "No active session."}), 400

    data = request.get_json(silent=True) or {}
    diagnosis = data.get("diagnosis", "").strip()
    if not diagnosis:
        return jsonify({"error": "No diagnosis provided."}), 400

    case = get_case(case_id)

    with _scope() as db:
        if db.sessions.get(session_id) is None:
            return jsonify({"error": "No active session."}), 400
        # complete() returns False if a diagnosis was already recorded, which
        # makes a double-submit idempotent at the database rather than in a
        # check the second request could race past.
        first_submission = db.sessions.complete(session_id)
        if first_submission:
            db.events.append(session_id, "diagnosis", {"text": diagnosis})
        state, _ = _load(db, session_id, case_id)

    if not first_submission:
        return jsonify({"status": "ok"})

    # Assessed from the event log, under the engine version in force, and
    # stored with its id (T-016). The feedback screen still recomputes
    # everything it renders — this row is the durable analytical record, for
    # progress trends, research export and threshold calibration.
    with _scope() as db:
        engine = db.engines.current()
        events = db.events.all_for(session_id)

    result = assess(events, case, engine)
    feedback = generate_feedback_with_source(
        result.bias_detail, result.clinical_eval, state, case)

    with _scope() as db:
        if engine is not None:
            db.results.save(session_id, result)
        db.feedback.save(session_id, feedback.lines, generator=feedback.generator)

    bias_results, clinical_eval = result.bias_detail, result.clinical_eval

    # The research JSON export, unchanged. It is the pilot's artefact and the
    # input to analyze_sessions.py; the event log does not replace it yet.
    save_session_file(
        str(session_id), case_id, case, state,
        session.get("pre_case_data", {}),
        bias_results, clinical_eval, feedback.lines,
    )

    return jsonify({"status": "ok"})


@bp.route("/feedback")
def feedback():
    """
    Renders the feedback page.

    Every number on it is recomputed here from the event log. Only the prose is
    read from storage, because only the prose cannot be recomputed — a model
    wrote it (ADR-0005).
    """
    session_id = _current_session_id()
    case_id = session.get("case_id")
    if session_id is None or not case_id:
        return redirect(url_for(".index"))

    case = get_case(case_id)
    if not case:
        return redirect(url_for(".index"))

    with _scope() as db:
        state, _ = _load(db, session_id, case_id)
        if state is None or state["diagnosis_submitted"] is None:
            return redirect(url_for(".index"))
        stored = db.feedback.latest(session_id)
        db.events.append(session_id, "feedback_viewed", {})

    view = build_feedback_view(
        state, case, case_id=case_id,
        bias_results=detect_all_biases(state, case),
        clinical_eval=evaluate_clinical(state, case),
        feedback_lines=stored["lines"] if stored else [],
    )
    return render_template("feedback.html", data=view)


@bp.route("/save_session", methods=["POST"])
def save_session_route():
    """Thin wrapper — sessions are saved automatically inside /conclude."""
    return jsonify({"status": "Sessions are saved automatically on /conclude."})
