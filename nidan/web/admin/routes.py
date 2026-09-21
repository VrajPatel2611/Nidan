"""
Admin console routes (BUILD_PLAN T-020, UX_SPEC §12).

Jinja + HTMX administrative shell, protected by @require_admin and @require_reviewer.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from nidan.api.auth import current_actor, require_admin, require_reviewer
from nidan.infra.db.repositories import repo_scope

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("")
@bp.get("/")
@require_admin
def dashboard():
    """Admin dashboard (A-01)."""
    with repo_scope(current_actor()) as db:
        recent_audits = db.audit.recent(limit=10)
        profile = db.profiles.get()

    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/dashboard.html",
        active_nav="cases",
        active_section="dashboard",
        user_email=user_email,
        recent_audits=recent_audits,
        pending_reviews=3,
        unreviewed_leakage=2,
    )


@bp.get("/cases")
@require_admin
def case_bank():
    """Case bank view (A-02)."""
    with repo_scope(current_actor()) as db:
        profile = db.profiles.get()
    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/cases.html",
        active_nav="cases",
        active_section="case_bank",
        user_email=user_email,
        pending_reviews=3,
    )


@bp.get("/reviews")
@require_reviewer
def review_queue():
    """Review queue view (A-05). Accessible by admins and reviewers."""
    with repo_scope(current_actor()) as db:
        profile = db.profiles.get()
    user_email = (profile.get("display_name") if profile else None) or "reviewer@nidan.internal"

    return render_template(
        "admin/reviews.html",
        active_nav="cases",
        active_section="review_queue",
        user_email=user_email,
        pending_reviews=3,
    )


@bp.get("/content")
@require_admin
def clinical_content():
    """Clinical content view (A-06)."""
    with repo_scope(current_actor()) as db:
        profile = db.profiles.get()
    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/content.html",
        active_nav="content",
        active_section="content",
        user_email=user_email,
        pending_reviews=3,
    )


@bp.get("/ops")
@require_admin
def ai_ops():
    """AI Operations view (A-08)."""
    with repo_scope(current_actor()) as db:
        profile = db.profiles.get()
    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/ops.html",
        active_nav="ops",
        active_section="ops",
        user_email=user_email,
        pending_reviews=3,
    )


@bp.get("/users")
@require_admin
def users():
    """Users & support view (A-09)."""
    with repo_scope(current_actor()) as db:
        profile = db.profiles.get()
    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/users.html",
        active_nav="users",
        active_section="users",
        user_email=user_email,
        pending_reviews=3,
    )


@bp.get("/system")
@require_admin
def system():
    """System view (A-10)."""
    with repo_scope(current_actor()) as db:
        profile = db.profiles.get()
    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/system.html",
        active_nav="system",
        active_section="system",
        user_email=user_email,
        pending_reviews=3,
    )


@bp.post("/audit-action")
@require_admin
def record_audit():
    """Test action recording to audit_log."""
    action = request.form.get("action", "admin.test_action")
    reason = request.form.get("reason", "admin action executed")
    entity_type = request.form.get("entity_type", "system")

    with repo_scope(current_actor()) as db:
        log_entry = db.audit.record(
            action=action,
            entity_type=entity_type,
            reason=reason,
            metadata={"ip": request.remote_addr},
        )
    return f"Audit log recorded ID {log_entry['id']}", 200
