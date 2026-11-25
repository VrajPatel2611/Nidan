"""
Clinical content (T-044): the master-list editor (`UX_SPEC` A-06) and the
topic lexicon editor (A-07).

## The two editors save differently, on purpose

**Master lists write the database.** `/v1` reads `examinations` and
`investigations` at request time (`CatalogRepository._menu` and
`master_entry`), so an item added here is on every case's menu at once, which
is what A-06's warning says. `cases.py` stays the seed for a fresh
database, so this database and `cases.py` may now differ, and that is
expected. `tests/db/test_seed.py` checks the seed on a freshly migrated
database, not this one.

**The lexicon does not write anything.** The engine scores from `topics.py`,
so a saved phrase would be ignored by scoring and would break
`test_seed.py`'s agreement. The editor builds a proposal and exports a
migration plus the `TOPIC_KEYWORDS` change; see `lexicon_tools.py`.

Every write is audited, and every route is `@require_admin`, so every refusal
is the console's identical 404 (`UX_SPEC` §12.1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, Response, abort, redirect, render_template, request

from nidan.api.auth import current_admin, require_admin
from nidan.domain.assessment.topics import TOPIC_KEYWORDS
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.catalog import DuplicateKey
from nidan.infra.db.repositories.lexicon import DEAD_AFTER_DAYS
from nidan.web.admin.content import lexicon_tools as lt

content_bp = Blueprint("admin_content", __name__, url_prefix="/admin/content")

TABLES: dict[str, dict[str, str]] = {
    "examinations": {"singular": "examination", "title": "Examinations"},
    "investigations": {"singular": "investigation", "title": "Investigations"},
}

_KEY = lt.TOPIC_KEY       # same shape rule: lowercase, digits, underscores


def _who(db) -> str:
    profile = db.profiles.get()
    return (profile.get("display_name") if profile else None) or "admin@nidan.internal"


def _table_or_404(table: str) -> dict[str, str]:
    if table not in TABLES:
        abort(404)
    return TABLES[table]


# ── A-06 · examinations and investigations ──────────────────────────────

@content_bp.get("")
@content_bp.get("/")
@require_admin
def index():
    return redirect("/admin/content/investigations")


@content_bp.get("/<table>")
@require_admin
def master_list(table: str):
    meta = _table_or_404(table)
    group = request.args.get("group", "")
    active = request.args.get("active", "")
    q = request.args.get("q", "").strip().lower()
    with repo_scope(current_admin()) as db:
        rows = db.catalog.admin_list(table)
        who = _who(db)
    groups = sorted({r["group_name"] for r in rows})
    shown = [r for r in rows
             if (not group or r["group_name"] == group)
             and (active != "yes" or r["is_active"])
             and (active != "no" or not r["is_active"])
             and (not q or q in r["key"] or q in r["label"].lower())]
    return render_template(
        "admin/content/list.html", active_nav="content", active_section=table,
        user_email=who, table=table, meta=meta, rows=shown, total=len(rows),
        groups=groups, group=group, active=active, q=q,
        flash=request.args.get("done"))


@content_bp.get("/<table>/new")
@require_admin
def new_item(table: str):
    meta = _table_or_404(table)
    with repo_scope(current_admin()) as db:
        groups = sorted({r["group_name"] for r in db.catalog.admin_list(table)})
        cases = db.catalog.case_count()
        who = _who(db)
    return render_template(
        "admin/content/form.html", active_nav="content", active_section=table,
        user_email=who, table=table, meta=meta, item=None, groups=groups,
        case_count=cases, errors=[], values={})


@content_bp.post("/<table>")
@require_admin
def add_item(table: str):
    meta = _table_or_404(table)
    values = _form_values()
    errors = _validate(values, new=True)
    with repo_scope(current_admin()) as db:
        if not errors:
            try:
                db.catalog.add_entry(table, **values)
            except DuplicateKey:
                errors.append(f"The key {values['key']!r} is already in use. "
                              f"Keys cannot be reused, even for a retired item.")
            else:
                db.audit.record(
                    "master_list.item_added", entity_type=table,
                    reason=f"added {values['key']}",
                    metadata={"key": values["key"], "label": values["label"]},
                    ip_address=request.remote_addr)
        groups = sorted({r["group_name"] for r in db.catalog.admin_list(table)})
        cases = db.catalog.case_count()
        who = _who(db)
    if not errors:
        return redirect(f"/admin/content/{table}?done=added:{values['key']}", 303)
    return render_template(
        "admin/content/form.html", active_nav="content", active_section=table,
        user_email=who, table=table, meta=meta, item=None, groups=groups,
        case_count=cases, errors=errors, values=values), 400


@content_bp.get("/<table>/<key>/edit")
@require_admin
def edit_item(table: str, key: str):
    meta = _table_or_404(table)
    with repo_scope(current_admin()) as db:
        item = db.catalog.admin_entry(table, key)
        groups = sorted({r["group_name"] for r in db.catalog.admin_list(table)})
        who = _who(db)
    if item is None:
        abort(404)
    return render_template(
        "admin/content/form.html", active_nav="content", active_section=table,
        user_email=who, table=table, meta=meta, item=item, groups=groups,
        case_count=None, errors=[], values=dict(item))


@content_bp.post("/<table>/<key>")
@require_admin
def update_item(table: str, key: str):
    meta = _table_or_404(table)
    values = _form_values()
    values.pop("key", None)       # never changes: see `update_entry`
    errors = _validate(values, new=False)
    with repo_scope(current_admin()) as db:
        item = db.catalog.admin_entry(table, key)
        if item is None:
            abort(404)
        if not errors:
            db.catalog.update_entry(table, key, **values)
            db.audit.record(
                "master_list.item_edited", entity_type=table,
                reason=f"edited {key}",
                metadata={"key": key, "changed": sorted(
                    f for f in values if (values[f] or None) != (item.get(f) or None))},
                ip_address=request.remote_addr)
        groups = sorted({r["group_name"] for r in db.catalog.admin_list(table)})
        who = _who(db)
    if not errors:
        return redirect(f"/admin/content/{table}?done=edited:{key}", 303)
    return render_template(
        "admin/content/form.html", active_nav="content", active_section=table,
        user_email=who, table=table, meta=meta, item=item, groups=groups,
        case_count=None, errors=errors, values={**values, "key": key}), 400


@content_bp.post("/<table>/<key>/active")
@require_admin
def set_active(table: str, key: str):
    """
    Retire or restore. A-06: retiring a used item needs a confirmation that
    names how many cases reference it. The button asks in the browser, and
    the server refuses without `confirm=1` too, so a retirement never happens
    because a script skipped the dialog.
    """
    _table_or_404(table)
    active = request.form.get("active") == "1"
    with repo_scope(current_admin()) as db:
        item = db.catalog.admin_entry(table, key)
        if item is None:
            abort(404)
        if not active and item["used_by"] and request.form.get("confirm") != "1":
            return (f"{key} is referenced by {item['used_by']} case(s). "
                    f"Retiring it needs confirmation."), 409
        db.catalog.set_active(table, key, active)
        db.audit.record(
            "master_list.item_restored" if active else "master_list.item_retired",
            entity_type=table, reason=f"{'restored' if active else 'retired'} {key}",
            metadata={"key": key, "used_by": item["used_by"]},
            ip_address=request.remote_addr)
    return redirect(
        f"/admin/content/{table}?done={'restored' if active else 'retired'}:{key}", 303)


def _form_values() -> dict[str, Any]:
    f = request.form
    return {"key": f.get("key", "").strip(), "label": f.get("label", "").strip(),
            "group_name": f.get("group_name", "").strip(),
            "normal_result": f.get("normal_result", "").strip(),
            "reference_range": f.get("reference_range", "").strip() or None}


def _validate(v: dict[str, Any], *, new: bool) -> list[str]:
    errors = []
    if new and not _KEY.match(v.get("key", "")):
        errors.append("The key is 3–48 characters: lowercase letters, digits "
                      "and underscores, starting with a letter (e.g. troponin_hs).")
    for field, label in (("label", "Label"), ("group_name", "Group"),
                         ("normal_result", "Normal result")):
        if not v.get(field):
            errors.append(f"{label} is required.")
    return errors


# ── A-07 · topic lexicon ────────────────────────────────────────────────

def _lexicon_page(proposal: lt.Proposal, *, topic: str | None,
                  messages: list[str] | None = None,
                  warnings: list[str] | None = None,
                  question: str = "", status: int = 200):
    with repo_scope(current_admin()) as db:
        stored = {t["topic_key"]: t for t in db.lexicon.topics()}
        last_counted = db.lexicon.last_counted()
        who = _who(db)
        phrases = db.lexicon.phrases(topic) if topic in stored else []
    after = lt.apply(TOPIC_KEYWORDS, proposal)
    topic = topic if topic in after else next(iter(after))
    stats = {p["phrase"]: p for p in phrases}
    added = {p for t, p in proposal.added if t == topic}
    removed = {p for t, p in proposal.removed if t == topic}
    rows = ([{"phrase": p, "added": p in added, "stat": stats.get(p)}
             for p in after[topic]]
            + [{"phrase": p, "removed": True, "stat": stats.get(p)}
               for p in TOPIC_KEYWORDS.get(topic, ()) if p in removed])
    dead_total = sum(t["dead"] for t in stored.values())
    return render_template(
        "admin/content/lexicon.html", active_nav="content",
        active_section="lexicon", user_email=who,
        topics=[{"key": k, "phrases": len(v),
                 "dead": stored.get(k, {}).get("dead", 0),
                 "new": k not in TOPIC_KEYWORDS,
                 "changed": any(t == k for t, _ in proposal.added + proposal.removed)}
                for k, v in after.items()],
        topic=topic, rows=rows, proposal=proposal,
        phrase_total=sum(len(v) for v in after.values()),
        dead_total=dead_total, dead_days=DEAD_AFTER_DAYS,
        last_counted=last_counted, blocking=lt.blocking(TOPIC_KEYWORDS, proposal),
        messages=messages or [], warnings=warnings or [], question=question,
        test=_test(question, topic, proposal) if question else None), status


def _test(question: str, topic: str, proposal: lt.Proposal) -> dict[str, Any]:
    now = lt.matches(question, TOPIC_KEYWORDS)
    after = lt.matches(question, lt.apply(TOPIC_KEYWORDS, proposal))
    return {"topic": topic, "covered": topic in after, "hits": after.get(topic, []),
            "covered_now": topic in now, "others": {t: p for t, p in after.items()
                                                    if t != topic},
            "changed": now != after}


@content_bp.get("/lexicon")
@require_admin
def lexicon():
    return _lexicon_page(lt.Proposal(), topic=request.args.get("topic"))


@content_bp.post("/lexicon")
@require_admin
def lexicon_action():
    """
    Every edit is a POST that returns the whole page with the proposal in
    hidden fields. Nothing is stored between requests, so leaving the page
    discards the proposal, and the page says so.
    """
    f = request.form
    proposal = lt.decode(f.to_dict(flat=False))
    topic = f.get("topic") or None
    action = f.get("action", "")
    messages: list[str] = []
    warnings: list[str] = []

    if action == "add_phrase":
        phrase = lt.normalise(f.get("phrase", ""))
        check = lt.check_phrase(TOPIC_KEYWORDS, proposal, topic or "", phrase)
        if check.ok:
            if (topic, phrase) in proposal.removed:
                proposal = lt.Proposal(
                    added=proposal.added, new_topics=proposal.new_topics,
                    removed=tuple(r for r in proposal.removed if r != (topic, phrase)))
            else:
                proposal = lt.Proposal(added=(*proposal.added, (topic, phrase)),
                                       removed=proposal.removed,
                                       new_topics=proposal.new_topics)
            messages.append(f"“{phrase}” proposed for {topic}.")
        warnings += check.errors + check.warnings
    elif action == "remove_phrase":
        phrase = lt.normalise(f.get("phrase", ""))
        if (topic, phrase) in proposal.added:
            proposal = lt.Proposal(
                added=tuple(a for a in proposal.added if a != (topic, phrase)),
                removed=proposal.removed, new_topics=proposal.new_topics)
        elif phrase in TOPIC_KEYWORDS.get(topic or "", ()):
            proposal = lt.Proposal(added=proposal.added,
                                   removed=(*proposal.removed, (topic, phrase)),
                                   new_topics=proposal.new_topics)
            messages.append(f"“{phrase}” proposed for removal from {topic}.")
    elif action == "restore_phrase":
        phrase = lt.normalise(f.get("phrase", ""))
        proposal = lt.Proposal(
            added=proposal.added, new_topics=proposal.new_topics,
            removed=tuple(r for r in proposal.removed if r != (topic, phrase)))
    elif action == "new_topic":
        key, name = f.get("new_key", "").strip(), f.get("new_name", "").strip()
        check = lt.check_topic(TOPIC_KEYWORDS, proposal, key, name)
        if check.ok:
            proposal = lt.Proposal(added=proposal.added, removed=proposal.removed,
                                   new_topics=(*proposal.new_topics, (key, name)))
            topic = key
            messages.append(f"Topic {key} proposed. Add at least one phrase "
                            f"before exporting.")
        warnings += check.errors
    elif action == "discard":
        proposal = lt.Proposal()

    return _lexicon_page(proposal, topic=topic, messages=messages,
                         warnings=warnings, question=f.get("question", ""))


@content_bp.post("/lexicon/test")
@require_admin
def lexicon_test():
    """The live tester's fragment, swapped by HTMX as the author types."""
    proposal = lt.decode(request.form.to_dict(flat=False))
    question = request.form.get("question", "")
    topic = request.form.get("topic") or next(iter(TOPIC_KEYWORDS))
    return render_template("admin/content/_tester.html", question=question,
                           test=_test(question, topic, proposal) if question.strip() else None)


def _export_parts(proposal: lt.Proposal):
    with repo_scope(current_admin()) as db:
        head = db.lexicon.schema_head()
        who = _who(db)
    revision = lt.next_revision(head)
    source = lt.migration_source(proposal, revision=revision, down_revision=head,
                                 author=who, today=datetime.now(UTC).date())
    return revision, head, source, who


@content_bp.post("/lexicon/export")
@require_admin
def lexicon_export():
    proposal = lt.decode(request.form.to_dict(flat=False))
    blocked = lt.blocking(TOPIC_KEYWORDS, proposal)
    if proposal.empty or blocked:
        return _lexicon_page(proposal, topic=request.form.get("topic"),
                             warnings=blocked or ["There is nothing to export yet."],
                             status=400)
    revision, head, source, who = _export_parts(proposal)
    with repo_scope(current_admin()) as db:
        # Audited although nothing in the database changed: this is the
        # moment a scoring change was proposed, and the commit that lands it
        # will point back here.
        db.audit.record(
            "lexicon.export_generated", entity_type="topic_lexicon",
            reason=f"migration {revision} generated",
            metadata={"revision": revision, "added": len(proposal.added),
                      "removed": len(proposal.removed),
                      "new_topics": [k for k, _ in proposal.new_topics]},
            ip_address=request.remote_addr)
    return render_template(
        "admin/content/export.html", active_nav="content",
        active_section="lexicon", user_email=who, proposal=proposal,
        filename=lt.migration_filename(revision), source=source, head=head,
        patch=lt.topics_patch(TOPIC_KEYWORDS, proposal))


@content_bp.post("/lexicon/export.py")
@require_admin
def lexicon_download():
    proposal = lt.decode(request.form.to_dict(flat=False))
    if proposal.empty or lt.blocking(TOPIC_KEYWORDS, proposal):
        abort(400)
    revision, _, source, _ = _export_parts(proposal)
    return Response(source, mimetype="text/x-python", headers={
        "Content-Disposition":
            f'attachment; filename="{lt.migration_filename(revision)}"'})
