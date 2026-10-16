"""
Case editor routes (BUILD_PLAN T-021, UX_SPEC §12.4).

Sectioned form for editing clinical cases with live invariant validation,
save-blocking on C-4 keyword overlaps, and immutable published version handling.
"""

from __future__ import annotations

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


def _parse_form_content(req) -> dict:
    """Extract content payload from JSON or form submit."""
    if req.is_json:
        return req.get_json()

    # Form payload parse helper
    raw = req.form.get("content_json")
    if raw:
        return json.loads(raw)

    # Fallback to form data extraction
    content = {
        "title": req.form.get("title", "").strip(),
        "patient": {
            "name": req.form.get("patient_name", "").strip(),
            "age": int(req.form.get("patient_age", 40)),
            "sex": req.form.get("patient_sex", "male"),
            "presenting_complaint": req.form.get("presenting_complaint", "").strip(),
            "introductory_text": req.form.get("introductory_text", "").strip(),
            "opening_line": req.form.get("opening_line", "").strip(),
        },
        "correct_diagnosis": req.form.get("correct_diagnosis", "").strip(),
        "accepted_diagnoses": [s.strip() for s in req.form.get("accepted_diagnoses", "").split(",") if s.strip()],
        "partial_diagnoses": [s.strip() for s in req.form.get("partial_diagnoses", "").split(",") if s.strip()],
        "anchor_topic": req.form.get("anchor_topic", "").strip(),
        "anchor_keywords": [s.strip() for s in req.form.get("anchor_keywords", "").split(",") if s.strip()],
        "alternative_hypothesis_keywords": [s.strip() for s in req.form.get("alternative_keywords", "").split(",") if s.strip()],
        "minimum_questions": int(req.form.get("minimum_questions", 7)),
        "required_topics": req.form.getlist("required_topics"),
        "contradictory_clues": [
            [tag.strip() for tag in clue_set.split(",") if tag.strip()]
            for clue_set in req.form.getlist("clue_sets") if clue_set.strip()
        ],
        "examination": {},
        "investigations": {},
        "system_prompt": req.form.get("system_prompt", "").strip(),
    }
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
            content = _parse_form_content(request)
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
    master_lists = _get_master_lists()
    content = _parse_form_content(request)
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
            "introductory_text": "A 45-year-old male presents to clinic...",
            "opening_line": "Hello doctor, I've had this pain for a few days.",
        },
        "correct_diagnosis": "Angina",
        "accepted_diagnoses": ["Angina", "Ischemic heart disease"],
        "partial_diagnoses": ["Coronary artery disease"],
        "anchor_topic": "cardiac",
        "anchor_keywords": ["chest pain", "angina"],
        "alternative_hypothesis_keywords": ["reflux", "gerd"],
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
            "ecg": {"category": "key", "result": "Normal"}
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
