"""
Clinical review (BUILD_PLAN T-023, UX_SPEC §12.6).

The review queue, assigning a version to a reviewer, recording a structured
judgement, and publishing a version once it has an approving one.

**Who runs as what.** Everything a reviewer does — reading the queue, opening a
draft, recording a review — runs as `current_reviewer()`, administrators
included: reviewing is reviewing, and the smaller privilege is the right one to
hold while doing it. Only assigning and publishing use `current_admin()`.

**The rubric rules are checked twice.** Here, so a clinician gets a sentence
naming what is short before anything is written; and in
`ReviewRepository.record()`, which is what actually holds if this check is
bypassed or wrong. The form also disables Approve, which is the first of the
three and the only one a reviewer should normally meet.

**Publication is checked twice too.** `has_approval()` here gives a readable
409; migration 007's `enforce_clinical_approval` trigger is the guarantee.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for

from nidan.api.auth import (
    current_admin,
    current_reviewer,
    error,
    require_admin,
    require_reviewer,
)
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.cases import AlreadyPublished, PublicationBlocked
from nidan.infra.db.repositories.reviews import (
    APPROVAL_FLOOR,
    RUBRIC,
    RubricViolation,
)

reviews_bp = Blueprint("admin_reviews", __name__, url_prefix="/admin/reviews")

# Labels for the four dimensions, in RUBRIC's order (`UX_SPEC` §12.6).
DIMENSION_LABELS: dict[str, str] = {
    "clinical_plausibility": "Clinical plausibility",
    "internal_consistency": "Internal consistency",
    "trap_validity": "Trap validity",
    "solvability": "Solvability from the information given",
}
assert tuple(DIMENSION_LABELS) == RUBRIC, "the form must ask exactly the rubric"

DECISION_LABELS: dict[str, str] = {
    "approved": "Approved",
    "changes_requested": "Changes requested",
    "rejected": "Rejected",
}

TABS: tuple[str, ...] = ("mine", "pending", "completed")

def _not_found():
    return error("not_found", "Not found.", 404)


def _is_admin() -> bool:
    return getattr(g, "platform_role", None) == "admin"


def _ago(when: datetime | None) -> str:
    """'5 hours ago', '2 days ago' — the queue's only timestamp format."""
    if when is None:
        return ""
    seconds = int((datetime.now(UTC) - when).total_seconds())
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = seconds // size
            return f"{n} {unit}{'' if n == 1 else 's'} ago"
    return "just now"


def _reviewer_names() -> dict[UUID, str]:
    """
    `reviewer_id` → display name, for every privileged account.

    `current_reviewer()`, not `current_admin()`: the queue resolves names for
    reviewers as well as administrators, and on a `@require_reviewer` route an
    administrator holds a `ReviewerUser` too. Migration 025 is what permits the
    read; before it this needed a `ServiceActor` with RLS off (handoff V-6).
    """
    with repo_scope(current_reviewer()) as db:
        people = db.reviews.reviewers()
    return {p["id"]: p["display_name"] or f"{p['platform_role']} {str(p['id'])[:8]}"
            for p in people}


def _row(entry: Mapping[str, Any], version: Mapping[str, Any] | None) -> dict[str, Any]:
    """One queue row: the listing entry plus what only the content knows."""
    content = (version or {}).get("content") or {}
    case_id = (version or {}).get("case_id")
    vid = entry["case_version_id"]
    return {
        **dict(entry),
        "diagnosis": content.get("correct_diagnosis") or "—",
        "trap": entry.get("anchor_topic") or content.get("anchor_topic") or "—",
        "ago": _ago(entry.get("assigned_at")),
        "playtest_url": (f"/admin/cases/{case_id}/versions/{vid}/playtest?review=1"
                         if case_id else None),
    }


def pending_count() -> int | None:
    """The sidebar's 'Review (n)': this person's outstanding assignments."""
    if getattr(g, "platform_role", None) not in ("reviewer", "admin"):
        return None
    if "pending_reviews" not in g:      # once per request, not once per render
        with repo_scope(current_reviewer()) as db:
            g.pending_reviews = len(db.reviews.assigned_to_me())
    return g.pending_reviews


@reviews_bp.app_context_processor
def _sidebar_count() -> dict[str, Any]:
    # Only on admin pages, and only once a role guard has run — the learner
    # app and the 404 path never pay for this query.
    if not request.path.startswith("/admin") or not hasattr(g, "platform_role"):
        return {}
    return {"pending_reviews": pending_count()}


# ── The queue ────────────────────────────────────────────────────────

@reviews_bp.get("")
@require_reviewer
def queue():
    """Review queue (A-05): assigned to me · all pending · completed."""
    tab = request.args.get("tab", "mine")
    if tab not in TABS:
        tab = "mine"

    with repo_scope(current_reviewer()) as db:
        mine = db.reviews.assigned_to_me()
        pending = db.reviews.pending()
        completed = db.reviews.completed()
        ids = {r["case_version_id"] for r in (*mine, *pending, *completed)}
        versions = {vid: db.cases.for_review(vid) for vid in ids}
        profile = db.profiles.get()

    names = _reviewer_names()

    assign = None
    if _is_admin():
        with repo_scope(current_admin()) as db:
            bank = db.cases.bank()
        assign = {
            "versions": [
                {"id": c["id"], "label": f"{c['title'] or c['slug']} · v{c['version']} ({c['status']})"}
                for c in sorted(bank, key=lambda c: (c["title"] or c["slug"]))
                if c["status"] == "draft"
            ],
            "reviewers": sorted(names.items(), key=lambda kv: kv[1]),
        }

    completed_rows = []
    for r in completed:
        row = _row(r, versions.get(r["case_version_id"]))
        row.update(
            decision_label=DECISION_LABELS.get(r["decision"], r["decision"]),
            reviewer=names.get(r["reviewer_id"], "a reviewer"),
            reviewed_ago=_ago(r["reviewed_at"]),
            scores=[(DIMENSION_LABELS[d], (r["scores"] or {}).get(d)) for d in RUBRIC],
        )
        completed_rows.append(row)

    return render_template(
        "admin/reviews/queue.html",
        active_nav="cases",
        active_section="review_queue",
        user_email=(profile or {}).get("display_name") or "reviewer@nidan.internal",
        tab=tab,
        mine=[_row(r, versions.get(r["case_version_id"])) for r in mine],
        pending=[_row(r, versions.get(r["case_version_id"])) for r in pending],
        completed=completed_rows,
        assign=assign,
        is_admin=_is_admin(),
        notice=request.args.get("notice"),
    )


# ── Assigning (admin) ────────────────────────────────────────────────

def _uuid(value: str | None) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


@reviews_bp.post("/assign")
@require_admin
def assign():
    """Put a version on a reviewer's list. Every assignment is audited."""
    version_id = _uuid(request.form.get("case_version_id"))
    reviewer_id = _uuid(request.form.get("reviewer_id"))
    if version_id is None or reviewer_id is None:
        return redirect(url_for("admin_reviews.queue", tab="pending",
                                notice="Choose a case version and a reviewer."))

    # The foreign key accepts any profile; only privileged accounts may review.
    names = _reviewer_names()
    if reviewer_id not in names:
        return redirect(url_for("admin_reviews.queue", tab="pending",
                                notice="That account cannot review cases."))

    with repo_scope(current_admin()) as db:
        version = db.cases.for_review(version_id)
        if version is None:
            return _not_found()
        db.reviews.assign(version_id, reviewer_id)
        db.audit.record(
            "case_version.review_assigned",
            entity_type="case_version",
            entity_id=version_id,
            reason=f"Assigned v{version['version']} to {names[reviewer_id]} for review",
            metadata={"reviewer_id": str(reviewer_id)},
            ip_address=request.remote_addr,
        )

    return redirect(url_for("admin_reviews.queue", tab="pending",
                            notice=f"Assigned to {names[reviewer_id]}."))


@reviews_bp.post("/unassign")
@require_admin
def unassign():
    """Take a version off a reviewer's list. Recorded reviews are untouched."""
    version_id = _uuid(request.form.get("case_version_id"))
    reviewer_id = _uuid(request.form.get("reviewer_id"))
    if version_id is None or reviewer_id is None:
        return redirect(url_for("admin_reviews.queue", tab="pending"))

    with repo_scope(current_admin()) as db:
        db.reviews.unassign(version_id, reviewer_id)
        db.audit.record(
            "case_version.review_unassigned",
            entity_type="case_version",
            entity_id=version_id,
            metadata={"reviewer_id": str(reviewer_id)},
            ip_address=request.remote_addr,
        )
    return redirect(url_for("admin_reviews.queue", tab="pending",
                            notice="Assignment removed."))


# ── The review form, shown inside Playtest ───────────────────────────

def form_context(version_id: UUID) -> dict[str, Any]:
    """What `_form.html` needs. Called by Playtest when opened with ?review=1."""
    me = current_reviewer()
    with repo_scope(me) as db:
        reviews = db.reviews.for_version(version_id)
        is_author = db.reviews.is_author(version_id, me.user_id)
        has_approval = db.reviews.has_approval(version_id)
    names = _reviewer_names()
    return {
        "version_id": version_id,
        "dimensions": list(DIMENSION_LABELS.items()),
        "floor": APPROVAL_FLOOR,
        "is_author": is_author,
        "is_admin": _is_admin(),
        "has_approval": has_approval,
        "already_reviewed": any(r["reviewer_id"] == me.user_id for r in reviews),
        "history": [
            {
                "decision": DECISION_LABELS.get(r["decision"], r["decision"]),
                "reviewer": names.get(r["reviewer_id"], "a reviewer"),
                "ago": _ago(r["reviewed_at"]),
                "comments": r["comments"],
                "scores": [(DIMENSION_LABELS[d], (r["scores"] or {}).get(d)) for d in RUBRIC],
            }
            for r in reviews
        ],
    }


def check_rubric(decision: str, scores: Mapping[str, int], comments: str) -> str | None:
    """
    The `UX_SPEC` §12.6 rules, as a sentence, or None.

    Mirrors `ReviewRepository._reject_bad_rubric`, which stays the backstop.
    """
    if decision not in DECISION_LABELS:
        return "Choose Approve, Request changes or Reject."
    missing = [DIMENSION_LABELS[d] for d in RUBRIC if d not in scores]
    if missing:
        return "Score every dimension: " + ", ".join(missing) + " is missing."
    if decision == "approved":
        short = [f"{DIMENSION_LABELS[d]} ({scores[d]})" for d in RUBRIC
                 if scores[d] < APPROVAL_FLOOR]
        if short:
            return (f"A case cannot be approved with any dimension below "
                    f"{APPROVAL_FLOOR}: " + ", ".join(short) + ". Request changes "
                    "or reject instead.")
    if decision in ("changes_requested", "rejected") and not comments:
        return (f"{DECISION_LABELS[decision]} needs a comment, so the author "
                f"knows what to change.")
    return None


@reviews_bp.post("/<uuid:version_id>/record")
@require_reviewer
def record(version_id: UUID):
    """Record one review. JSON in and out, so Playtest keeps its state."""
    body = request.get_json(silent=True) or {}
    decision = str(body.get("decision", ""))
    comments = str(body.get("comments") or "").strip()

    raw = body.get("scores") or {}
    scores: dict[str, int] = {}
    for d in RUBRIC:
        try:
            value = int(raw[d])
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= value <= 5:
            scores[d] = value

    problem = check_rubric(decision, scores, comments)
    if problem:
        return jsonify({"error": problem}), 400

    with repo_scope(current_reviewer()) as db:
        if db.cases.for_review(version_id) is None:
            return _not_found()
        try:
            review_id = db.reviews.record(version_id, decision=decision,
                                          scores=scores, comments=comments or None)
        except RubricViolation as exc:
            return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "recorded", "review_id": str(review_id),
                    "decision": DECISION_LABELS[decision]})


# ── Publishing (admin) ───────────────────────────────────────────────

@reviews_bp.post("/<uuid:version_id>/publish")
@require_admin
def publish(version_id: UUID):
    """
    Make a version live. 409 with a readable sentence if it may not be.

    `has_approval()` first, so the usual refusal is ours; the trigger behind
    `publish()` is what holds if that check is ever wrong.
    """
    with repo_scope(current_admin()) as db:
        version = db.cases.for_review(version_id)
        if version is None:
            return _not_found()
        if not db.reviews.has_approval(version_id):
            return jsonify({"error": "This case version has no approving clinical "
                                     "review yet, so it cannot be published."}), 409
        try:
            db.cases.publish(version_id)
        except PublicationBlocked:
            return jsonify({"error": "This case version has no approving clinical "
                                     "review yet, so it cannot be published."}), 409
        except AlreadyPublished:
            return jsonify({"error": "Another version of this case is already "
                                     "published. Retire it before publishing "
                                     "this one."}), 409
        db.audit.record(
            "case_version.published",
            entity_type="case_version",
            entity_id=version_id,
            reason=f"Published v{version['version']} of {version['slug']}",
            ip_address=request.remote_addr,
        )

    return jsonify({"status": "published"})
