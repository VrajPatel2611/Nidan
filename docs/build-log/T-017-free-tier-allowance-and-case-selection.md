# T-017 · Free-tier allowance and case selection

| | |
|---|---|
| **Task** | T-017, BUILD_PLAN Phase 1 |
| **Status** | ✅ Complete — 13 September 2026 |
| **Branch** | `feat/allowance-and-selection` |
| **Estimated** | 1.5 days |
| **Specification** | `PRD` FR-3, FR-10.1 · `DATA_MODEL` §11.1–11.2 |
| **Behaviour change** | `POST /v1/sessions` exists; free users are capped at 3 cases a month |

---

## 1 · Summary

The first task that makes Nidan a product rather than a demo: the gate between
free and paid, and the rule that the system — not the learner — picks the case.

```
domain/selection.py                  which case, and how much of the month is left
infra/db/repositories/selection.py   candidates · allowance count · case history
api/v1.py                            POST /v1/sessions · allowance on GET /me
config.py                            FREE_TIER_SESSIONS_PER_MONTH = 3
```

**38 new tests.** 540 pass.

---

## 2 · Definition of done

| # | Acceptance criterion | Met by |
|---|---|---|
| 1 | Random published case the user has not completed; falls back to least-recent | `choose_case` + 6 selection tests |
| 2 | Allowance counts every session started this month incl. abandoned | `test_abandoned_sessions_still_count` |
| 3 | Limit reached → 403 `monthly_limit_reached` with `resets_at` | `test_a_free_learner_is_blocked_at_the_limit_with_a_reset_date` |
| 4 | Reserved case does not reroll on refresh | `test_a_started_case_is_reserved_and_does_not_reroll` |

---

## 3 · What was built

### 3.1 The learner does not choose

`PRD` FR-3 gives three reasons and the third is the commercial one:

> free choice lets users avoid uncomfortable specialties, repeat familiar cases,
> and — once answers circulate — pick the one they have been told about.

`choose_case` prefers a case with no history, at random. When every case has
been attempted it returns the least-recently seen, **marked as a repeat**
(FR-3.2) — and the marking is not decoration: a learner not told it is a repeat
will read their own memory of the answer as clinical reasoning.

The randomness is injected (`rng=`) so a test can pin it. It is the only thing
in the module that is not a pure function of its inputs, so it is the only thing
passed in.

### 3.2 `user_case_history` had no writer

The table was created in T-010 and nothing had ever populated it. `BUILD_PLAN`
assigns no task to do so, and criterion 1 — *"a case the user has not
completed"* — is unanswerable without it. T-017 adds `record_attempt`.

`best_verdict` is the part with a trap. "Best" needs a real ordering:

```python
VERDICT_ORDER = ("other", "anchored", "partial", "correct")
```

Alphabetically `'anchored'` precedes `'correct'`, so a `GREATEST()` in SQL or a
bare `max()` in Python records a learner's **worst** attempt as their best —
silently, and only for the learners who improved, which is the group least
likely to complain about it.

### 3.3 The month boundary is the learner's, not the server's

`DATA_MODEL` §11.2 suggests `date_trunc('month', now() AT TIME ZONE :tz)`. That
returns a **naive** timestamp, and comparing it against a `TIMESTAMPTZ` column
shifts the boundary by the UTC offset.

For a learner in Asia/Kolkata, September begins at **18:30 UTC on 31 August**.
Getting it wrong gives them five and a half hours of the wrong month's
allowance — wrong on exactly one day a month, which is the hardest kind of bug
to notice and the easiest to dismiss as a fluke.

So the boundary is computed as a real zone-aware datetime in
`domain/selection.py`, where it can be tested without a database, and passed to
the query as a parameter. A bad value in `profiles.timezone` falls back to UTC
rather than raising: nobody should be blocked from starting a case by a field
they may never have set.

### 3.4 Abandoning still spends it

```sql
SELECT count(*) FROM sessions WHERE started_at >= :since
```

No status filter. `PRD` FR-3's edge cases are explicit — otherwise a free user
could start, abandon and restart without limit, and the cap would mean nothing.

It is also the rule most likely to produce a support email, so the refusal says
so in the message: *"Sessions you started and did not finish count too."*

### 3.5 Blocked at the start, with a date

`PRD` FR-10's edge cases require the block at case start, **never**
mid-consultation. The refusal carries `resets_at`, `limit` and `used` in the
`Error` schema's existing `details` object — a block with no date is a dead end,
and a client cannot compute one.

Pro is unlimited, expressed as `None` rather than a large number so that no
client renders *"999,997 remaining"* and no comparison accidentally exhausts it.

### 3.6 Where the allowance may appear

`PRD` FR-10.2 and P2 together: on the dashboard, **before** starting, never
during a consultation. `GET /me` carries `sessions_remaining_this_month`; no
session payload does, and a test asserts their absence from the session body.

A visible counter during a case teaches the counter — the same argument that
keeps coverage and question counts off the consultation screen.

### 3.7 The reservation is the session row

Criterion 4 needs no new mechanism. The session pins a `case_version_id` when it
is created, so a refresh cannot roll a different case. A second `POST /sessions`
returns **409 `session_already_active`** with the existing session's id, and the
client offers resume-or-abandon — FR-3's edge case wants that to be the client's
decision, not the server's.

---

## 4 · Where we diverged from the specification

**The monthly limit is enforced on `/v1/sessions` only**, not on the
server-rendered prototype — the same decision as T-015's trial limit, taken with
Vraj, for the same reason: the prototype is a local development surface with a
deletion date (T-030), and three cases a month would make authoring and demoing
impossible. It is a surface-based exemption rather than a role-based one, and it
expires when the surface does. After T-030 there is one rule and no bypass;
testing in production is done with Pro accounts, which exercise the code users
actually run.

**The month boundary is computed in Python, not in SQL.** §11.2's `AT TIME ZONE`
form is the naive-timestamp trap described in §3.3.

**`record_attempt` has no production caller yet.** Nothing concludes an
*authenticated* session: the prototype's `/conclude` runs in the anonymous trial
scope, and the JSON consultation API arrives with T-030. The method is written,
tested directly, and used by the selection tests to build history — but the
wiring point does not exist yet, and inventing one would have meant inventing an
endpoint.

---

## 5 · The drafts wall, for the third time

Selection filters `status = 'published'`. **Every seeded case is a draft.**

Migration 019 seeded all five that way on purpose — `DATA_MODEL` §9.2: publishing
them without review would make the publication gate a formality. They stay drafts
until a clinician approves them at **T-023**.

So against the current database, correct selection finds nothing. That is the
gate working, not a defect, and `no_cases_available` already existed in the error
enum for exactly this — FR-3's edge case asks for a friendly error and an admin
alert. `test_no_published_cases_is_a_friendly_503_not_a_crash` pins the
behaviour rather than treating it as an anomaly.

**T-017's headline feature cannot be demonstrated end to end until T-023.** The
tests publish their own fixture cases; the prototype keeps its transitional
resolver. This is the third task to hit the same wall, which is worth noting as a
pattern: the publication gate is doing real work, and the content path is the
constraint `BUILD_PLAN` §11.1 always said it was.

---

## 6 · Two probes, and one that proved nothing

Each new guard was checked by breaking what it guards:

| Break | Tests that caught it |
|---|---|
| Rank verdicts by string comparison | 1 |
| Compute the month boundary in UTC, ignoring the learner's zone | 2 |
| Offer any case, ignoring history | **0 → 4** |

The third reported zero failures, which would have meant the history filter was
untested. It was not: the probe's search string used single quotes where the
source has double, so the replacement silently did nothing and the "probe" ran
against unmodified code.

**A probe that changes nothing is indistinguishable from a test that catches
nothing.** The retry asserts the target string is present before replacing it,
and then four tests fail as they should. The same assertion has now earned its
place twice — `test_fails_when_a_detector_is_degraded` has carried it since
T-004, and T-016 found its sibling *without* one had been silently degrading
nothing for months.

---

## 7 · A test that deleted its own fixture

`test_a_case_already_attempted_is_not_offered_while_others_remain` truncated
between iterations to clear sessions, using the shared `_DATA_TABLES` list.

That list includes `user_case_history` — the history the test had just written,
and the entire subject of the test. It failed with the already-seen case being
offered, which looked exactly like a broken selection query.

Rewritten to use a Pro account (so three sessions do not exhaust the loop) and
to abandon rather than truncate. The shared list was the right instinct — it is
what T-013 learned — but it is a list of *everything disposable*, and this test
had made one of those tables precious.

---

## 8 · Verification

```
pytest                          540 passed        (was 502)
pytest tests/db -q --no-cov     165 passed        (was 149)
ruff check .                    All checks passed
mypy nidan/domain --strict      Success: no issues found in 15 source files
lint-imports                    2 contracts kept, 0 broken
python validate_detectors.py    PASS: 94.4%
```

| File | Tests | Defends |
|---|---|---|
| `tests/domain/test_selection.py` | 22 | selection, month boundaries, verdict ranking — **no database** |
| `tests/db/test_allowance.py` | 16 | the four criteria through real requests, and FR-3.4's leak rule |

---

## 9 · What this changes for you

**Nothing about the prototype.** Still unlimited, still five cases.

**`POST /v1/sessions` exists**, and enforces the cap. Free is 3 a month, set by
`FREE_TIER_SESSIONS_PER_MONTH` — configured, not schema, because it is a pricing
decision and pricing changes faster than migrations should.

**`GET /v1/me` now reports `sessions_remaining_this_month`** — `null` for Pro.

---

## 10 · Known debt left behind

**`ORDER BY random()`** is fine at five cases and a sequential scan at ten
thousand. Correct now; revisit when the catalogue grows.

**No admin alert on `no_cases_available`.** FR-3's edge case asks for one;
alerting arrives with the operational work in Phase 4.

**`record_attempt` is unwired**, as above — T-030.

**Retry-a-case for Pro users (FR-3 user story) is not implemented.** Selection
always chooses; deliberate choice of a past case is a separate endpoint.

---

## 11 · How to undo it

```bash
git revert <commit>
```

No migration. `user_case_history` rows already written stay valid.

---

## 12 · Next

**T-018 · Pilot data backfill**, then T-019 and T-020 close Phase 1.

The larger point from §5 stands: **T-023 is the gate that matters**. Until the
clinical review workflow exists, no case can be published, selection has nothing
to select, and your two clinician reviewers cannot look at a case at all —
which `BUILD_PLAN` §2.1 already calls the gate that matters more than it looks.
