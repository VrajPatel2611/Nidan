# T-018 · Pilot data backfill

| | |
|---|---|
| **Task** | T-018, BUILD_PLAN Phase 1 |
| **Status** | ✅ Complete — 13 September 2026 |
| **Branch** | `feat/pilot-backfill` |
| **Estimated** | 1 day |
| **Specification** | `DATA_MODEL` §9.3 |
| **Behaviour change** | None to the app. A run-once script imports the pilot |

---

## 1 · Summary

The pilot lived in 16 JSON files beside the code. It now lives in the schema.

```
sessions/*.json  →  8 profiles      (email NULL, research_pid = P01…P08)
                 →  16 sessions     (completed, sequence from the pilot)
                 →  417 events      (synthesised, marked "backfilled")
                 →  16 results      (verbatim, under engine pilot-2026-07)
                 →  16 feedback rows · 16 case-history rows
```

**15 new tests.** 555 pass. Also a labelling pass across `README.md` and
`PROJECT_MAP.md`, requested alongside this task.

---

## 2 · Definition of done

| # | Acceptance criterion | Met by |
|---|---|---|
| 1 | 16 sessions imported with 8 profiles keyed on `research_pid` | `test_sixteen_sessions_and_eight_participants_are_imported` |
| 2 | Synthesised events carry `provenance: "backfilled"` | `test_every_synthesised_event_is_marked_backfilled` |
| 3 | Results match the original JSON exactly | `test_every_result_matches_the_original_json` |
| 4 | Idempotent — re-running creates no duplicates | `test_running_it_twice_changes_nothing` |

---

## 3 · What was built

### 3.1 The point of the whole exercise

Today's engine does not reproduce one of the sixteen. T-016 found it and traced
it: P07's case 2 is the pulmonary embolism case, the learner asked about a
*"travel bug on the flight"*, and the pilot-era anchor keyword list contained
`"travel bug"` — so the question that pointed **at** the correct diagnosis was
counted as evidence of anchoring. The keyword was removed under invariant C-4.

After this import, **both numbers are in the database and both are correct**:

```
P07  pilot-2026-07   anchoring = 0.710  detected = true
     (engine 1.0.0)  anchoring = 0.000  detected = false
```

Each is attached to the engine version that produced it. `DATA_MODEL` §6.4 said
`engine_versions` would make exactly this *"a query rather than a forensic
exercise"*; this is the task where that stops being a claim about a table and
becomes a row you can select.

**Results are inserted verbatim, never recomputed.** Recomputing would overwrite
the published record with today's numbers and destroy the evidence — including
the one case in the pilot where a learner was marked down for asking the best
question available to them. The `pilot-2026-07` row carries a `notes` field
explaining precisely why it differs, so the reason travels with the data rather
than living in a build log.

### 3.2 Idempotency is a consequence, not a mechanism

Every id is `uuid5` of the source data — `stable_id("profile", "P01")`,
`stable_id("session", filename)` — from a fixed namespace constant. A second run
computes the same ids and upserts the same rows.

That also makes a *failed half-run* safe: re-running addresses the same rows
rather than creating a second copy. `session_events` is the exception, since the
append-only trigger refuses UPDATE and DELETE — so the events step is
skip-if-present rather than an upsert.

### 3.3 Provenance, and a contract that had to widen

`DATA_MODEL` §9.3 requires `"provenance": "backfilled"` in every synthesised
payload. **T-013's validator refused it**, because unknown keys are rejected —
which is the unknown-key rule working exactly as designed, and directly in the
way of the spec.

`provenance` is now an allowed optional key on every event type. The alternative
was letting the backfill skip validation, and a script that bypasses the
validator is a script that can write malformed events into an append-only table.

The marker earns its place immediately. Against the local stack after the
import:

```
events by provenance:
   backfilled     417
   (live)          19
```

Those 19 are from the gunicorn verification in T-013. The warning in §9.3 —
*backfilled timestamps are synthetic and must be excluded from any timing
analysis* — is only actionable because the two are distinguishable, and zero
unmarked events belong to a backfilled session.

### 3.4 It does not run as the application

The first run failed:

```
permission denied for table engine_versions
```

Migration 020 grants the application role SELECT on clinical and engine content
and nothing more, deliberately. The obvious fix — widen the grant — would also
widen it for `nidan_service`, which is the role the **anonymous-trial path**
runs as. That is far too high a price for a run-once import.

So the backfill connects as the migrating user, like alembic does. It is an
operator task, not a request, and it writes two things the application must
never write: `engine_versions`, and `auth.users`.

That second one is worth flagging. `profiles.id` references `auth.users`, which
**Supabase owns in production**. The pilot participants have no account and
never will — no email, no credentials, nobody can sign in as them — so the auth
row is a placeholder that exists only to satisfy the foreign key. It is written
in one clearly-marked function, which is the line to replace with Supabase's
admin API if this is ever run against a live project.

### 3.5 Small mappings, each of which fails loudly if missed

| JSON | Column | |
|---|---|---|
| `year_of_study: "year_3"` | `year_of_training SMALLINT CHECK 1–10` | parse the digit |
| `confidence_pre: "3"` | `confidence_pre SMALLINT` | string → int |
| `participant_id: "P01"` | `research_pid TEXT UNIQUE` | direct |

---

## 4 · Where we diverged from the specification

**The scorecards are the pilot's `clinical_eval` blocks, not §8.6's shape.**
Rebuilding them would be recomputation, and criterion 3 says the results match
the original JSON exactly.

**`bias_detail` has no `counters` and no `rule_fired`.** Both were added in
T-016, so these sixteen rows are the only ones in the table without them. A
reader that assumes §8.5's current shape will break on exactly the oldest data —
worth knowing before writing that reader, and recorded here rather than
discovered later.

**The import is not run in production by default.** Whether real participants'
data belongs in the production database is a privacy decision, not an
engineering one. Run locally and in staging; decide separately, closer to launch.
Agreed with Vraj.

**The drafts wall did not block this**, for the first time in four tasks.
`sessions.case_version_id` has no published requirement, so backfilled sessions
point at the seeded draft versions perfectly well.

---

## 5 · The labelling pass

Requested alongside this task: make it obvious which parts of the repository are
product and which are research.

Rather than moving or deleting anything, `README.md` and `PROJECT_MAP.md` now
open with the same three-way split — **product · research · process** — and
state the fact that settles the question:

> The deployed artefact is the container image, and it contains only `nidan/`.

The Dockerfile copies `pyproject.toml`, `README.md` and `nidan/`, and nothing
else. The separation already existed at the boundary that decides what runs.

Deleting the research from the repository was considered and rejected for three
reasons: `sessions/*.json` is a **test input** read on every push by
`test_golden_assessment.py`, so removing it would delete the test that protects
the published claim; deleting a folder does not remove it from git history, and
rewriting history would break every clone and every PR reference; and for a
final-year project the repository is part of what is submitted, where the paper
and the pilot data are evidence rather than clutter.

**Seven stale references were fixed while in there.** The README credited
*Gemini 2.5 Flash* and told readers to get a Gemini API key — the model changed
to Llama 3.3 70B via Groq in Phase 0 (`ADR-0011`). Its "Project Structure"
section still described the pre-T-001 layout (`app.py`, `bias_detector.py` at
the root), none of which has existed for sixteen tasks.

---

## 6 · A probe that appeared to prove nothing, one level up

Three probes, each breaking something the tests guard:

| Break | Result |
|---|---|
| Drop the provenance marker | 1 failure |
| Store a wrong score instead of the published one | 2 failures |
| **Non-deterministic ids (breaks idempotency)** | **"0 failures"** |

The third looked like an untested guard. It was not: the probe produced **14
errors**, not failures — a `UNIQUE` violation on `research_pid` raised inside
the fixture, and pytest reports fixture failures as ERROR. My
`grep -c "^FAILED"` counted zero.

T-017 recorded a probe whose *mutation* silently did nothing. This one's
mutation worked perfectly and the *measurement* was wrong. Same lesson, one
level up: **the probe has to be checked as carefully as the thing it probes.**

---

## 7 · Verification

```
pytest                          555 passed        (was 540)
pytest tests/db -q --no-cov     180 passed        (was 165)
ruff check .                    All checks passed
mypy nidan/domain --strict      Success
lint-imports                    2 contracts kept, 0 broken
```

And run for real against the local stack:

```
Imported the pilot:
  profiles   16      sessions   16      events    417
  results    16      feedback   16      history    16
```

```
participants : 8
sessions     : 16 backfilled + 2 from the T-013 gunicorn run
verdicts     : {'correct': 12, 'anchored': 3, 'other': 1}
```

The verdict distribution matches the pilot exactly.

---

## 8 · What this changes for you

**Your pilot is now queryable.** Eight participants, sixteen consultations,
their events, results, feedback and case history — in the same schema the
product uses.

**Phase 2 gets real data.** The admin console, history and progress screens are
built against sixteen genuine consultations rather than fixtures. Fixture data
agrees with whatever you built; real data argues back.

**Nothing about running the app changes.** The script is run-once and separate.

---

## 9 · Known debt left behind

**The synthesised log is block-ordered.** The JSON preserved questions,
examinations and investigations as separate blocks but not their interleaving,
so the order is plausible rather than true, and the timestamps are one second
apart. Hence the provenance marker and the warning attached to it.

**Sixteen rows lack `counters` and `rule_fired`**, as above.

**`auth.users` placeholder rows** would need Supabase's admin API to run against
a live project.

**Per-question topic attribution is unrecoverable** — the aggregate is all the
pilot format kept, so every topic is attached to the first reply.

---

## 10 · How to undo it

```sql
DELETE FROM profiles WHERE research_pid LIKE 'P0%';   -- cascades to sessions,
                                                      -- events, results, feedback
DELETE FROM engine_versions WHERE version = 'pilot-2026-07';
```

`ON DELETE CASCADE` from `profiles` removes everything the import created. The
JSON files are untouched and remain the source of truth.

---

## 11 · Next

**Phase 1 is nearly closed.** Then Phase 2 — and `BUILD_PLAN` calls it *"the
milestone that matters most"*:

> **Goal:** clinicians can review cases without reading code.

**T-023 is the gate.** Until the clinical review workflow exists, no case can be
published, selection has nothing to select, your two clinician reviewers cannot
look at a case at all, and content authoring — which §11.1 rates the real
critical path — cannot start in earnest. Four tasks have now hit that wall.
