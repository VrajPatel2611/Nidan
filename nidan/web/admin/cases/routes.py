"""
Case editor routes (BUILD_PLAN T-021, UX_SPEC §12.4).

Sectioned form for editing clinical cases with live invariant validation,
save-blocking on C-4 keyword overlaps, and immutable published version handling.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from uuid import UUID

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from nidan.api.auth import current_admin, require_admin
from nidan.domain.assessment.topics import TOPIC_KEYWORDS
from nidan.domain.content.cases import MASTER_EXAMINATIONS, MASTER_INVESTIGATIONS
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.cases import (
    ConcurrentEdit,
    ContentInvariantViolation,
    c4_collisions,
)

cases_bp = Blueprint("admin_cases_editor", __name__, url_prefix="/admin/cases")


def _get_master_lists() -> dict:
    """Fetch master lists for examinations, investigations, and topic lexicon."""
    exams = [
        {"key": k, "label": v["label"], "category": v.get("group", "")}
        for k, v in MASTER_EXAMINATIONS.items()
    ]
    tests = [
        {
            "key": k,
            "label": v["label"],
            "category": v.get("group", ""),
            "normal_result": v.get("normal_result", ""),
            "reference_range": v.get("reference_range", ""),
        }
        for k, v in MASTER_INVESTIGATIONS.items()
    ]
    topics = [
        {
            "topic_key": k,
            "display_name": k.replace("_", " ").title(),
            "category": "History",
        }
        for k in TOPIC_KEYWORDS
    ]

    return {
        "examinations": exams,
        "investigations": tests,
        "topics": topics,
    }


def _validate_invariants(content: dict, master_lists: dict) -> dict:
    """Validate invariants C-1 through C-7 for live feedback."""
    collisions = c4_collisions(content)
    is_c4_valid = len(collisions) == 0

    exam_keys = {e["key"] for e in master_lists["examinations"]}
    test_keys = {t["key"] for t in master_lists["investigations"]}
    topic_keys = {tp["topic_key"] for tp in master_lists["topics"]}

    content_exams = set(content.get("examination", {}).keys())
    content_tests = set(content.get("investigations", {}).keys())
    content_topics = set(content.get("required_topics", []))

    c1_invalid = sorted(content_exams - exam_keys)
    c2_invalid = sorted(content_tests - test_keys)
    c3_invalid = sorted(content_topics - topic_keys)

    accepted_diag = content.get("accepted_diagnoses", [])
    c5_valid = len(accepted_diag) >= 2

    clues = content.get("contradictory_clues", [])
    c6_valid = len(clues) >= 4

    key_tests = [
        k for k, v in content.get("investigations", {}).items()
        if isinstance(v, dict) and v.get("category") == "key"
    ]
    c7_valid = len(key_tests) >= 1

    warnings = []
    if c1_invalid:
        warnings.append(f"C-1 warning: unknown examination keys {c1_invalid}")
    if c2_invalid:
        warnings.append(f"C-2 warning: unknown investigation keys {c2_invalid}")
    if c3_invalid:
        warnings.append(f"C-3 warning: unknown required topics {c3_invalid}")

    publish_blocked_reasons = []
    if not is_c4_valid:
        publish_blocked_reasons.append("C-4: anchor keywords overlap contradictory clues")
    if not c5_valid:
        publish_blocked_reasons.append("C-5: accepted diagnoses count must be ≥ 2")
    if not c6_valid:
        publish_blocked_reasons.append("C-6: contradictory clues set count must be ≥ 4")
    if not c7_valid:
        publish_blocked_reasons.append("C-7: must include at least 1 key investigation")

    return {
        "c4_collisions": collisions,
        "is_c4_valid": is_c4_valid,
        "c5_valid": c5_valid,
        "c6_valid": c6_valid,
        "c7_valid": c7_valid,
        "warnings": warnings,
        "publish_blocked_reasons": publish_blocked_reasons,
        "can_save": is_c4_valid,
        "can_publish": is_c4_valid and c5_valid and c6_valid and c7_valid,
    }


def _csv(value: str) -> list[str]:
    return [s.strip() for s in value.split(",") if s.strip()]


def _set(target: dict, key: str, value) -> None:
    """Write `value`, unless it is empty and the key was never there."""
    if value or key in target:
        target[key] = value


def _parse_form_content(req, existing: dict | None = None) -> dict:
    """
    The content to save: JSON as posted, or the form merged over `existing`.

    **Merged, not rebuilt.** The form renders only part of a case -- it has no
    control for an examination's `key` flag, nor for investigation categories
    other than "key" -- so building the content from the form alone silently
    dropped everything it does not show. Each field below is written only if
    the form posted it; anything else in the stored content is kept as it was.
    """
    if req.is_json:
        payload = dict(req.get_json())
        payload.pop("expected_updated_at", None)   # a save token, not content
        return payload

    raw = req.form.get("content_json")
    if raw:
        return json.loads(raw)

    form = req.form
    content = copy.deepcopy(dict(existing or {}))

    if "title" in form:
        _set(content, "title", form["title"].strip())

    patient = dict(content.get("patient") or {})
    # `intro` is the stored key; the form field kept its older name.
    for field, key in (("patient_name", "name"), ("patient_sex", "sex"),
                       ("presenting_complaint", "presenting_complaint"),
                       ("introductory_text", "intro"),
                       ("opening_line", "opening_line")):
        if field in form:
            _set(patient, key, form[field].strip())
    if form.get("patient_age", "").strip():
        patient["age"] = int(form["patient_age"])
    if patient:
        content["patient"] = patient

    for field in ("correct_diagnosis", "anchor_topic"):
        if field in form:
            _set(content, field, form[field].strip())
    for field, key in (("accepted_diagnoses", "accepted_diagnoses"),
                       ("partial_diagnoses", "partial_diagnoses"),
                       ("anchor_keywords", "anchor_keywords"),
                       ("alternative_keywords", "alternative_topics")):
        if field in form:
            _set(content, key, _csv(form[field]))
    # The name an earlier version of this form saved alternative_topics under.
    content.pop("alternative_hypothesis_keywords", None)

    if "system_prompt" in form:
        # Browsers submit textarea line breaks as CRLF.
        _set(content, "system_prompt", form["system_prompt"].replace("\r\n", "\n"))

    # The history section always posts minimum_questions; when it is present,
    # an empty required_topics list means every box was unticked.
    if "minimum_questions" in form:
        content["minimum_questions"] = int(form["minimum_questions"])
        ticked = form.getlist("required_topics")
        kept = [t for t in content.get("required_topics", []) if t in ticked]
        content["required_topics"] = kept + [t for t in ticked if t not in kept]

    if "clue_sets" in form:
        content["contradictory_clues"] = [
            _csv(clue_set) for clue_set in form.getlist("clue_sets") if _csv(clue_set)
        ]

    exams = dict(content.get("examination") or {})
    for key, master in MASTER_EXAMINATIONS.items():
        field = f"exam_{key}"
        if field not in form:
            continue
        finding = form[field].strip()
        if finding:
            entry = dict(exams.get(key) or {"key": False, "label": master["label"]})
            entry["finding"] = finding
            exams[key] = entry
        else:
            exams.pop(key, None)   # blank means the normal finding
    _set(content, "examination", exams)

    tests = dict(content.get("investigations") or {})
    for key, master in MASTER_INVESTIGATIONS.items():
        field = f"test_result_{key}"
        if field not in form:
            continue
        result = form[field].strip()
        is_key = form.get(f"test_key_{key}") == "key"
        if not result and not is_key:
            tests.pop(key, None)
            continue
        previous = tests.get(key) or {}
        entry = dict(previous or {"label": master["label"]})
        entry["result"] = result or master.get("normal_result", "")
        # The form can promote to "key" and demote from it; "low_value" and
        # "reasonable" have no control, so they are kept as they were.
        if is_key:
            entry["category"] = "key"
        elif previous.get("category") not in (None, "key"):
            entry["category"] = previous["category"]
        else:
            entry["category"] = "reasonable"
        tests[key] = entry
    _set(content, "investigations", tests)

    return content


@cases_bp.get("/<uuid:case_id>/versions/<uuid:version_id>")
@require_admin
def editor(case_id: UUID, version_id: UUID):
    """Case editor view (A-03)."""
    with repo_scope(current_admin()) as db:
        case_ver = db.cases.for_editing(version_id)
        if case_ver is None:
            return jsonify({"error": {"code": "not_found", "message": "Not found."}}), 404

        all_versions = db.cases.versions(case_id)
        profile = db.profiles.get()

    master_lists = _get_master_lists()

    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"
    content = case_ver["content"] or {}
    validation = _validate_invariants(content, master_lists)

    return render_template(
        "admin/cases/editor.html",
        active_nav="cases",
        active_section="case_editor",
        user_email=user_email,
        case=case_ver,
        content=content,
        all_versions=all_versions,
        master_lists=master_lists,
        validation=validation,
        updated_at=case_ver["updated_at"].isoformat() if case_ver.get("updated_at") else "",
    )


@cases_bp.post("/<uuid:case_id>/versions/<uuid:version_id>/save")
@require_admin
def save(case_id: UUID, version_id: UUID):
    """Save draft or create new draft from published version."""
    with repo_scope(current_admin()) as db:
        existing = db.cases.for_editing(version_id)
        if existing is None:
            return jsonify({"error": {"code": "not_found", "message": "Not found."}}), 404

        try:
            content = _parse_form_content(request, existing.get("content"))
        except Exception as err:
            return jsonify({"error": "invalid_payload", "message": str(err)}), 400

        # C-4 Validation check
        collisions = c4_collisions(content)
        if collisions:
            return jsonify({
                "error": "c4_violation",
                "message": "C-4 violation: anchor keywords overlap contradictory clues",
                "collisions": collisions,
            }), 400

        status = existing["status"]

        if status == "published":
            # Editing published version creates new draft vN+1
            new_id = db.cases.create_draft(case_id, content)
            db.audit.record(
                "case_version.draft_created",
                entity_type="case_version",
                entity_id=new_id,
                reason=f"Created draft v{existing['version'] + 1} from published v{existing['version']}",
                metadata={"source_version_id": str(version_id)},
            )
            redirect_url = url_for("admin_cases_editor.editor", case_id=case_id, version_id=new_id)
            if request.is_json:
                return jsonify({"status": "created_draft", "new_version_id": str(new_id), "redirect": redirect_url}), 200
            return redirect(redirect_url)

        else:
            # Editing draft
            expected_iso = request.form.get("expected_updated_at") or (request.json.get("expected_updated_at") if request.is_json else None)
            if not expected_iso and existing.get("updated_at"):
                expected_iso = existing["updated_at"].isoformat()

            try:
                expected_dt = datetime.fromisoformat(expected_iso)
            except (TypeError, ValueError):
                expected_dt = existing["updated_at"]

            try:
                new_updated_at = db.cases.update_draft(version_id, content, expected_updated_at=expected_dt)
            except ConcurrentEdit as exc:
                return jsonify({"error": "concurrent_edit", "message": str(exc)}), 409
            except ContentInvariantViolation as exc:
                return jsonify({"error": "c4_violation", "message": str(exc)}), 400

            db.audit.record(
                "case_version.updated",
                entity_type="case_version",
                entity_id=version_id,
                reason="Saved draft edits",
                metadata={"version": existing["version"]},
            )

            if request.is_json:
                return jsonify({"status": "saved", "updated_at": new_updated_at.isoformat()}), 200
            return redirect(url_for("admin_cases_editor.editor", case_id=case_id, version_id=version_id))


@cases_bp.post("/<uuid:case_id>/versions/<uuid:version_id>/validate")
@require_admin
def validate(case_id: UUID, version_id: UUID):
    """HTMX endpoint to validate invariants live as user types."""
    with repo_scope(current_admin()) as db:
        existing = db.cases.for_editing(version_id)
    if existing is None:
        return jsonify({"error": {"code": "not_found", "message": "Not found."}}), 404

    master_lists = _get_master_lists()
    try:
        content = _parse_form_content(request, existing.get("content"))
    except (ValueError, TypeError):
        # Mid-edit input such as an empty age; the next keystroke revalidates.
        return "", 204
    validation = _validate_invariants(content, master_lists)

    return render_template(
        "admin/cases/_validation.html",
        validation=validation,
        case_id=case_id,
        version_id=version_id,
    )


@cases_bp.post("/new")
@require_admin
def create_new_case():
    """Create a new case and initial draft version."""
    slug = request.form.get("slug", "").strip()
    specialty = request.form.get("specialty", "General Medicine").strip()

    if not slug:
        slug = f"case-{int(datetime.now().timestamp())}"

    initial_content = {
        "title": request.form.get("title", "New Clinical Case").strip(),
        "patient": {
            "name": "John Doe",
            "age": 45,
            "sex": "male",
            "presenting_complaint": "Chest pain",
            "intro": "A 45-year-old male presents to clinic...",
            "opening_line": "Hello doctor, I've had this pain for a few days.",
        },
        "correct_diagnosis": "Angina",
        "accepted_diagnoses": ["Angina", "Ischemic heart disease"],
        "partial_diagnoses": ["Coronary artery disease"],
        "anchor_topic": "cardiac",
        "anchor_keywords": ["chest pain", "angina"],
        "alternative_topics": ["reflux", "gerd"],
        "minimum_questions": 7,
        "required_topics": ["pain_character", "aggravating_factors"],
        "contradictory_clues": [
            ["burning", "acid"],
            ["relief with antacids"],
            ["no radiation", "pleuritic"],
            ["normal ecg"],
        ],
        "examination": {},
        "investigations": {
            "ecg": {"label": "ECG (12-lead)", "category": "key", "result": "Normal"}
        },
        "system_prompt": "You are playing a virtual patient...",
    }

    with repo_scope(current_admin()) as db:
        new_case_id = db.cases.create_case(slug=slug, specialty=specialty)
        new_version_id = db.cases.create_draft(new_case_id, initial_content)

        db.audit.record(
            "case.created",
            entity_type="case",
            entity_id=new_case_id,
            reason=f"Created new case '{slug}'",
            metadata={"initial_version_id": str(new_version_id)},
        )

    return redirect(url_for("admin_cases_editor.editor", case_id=new_case_id, version_id=new_version_id))
