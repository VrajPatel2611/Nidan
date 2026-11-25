"""
The four admin screens that are in the navigation but not built.

Content, AI Ops, Users and System each rendered a title and a one-line
description and nothing else. That reads as a *broken* page rather than an
unbuilt one, and the console had no way to say which it was — so each now
includes `admin/_planned.html` and states what it will show, under whose
task, or that it has no task at all.

The test worth having here is
`test_every_task_a_planned_screen_names_exists_in_the_build_plan`. A screen
that advertises "T-044, owned by Yogesh" is making a claim about the plan,
and the plan is a different file that moves. A stale task number on a screen
an examiner is reading is worse than no number, because it is specific.

These are static reads of the templates. Nothing here needs a database, so
it still runs when Docker is down.
"""

from __future__ import annotations

import pathlib
import re

import pytest

TEMPLATES = pathlib.Path("nidan/web/templates/admin")
BUILD_PLAN = pathlib.Path("docs/spec/BUILD_PLAN.md")

# The four screens in the nav that nothing builds yet, and whether each is
# allowed to name a task. Users (A-09) is specified with no task; System is
# not in UX_SPEC at all. Both must say so rather than imply a plan.
PLANNED = {
    "content.html": "T-044",
    "ops.html": "T-043",
    "users.html": None,
    "system.html": None,
}


def _source(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", sorted(PLANNED))
def test_each_unbuilt_screen_declares_itself(name: str) -> None:
    """The shell is gone and the shared note is in its place."""
    assert 'include "admin/_planned.html"' in _source(name), (
        f"{name} no longer includes the 'not built yet' note. A bare shell "
        f"is indistinguishable from a broken page."
    )


@pytest.mark.parametrize("name,task", sorted(PLANNED.items()))
def test_a_screen_with_no_task_does_not_claim_one(name: str, task: str | None) -> None:
    """
    `task = none` is what makes the note say "this screen has no task".

    Setting it to a plausible string instead would turn an unowned screen
    into one that looks scheduled, which is the specific dishonesty this
    file exists to prevent.
    """
    source = _source(name)
    declares_none = re.search(r"task\s*=\s*none", source) is not None
    if task is None:
        assert declares_none, (
            f"{name} covers a screen with no task in BUILD_PLAN, so it must "
            f"pass `task = none` and say so."
        )
    else:
        assert not declares_none, f"{name} should name {task}."
        assert task in source, f"{name} should name {task}."


def test_every_task_a_planned_screen_names_exists_in_the_build_plan() -> None:
    """
    A task number on one of these screens must be a real task.

    This is the one that bites: BUILD_PLAN's own screen references for
    T-043 and T-044 were off by one until 24 Nov 2026 and nothing caught it,
    because no test compared a claim about the plan with the plan.
    """
    plan = BUILD_PLAN.read_text(encoding="utf-8")
    named = {t for t in PLANNED.values() if t}
    assert named, "nothing to check — did PLANNED lose its tasks?"
    for task in sorted(named):
        assert re.search(rf"\*\*{re.escape(task)} ·", plan), (
            f"the admin console names {task}, which BUILD_PLAN does not "
            f"define. Either the task was renumbered or the screen is stale."
        )


def test_the_shared_note_renders_both_ways() -> None:
    """
    With a task and without, because the two branches say opposite things
    and only one of them is exercised by any given screen.
    """
    from flask import render_template

    from nidan.app import create_app

    app = create_app({"TESTING": True, "SECRET_KEY": "planned"})
    with app.test_request_context():
        scheduled = render_template(
            "admin/_planned.html", task="T-043", spec="UX_SPEC A-08",
            owner="Yogesh", estimate="2 d", items=["one thing"])
        unowned = render_template(
            "admin/_planned.html", task=None, spec="UX_SPEC A-09",
            owner=None, estimate=None, items=None)

    assert "T-043" in scheduled and "Yogesh" in scheduled
    assert "one thing" in scheduled
    assert "has no task" not in scheduled

    assert "has no task" in unowned
    # The empty-items branch must not leave a stray "What it will show:".
    assert "What it will show" not in unowned
