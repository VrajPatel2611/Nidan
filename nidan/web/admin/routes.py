"""
Admin console routes (BUILD_PLAN T-020, UX_SPEC §12).

Jinja + HTMX administrative shell, protected by @require_admin and @require_reviewer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import Blueprint, redirect, render_template, request

from nidan.api.auth import (
    current_actor,
    current_admin,
    require_admin,
)
from nidan.config import settings
from nidan.infra import budget
from nidan.infra.db.repositories import repo_scope
from nidan.infra.llm import pricing

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("")
@bp.get("/")
@require_admin
def dashboard():
    """
    Admin dashboard (A-01).

    **Every figure on this screen is read from the database.** It did not
    start that way: "142 sessions today", "118 completed", "$1.84 LLM cost",
    "3 cases awaiting clinical review", "6.2% feedback fallback rate" and
    "10 published · 2 drafts · 0 retired" were literals in the template, and
    the first four of them were wrong by an order of magnitude against the
    data underneath. T-040 had already replaced an invented leakage rate here
    for the reason that applies to all of them: a hardcoded figure reads as a
    real backlog nobody can find, and as silence on the day there is one.

    Two of the old cards could not be replaced, and are gone rather than
    approximated:

    * **sessions today / completed.** `sessions` has RLS on, and the only
      policies are `own_sessions` and migration 034's
      `flagged_sessions_are_visible_to_admins` — so an admin scope sees its
      own sessions plus the ones a leakage flag points at, and nothing else.
      Counting them would report a number that is correct SQL and a false
      statement about usage. Admin visibility of learners' sessions is
      `UX_SPEC` A-09's to ask for, with the policy that goes with it; it is
      not something this screen should acquire by widening 034.
    * **feedback fallback rate.** The rule-based fallback writes no
      `llm_calls` row at all — `FeedbackResult.call` is `None` because
      nothing was billed — so the denominator for that rate does not exist in
      the database. `spend()["not_ok"]` counts the calls that were made and
      did not succeed, which is a different and true thing.

    Runs as `current_admin()`, not `current_actor()`: the draft count needs
    `admin_manages_case_versions`, and under `nidan_app` only published
    versions are visible, so the panel would report every draft as absent.
    """
    with repo_scope(current_admin()) as db:
        recent_audits = db.audit.recent(limit=10)
        profile = db.profiles.get()
        leakage = db.leakage.unreviewed_count()
        content = db.cases.bank_counts()
        spend = db.llm_calls.spend()
        awaiting_review = len(db.reviews.pending())

    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    return render_template(
        "admin/dashboard.html",
        active_nav="cases",
        active_section="dashboard",
        user_email=user_email,
        recent_audits=recent_audits,
        unreviewed_leakage=leakage["low"] + leakage["high"],
        unreviewed_leakage_high=leakage["high"],
        content=content,
        spend=spend,
        awaiting_review=awaiting_review,
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


# Clinical content (A-06, A-07) lives in nidan/web/admin/content/ (T-044).


# The windows A-08's range selector offers. "Today" and "this month" are UTC
# calendar boundaries, the same as the budget's month, so the two figures on
# the page can be compared without a footnote.
WINDOWS: dict[str, str] = {
    "today": "Today", "7d": "Last 7 days", "30d": "Last 30 days",
    "month": "This month",
}


def _window_start(window: str) -> datetime:
    now = datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {"today": midnight, "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "month": midnight.replace(day=1)}[window]


@bp.get("/ops")
@require_admin
def ai_ops_moved():
    """The page moved to `UX_SPEC` A-08's own route; old links still land."""
    return redirect("/admin/ai", 301)


@bp.get("/ai")
@require_admin
def ai_ops():
    """
    AI operations (T-043, `UX_SPEC` A-08).

    **Every figure is from `llm_calls` or `leakage_flags`, and neither has
    RLS**, so an admin scope reads all of both with no new policy. That is
    the choice Vraj's Y-31 asked to be made deliberately. Usage over time
    comes from what the platform *spent*, never from `sessions`, which an
    admin scope cannot count truthfully, and nothing here needs
    `ServiceActor`.

    Three things this page cannot say, and says so rather than estimating:

    * **Playtest is absent from the cost.** It records nothing, by design
      (`purpose` has no `playtest`), so the figures are learner spend, not
      total spend.
    * **The anonymous-trial prototype records no feedback calls**, so its
      sessions are not in "per completed session".
    * **Failed and fallback rows begin with T-043.** Before it, a failure
      wrote nothing, so a window reaching back before this deploy
      under-counts both.
    """
    window = request.args.get("window", "today")
    if window not in WINDOWS:
        window = "today"
    since = _window_start(window)
    with repo_scope(current_admin()) as db:
        profile = db.profiles.get()
        overview = db.llm_calls.overview(since)
        usage = db.llm_calls.usage(since)
        leaks = db.leakage.flagged_since(since)
        unreviewed = db.leakage.unreviewed_count()
    state = budget.current(fresh=True)
    user_email = (profile.get("display_name") if profile else None) or "admin@nidan.internal"

    def rate(n: int, d: int) -> float | None:
        return n / d * 100 if d else None

    return render_template(
        "admin/ops.html",
        active_nav="ops",
        active_section="ops",
        user_email=user_email,
        window=window, windows=WINDOWS, since=since,
        o=overview, usage=usage, budget=state,
        alert_at=budget.ALERT_AT,
        cheapest=pricing.cheapest_model(),
        configured_model=settings.GROQ_MODEL,
        error_rate=rate(overview["failed"], overview["calls"]),
        fallback_rate=rate(overview["fallback"], overview["feedback"]),
        leak_rate=rate(leaks["flagged"], overview["replies"]),
        leaks=leaks, unreviewed=unreviewed["low"] + unreviewed["high"],
        prices_checked=pricing.PRICES_CHECKED,
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
