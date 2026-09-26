# T-022 · Playtest with live instrumentation

**4 days · depends on T-021 and T-016 (done) · Owner Y**

> ```bash
> git checkout main && git pull origin main && git checkout -b feat/t-022-playtest
> ```
> The `git pull` matters more here than anywhere: T-021 will have merged in
> between, and this task builds directly on it.

---

# What this screen is

`/admin/cases/{id}/versions/{v}/playtest` — `UX_SPEC` calls it **the
highest-value screen in the console**, and that is not marketing copy.

A split view. Left: the student's consultation, exactly as a learner sees it.
Right: everything the assessment engine is thinking, live, question by question.

**This is how a clinician sees *why* a detector fired without reading Python.**
Right now, the only way to answer "why did this case flag anchoring?" is to open
`nidan/domain/assessment/bias.py`. After this screen exists, a doctor can answer
it themselves — and, more importantly, can catch a broken case while authoring
it instead of after collecting data from it.

**No backend blocker on this one.** Everything you need already exists.

---

# Reading, in order

1. `docs/spec/UX_SPEC.md` §12.5 — the screen, with a drawing
2. `docs/spec/BUILD_PLAN.md` — the T-022 block, five criteria
3. `nidan/domain/assessment/engine.py` — the `assess()` function you will call
4. `nidan/domain/session.py` — `replay(events)`, which rebuilds state from the log

You do not need to understand the detectors' internals. You need to know what
they return, and that is `AssessmentResult` in `engine.py`.

---

# The acceptance criteria

1. Split view: student UI left, instrumentation right
2. Right panel shows per-question matched topics, counters (q, a, m, c, k/K),
   live detector state, and clues explored
3. **Leakage warning** when a reply reveals an unasked required topic
4. **Ephemeral** — playtest sessions never appear in user data or analytics
5. Reset without leaving the page

---

# How the engine works, in the amount you need

The whole system is event-sourced. A consultation is not an object held in
memory — it is an append-only list of events, and state is a pure function of
that list.

```python
from nidan.domain.session import replay
from nidan.domain.assessment.engine import assess

session = replay(events, case_id=..., started_at=...)   # current state
result  = assess(events, case)                          # full assessment
```

`assess()` is **pure**. Same events in, same result out, no database, no clock,
no network. That is what makes this screen possible: after every single
question, you call `assess()` on the events so far and render whatever comes
back. No special "playtest mode" inside the engine, no duplicated logic — the
right-hand panel is just the engine's real output, displayed.

`AssessmentResult` carries `question_count`, `examination_count`,
`investigation_count`, `coverage_pct`, `topics_hit`, `topics_missed`,
`bias_detail`, the two scorecards, `key_investigations_done` /
`key_investigations_total`.

`bias_detail` has one entry per detector:

```python
{"anchoring":         {"detected": bool, "score": float, "rule_fired": "A1"|"A2"|None, "reason": str, ...},
 "premature_closure": {...},   # rules P1, P2
 "confirmation_bias": {...}}   # rules C1, C2
```

`rule_fired` is what you show in the "which rule" column. Two rules per
detector, OR-ed — `A1` is topic concentration above the threshold, `A2` is
"asked 3+ anchor questions and zero alternative ones". A case author who can see
*which* rule fired can tell a genuine trap from a badly written one.

---

# The four panels on the right

## Matched topics — per question, with *why*

For each question the tester asks, show which required topics it matched **and
what caused the match** — which keyword, or which similarity score.

```
Question 2
Matched topics
 ✓ pain_character   (keyword "burning")
```

The "why" is the entire value. "It matched" tells a clinician nothing; "it
matched because you used the word *burning*" tells them whether the lexicon is
right.

The function is `extract_topics(user_message)` in
`nidan/domain/assessment/topics.py`, and the lexicon it uses is `TOPIC_KEYWORDS`
in the same file.

## Counters — live

```
q=2   a=0   m=1   c=2/8 (25%)
```

| | |
|---|---|
| `q` | questions asked |
| `a` | alternative-hypothesis questions |
| `m` | anchor-topic questions |
| `c` | required topics covered / total |
| `k/K` | key investigations done / total |

All of them come straight off `AssessmentResult`.

## Detectors — live

```
Anchoring       ✗   0.00   —
Premature       ✓   0.75   P2
Confirmation    ✗   0.00   —
```

Flag, score, and which rule fired. Update after every question.

## Clues explored

Which contradictory clues the tester has uncovered, and which they have not.
Read from the session state against `case["contradictory_clues"]`.

```
Clues explored  2 / 6
 ✓ burning   ✓ after meal
 ○ ibuprofen ○ antacid ○ lying ○ reflux
```

---

# Leakage — criterion 3, and the subtle one

An amber warning when **the patient's reply reveals a required topic the
question did not ask about.**

```
⚠ LEAKAGE — reply mentioned "after dinner" (meal_relationship) but the
   question did not ask about meals.
```

Why this matters: the learner gets credit for covering `meal_relationship`
without having thought to ask about meals. The case has done their reasoning for
them. The data then says the learner had 90 % history coverage when really the
persona prompt was too chatty. Every session recorded against that case is
quietly contaminated.

Catching it during authoring costs a prompt edit. Catching it after a study
costs the study.

**How to detect it:** run `extract_topics()` on the patient's *reply*, run it on
the learner's *question*, and flag any required topic present in the reply but
absent from the question.

That is a heuristic, and it will have false positives. Say so in the UI —
"possible leakage" and an amber tone, not a red error. The author decides.

There is a `leakage_flags` table in the schema, but it is for production
sessions. **Playtest writes nothing to it** — see below.

---

# Ephemeral — criterion 4, and the one that is easy to get wrong

**A playtest session must never appear in user data, analytics, or the research
export.** Ever.

This is not a nice-to-have. Two clinicians playtesting cases for a week would
otherwise inject dozens of expert consultations into a dataset about student
reasoning, and nobody would notice until the numbers looked strange.

Concretely:

- **Do not write to `sessions`, `session_events`, or `session_results`.** Hold
  the event list in the Flask session or in memory for the request. The engine
  does not care where the events come from — it takes a list.
- LLM calls are tagged `purpose="playtest"` so they are excluded from
  cost-per-session reporting.
- Draft versions are playtestable. That is the entire point — a case must be
  testable before it is approved. `db.cases.for_editing(version_id)` returns
  drafts; `db.cases.content(...)` does not.

If you find yourself writing `db.events.append(...)` in this task, stop.

---

# Reset — criterion 5

A reset button that clears the whole thing without a page reload. Empty the
event list, re-render both panels, keep the case loaded. An author will press
this fifty times in an afternoon while tuning a persona prompt.

---

# Files

### You write

```
nidan/web/admin/playtest/__init__.py
nidan/web/admin/playtest/routes.py
nidan/web/templates/admin/playtest/index.html
nidan/web/templates/admin/playtest/_student.html
nidan/web/templates/admin/playtest/_instrumentation.html
nidan/web/static/admin/playtest.js
tests/test_admin_playtest.py
docs/build-log/T-022-playtest.md
```

Plus a `[ Playtest ]` button on the case editor from T-021 — yours.

### You must not touch

```
nidan/domain/assessment/**    ← the research instrument. Call it, never change it
nidan/domain/session.py
nidan/infra/**
migrations/**
```

You are **calling** the engine here, not modifying it. If you feel you need to
change something inside `domain/assessment/`, you have misread the task — ask.

---

# Suggested order

**Day 1 · The student side.** Split layout, and the left panel working: ask a
question, get a reply, show the transcript. Reuse what `nidan/api/routes.py`
already does for the prototype consultation — read it, do not import from it.

**Day 2 · Counters and detectors.** Call `assess()` after every event, render
the counters and the three detector rows. This is the moment the screen starts
being useful, and it is a small amount of code because the engine does the work.

**Day 3 · Matched topics and clues.** Per-question topic matching with the
reason. Clues explored. HTMX to update the right panel without a reload.

**Day 4 · Leakage, reset, tests, build log.**

---

# Tests to write

In `tests/test_admin_playtest.py`:

1. The playtest route 404s for anonymous, non-admin and expired tokens, with
   **identical** bodies
2. **A playtest session writes no row to `sessions`, `session_events` or
   `session_results`** — count rows before and after a full playtest
3. The instrumentation panel reflects what the engine actually returned, not a
   re-implementation of it
4. Leakage is flagged when a reply contains a required topic the question did
   not ask about
5. Reset clears the events and the panels
6. A **draft** version is playtestable

Number 2 is the important one. Write it, then break it on purpose: add a write
to `session_events`, watch the test go red, take it out again.

---

# Definition of done

- [ ] All five acceptance criteria satisfied
- [ ] The five checks in `00_START_HERE.md` Part 5 pass locally
- [ ] You have watched the "writes nothing" test fail on purpose
- [ ] `docs/build-log/T-022-playtest.md` written
- [ ] `BUILD_PLAN` T-022 marked done, `python scripts/build_status.py` run
- [ ] Pull request open, base `main`, eight checks green
