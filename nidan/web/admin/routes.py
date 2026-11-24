"""
Admin console routes (BUILD_PLAN T-020, UX_SPEC §12).

Jinja + HTMX administrative shell, protected by @require_admin and @require_reviewer.
"""

from __future__ import annotations

from flask import Blueprint, render_template, request

from nidan.api.auth import (
    current_actor,
    current_admin,
    require_admin,
)
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
        # T-040. This was the literal `2` until the queue existed, and a
        # hardcoded "needs attention" figure is worse than an empty panel:
        # it reads as a real backlog nobody can find, and as silence on the
        # day there IS one.
        leakage = db.leakage.unreviewed_count()

    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/dashboard.html",
        active_nav="cases",
        active_section="dashboard",
        user_email=user_email,
        recent_audits=recent_audits,
        unreviewed_leakage=leakage["low"] + leakage["high"],
        unreviewed_leakage_high=leakage["high"],
    )


@bp.get("/cases")
@require_admin
def case_bank():
    """Case bank view (A-02)."""
    with repo_scope(current_admin()) as db:
        cases = db.cases.bank()
        profile = db.profiles.get()
    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/cases.html",
        active_nav="cases",
        active_section="case_bank",
        user_email=user_email,
        cases=cases,
    )


# The review queue (A-05) lives in nidan/web/admin/reviews/ (T-023).


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
    )


@bp.get("/leakage")
@require_admin
def leakage_queue():
    """
    The persona-leakage queue (T-040 criterion 2, `TECH_SPEC` §5.3).

    Under AI Ops rather than on its own nav entry: `UX_SPEC` §12 has no
    leakage screen, and A-08 is where the sidebar already promises "LLM
    Metrics & Leakage". T-043 builds the metrics half of that page.

    Shows the patient's words beside the flag, read live from
    `session_events` — the reply is what an administrator is judging, and a
    copy of it stored on the flag would outlive the erasure that redacts the
    original.
    """
    include_reviewed = request.args.get("all") == "1"
    # `current_admin()`, not `current_actor()`. Migration 034's two policies
    # are `TO nidan_admin`, and `own_sessions` binds every other role -- so
    # under an ordinary `AuthenticatedUser` the join through `sessions`
    # returns nothing and the queue renders empty. That reads as "no leaks"
    # rather than as a permission problem, which is the failure mode
    # `DATA_MODEL` 10.1 is otherwise careful about, and it is what
    # `tests/db/test_admin_leakage_queue.py` caught.
    with repo_scope(current_admin()) as db:
        profile = db.profiles.get()
        flags = [
            {**flag, "reply": db.leakage.reply_text(
                flag["session_id"], flag["event_seq"])}
            for flag in db.leakage.queue(include_reviewed=include_reviewed)
        ]
        counts = db.leakage.unreviewed_count()
    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/leakage.html",
        active_nav="ops",
        active_section="leakage",
        user_email=user_email,
        flags=flags,
        counts=counts,
        include_reviewed=include_reviewed,
    )


@bp.post("/leakage/<uuid:flag_id>")
@require_admin
def review_leakage(flag_id):
    """
    Confirm or dismiss one flag.

    **Audited, because confirming removes a session from the research
    export** (`DATA_MODEL` §11.7). That is a decision about the dataset the
    published result rests on, and the one question anyone will ask later is
    who decided it and when. The verdict goes in `reason` rather than only in
    `metadata` so it is readable in the audit screen without expanding JSON.
    """
    confirmed = request.form.get("verdict") == "confirm"
    # An UPDATE on `leakage_flags`, which only `nidan_admin` may perform
    # (migration 034). `LeakageRepository.review()` refuses anything else in
    # Python before the statement runs.
    with repo_scope(current_admin()) as db:
        decided = db.leakage.review(flag_id, confirmed=confirmed)
        if decided:
            db.audit.record(
                "leakage_flag.reviewed",
                entity_type="leakage_flag",
                entity_id=flag_id,
                reason=("confirmed — session excluded from research export"
                        if confirmed else "dismissed — not a leak"),
                metadata={"confirmed": confirmed},
                ip_address=request.remote_addr,
            )
    if not decided:
        # Not an error: someone else got there first. `review()`'s
        # `AND reviewed = false` is what makes that safe rather than a race
        # in which the second verdict silently overwrites the first.
        return "Already reviewed by someone else.", 409
    return "", 204


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
