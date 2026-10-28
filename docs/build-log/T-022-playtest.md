# T-022 · Playtest with live instrumentation

| | |
|---|---|
| **Task** | T-022, BUILD_PLAN Phase 2 |
| **Status** | ✅ Complete — 28 October 2026 |
| **Branch** | `feat/t-022-playtest` |
| **Estimated** | 4 days |
| **Specification** | `UX_SPEC` §12.5 A-04 · `BUILD_PLAN` T-022 |
| **Behaviour change** | New admin screen at `/admin/cases/{id}/versions/{v}/playtest`: a consultation on the left, the assessment engine's live view of it on the right. Nothing it does is stored. |

---

## 1 · Summary

```
nidan/web/admin/playtest/__init__.py               package export
nidan/web/admin/playtest/routes.py                 page + ask / examine / investigate / diagnose / state
nidan/web/admin/playtest/instrumentation.py        what the right-hand panel shows, from assess()
nidan/web/templates/admin/playtest/index.html      the split view
nidan/web/templates/admin/playtest/_student.html   transcript, as a learner sees it
nidan/web/templates/admin/playtest/_instrumentation.html  counters, detectors, clues, topics, leakage
nidan/web/static/admin/playtest.js                 holds the event log; posts it, swaps the panels
nidan/web/templates/admin/cases/editor.html        + [ Playtest ] button
nidan/app.py                                       + blueprint registration
tests/test_admin_playtest.py                       16 tests, against a real database
```

**16 new tests.** 623 pass across the full suite, none skipped.

---

## 2 · Definition of done

| # | Acceptance criterion | Met by |
|---|---|---|
| 1 | Split view: student UI left, instrumentation right | `index.html` |
| 2 | Per-question matched topics, counters, live detectors, clues explored | `instrumentation.build()` · `_instrumentation.html` |
| 3 | Leakage warning when a reply reveals an unasked required topic | `instrumentation._turns()` — amber, worded as *possible* leakage |
| 4 | Ephemeral — never in user data or analytics | No `sessions` row, no `session_events`, no `session_results`; LLM calls tagged `purpose="playtest"` |
| 5 | Reset without leaving the page | `playtest.js` empties the log and posts to `/state` |

| Check | Result |
|---|---|
| "Writes nothing" test watched failing on purpose | ✅ A `session_events` write added to `/ask` turned it red; removed |
| `ruff` · `mypy --strict` · `lint-imports` | clean · clean · 2 kept |
| `pytest` (Docker running, nothing skipped) | 623 passed |
| `validate_detectors.py` | 94.4 % |
| `test_case_invariants.py` | 46 passed |

---

## 3 · Decisions

### 3.1 The event log lives in the browser

Each request posts the events so far; the server validates every one with
`validate_payload`, appends the new ones, runs `assess()` and returns the whole
list with both panels rendered. The server keeps nothing between requests.

The brief offered the Flask session or server memory. The Flask session is a
signed cookie of about 4 KB, which a dozen patient replies outgrow. Server memory
is per gunicorn worker, so consecutive requests would see different playtests.
The browser has neither problem, and makes Reset an empty list.

A client can post an event list it invented. It is validated against the event
shapes, limited to the six playtest event types and to 400 events, and the only
thing it can mislead is the author's own panel.

### 3.2 The panel displays the engine; it does not recompute it

Counters, flags, scores and rules are read off `AssessmentResult`.
`test_the_panel_shows_what_assess_returned` doctors the result on its way in
and asserts the doctored values appear — a panel that computed its own numbers
would fail it.

Two things the engine does not report are derived here, each tied back to it:

- **Why a topic matched.** `extract_topics` returns topic names only. The keyword
  is the first one in that topic's `TOPIC_KEYWORDS` entry found in the text —
  the one `extract_topics`'s own loop stops at.
- **Which clues were explored.** The engine reports a count, `k`. The per-clue
  breakdown uses `clue_keywords` from `bias.py` and is compared with `k`; if
  they ever differ the panel says so in red rather than showing either silently.

### 3.3 Counters `a` and `m` — the brief has them the wrong way round

The T-022 brief defines `a` as alternative-hypothesis questions and `m` as
anchor-topic questions. The engine (`detect_anchoring`) and `DATA_MODEL` §8.5
(`"q": 6, "a": 6, "m": 1`) have `a` = anchor, `m` = alternative. The spec wins;
the panel shows the engine's values with a legend.

`k/K` in the engine is contradictory clues explored / total. Key investigations
are shown separately as *key tests n/N*.

### 3.4 Leakage

A required topic that `extract_topics` finds in the patient's reply but not in
the question. It is a heuristic with false positives — "worse" matches
`relieving_factors` — so it is amber and says *possible*. Nothing is written to
`leakage_flags`, which is for production sessions.

Worth knowing when reading it: coverage credit comes from the **question**
(`patient_reply.matched_topics` is `extract_topics(question)`), so a leaky reply
does not inflate `c` directly. What it does is hand the learner information they
did not ask for, which makes the case easier than its numbers say.

### 3.5 Detector names

The headings are the plain-language ones — *Diagnostic focus · History
completeness · Evidence exploration* — with the technical name beside each in
muted text. This is an authoring screen, and the rule labels (A1, P2, C1…) only
mean something against those names. The student panel has no assessment state
and no such vocabulary.

### 3.6 Admin only, for now

The routes are `@require_admin`, and the version is loaded with `for_editing`,
which is what makes drafts playtestable. T-023 needs reviewers to open Playtest,
but a reviewer's scope cannot read drafts yet — that is handoff item V-1. When it
lands, T-023 changes the guard.

### 3.7 No audit rows

Playtest changes nothing, so it records nothing; the editor's GET does not audit
either. An audit row per question would also bury the real actions.

---

## 4 · Found along the way — not fixed here

**The case editor's form path loses content.** `_parse_form_content` in
`nidan/web/admin/cases/routes.py` rebuilds the whole content dict from form
fields: it sets `examination` and `investigations` to `{}`, writes
`alternative_hypothesis_keywords` where the engine reads `alternative_topics`,
and drops `patient.intro`. Saving a seeded case through the form wipes its
examinations and investigations. A separate fix, on its own branch. Playtest
names any missing engine field instead of failing with a 500.

---

## 5 · How to undo

1. `git revert` the T-022 commit
2. Nothing in the database to undo — Playtest writes nothing

---

## 6 · Verification

```bash
ruff check . && mypy nidan/domain --strict && lint-imports
pytest -q                                   # 623 passed, Docker running
pytest tests/test_admin_playtest.py -q      # 16 passed
python validate_detectors.py                # PASS: 94.4% >= 94%
pytest tests/test_case_invariants.py -q     # 46 passed
```
