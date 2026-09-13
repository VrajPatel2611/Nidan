# Nidan — Build Plan

---

## Contents

**1. Document control**

&nbsp;&nbsp;&nbsp;&nbsp;1.1 How to use this  
&nbsp;&nbsp;&nbsp;&nbsp;1.2 Task format  
&nbsp;&nbsp;&nbsp;&nbsp;1.3 Global definition of done  
**2. Critical path**

&nbsp;&nbsp;&nbsp;&nbsp;2.1 The gate that matters most  
**3. Parallelisation**

**4. Phase 0 — Foundation**

**5. Phase 1 — Persistence and accounts**

**6. Phase 2 — Admin console P0**

**7. Phase 3 — API and web app**

**8. Phase 4 — Commercial readiness**

**9. Phases 5–7 — post-launch**

**10. Schedule summary**

&nbsp;&nbsp;&nbsp;&nbsp;10.1 Minimum viable cut  
**11. Risks to the plan**

&nbsp;&nbsp;&nbsp;&nbsp;11.1 The risk I would watch  

---

---

# 1. Document control

| Field | Value |
|---|---|
| **Document** | Nidan Build Plan |
| **Version** | v1.0 |
| **Status** | Draft |
| **Team** | Vraj Patel, Yogesh Bagotia (+ AI assistance) |
| **Depends on** | `PRD.md` · `UX_SPEC.md` · `DATA_MODEL.md` · `API_CONTRACT.md` |

## 1.1 How to use this

This is the working document. Tasks are executed in dependency order; each carries acceptance criteria precise enough that "is it done?" is never a discussion.

**Estimates assume two developers with AI assistance.** They are the *implementation* estimate only — they exclude clinical content authoring (`PRD` D-2), which runs in parallel and is not engineering work.

## 1.2 Task format

```
T-nnn · Title
  Phase       which phase
  Depends     task ids that must complete first
  Files       primary files created or changed
  Spec        the authoritative spec section
  Accept      testable criteria — all must pass
  Tests       what must exist and pass
  Est         developer-days
  Owner       suggested (V = Vraj, Y = Yogesh, either)
```

## 1.3 Global definition of done

A task is **not** done until all of these hold:

1. Code merged to `main` via pull request
2. Unit tests written and passing; `domain/` coverage ≥ 90 %
3. `ruff` and `mypy` clean
4. **`DATA_MODEL.md` updated in the same PR** if the schema changed
5. **`openapi.yaml` updated in the same PR** if an endpoint changed
6. The detector-validation gate still reports ≥ 94 %
7. No new `TODO` without a linked task id

---

# 2. Critical path

The chain that determines the earliest possible launch. Everything else can slip without moving the date.

```
T-001 package restructure
   └─ T-004 CI + validation gate
        └─ T-010 schema + migrations
             └─ T-013 event-sourced sessions
                  └─ T-016 assessment from events
                       └─ T-021 case editor
                            └─ T-022 playtest
                                 └─ T-023 clinical review        ← clinicians unblocked
                                      └─ T-030 JSON API
                                           └─ T-034 consultation screen
                                                └─ T-036 feedback screen
                                                     └─ T-041 Stripe
                                                          └─ T-045 launch
```

**Critical-path total ≈ 52 days.** Total effort ≈ 74 days, so ~22 days of work can run in parallel.

## 2.1 The gate that matters most

**T-023 (clinical review workflow) unblocks your two clinician reviewers.** Until it exists, only a programmer can look at a case, and content authoring — which is on its own critical path for `PRD` D-2 — cannot start in earnest.

**Pull T-021 → T-023 as early as dependencies allow.** They are scheduled in Phase 2 for that reason, ahead of the consumer app.

---

# 3. Parallelisation

Two developers, minimal collision. The split follows the layering in `ADR-0009`.

| Track | Owner | Scope |
|---|---|---|
| **Backend / data** | Vraj | Schema, domain layer, assessment engine, API, LLM gateway |
| **Frontend / admin** | Yogesh | Next.js app, admin console, UX implementation |
| **Shared** | Both | Phase 0, contract tests, deployment |

### Where the tracks meet

Three synchronisation points. Everything else is independent.

| # | Point | Contract |
|---|---|---|
| S-1 | After T-011 | `openapi.yaml` exists → frontend can mock and build against it |
| S-2 | After T-030 | Real API live → frontend switches from mocks |
| S-3 | Before T-045 | End-to-end verification together |

**S-1 is the important one.** Once `openapi.yaml` is committed, the frontend generates types and builds against a mock server — Yogesh is not blocked on Vraj finishing endpoints.

---

> **A note on paths.** File paths below say `nidan/`. Tasks T-001 to T-007 were
> executed when the package was called `vpsim/`; it was renamed on 11 September
> 2026 (`PRD` D-8). This document is the forward-looking contract, so it uses
> current paths throughout. The record of what was actually built, under the old
> name, is in `docs/build-log/`.

# 4. Phase 0 — Foundation

**Goal:** existing behaviour under test, reproducible build, CI enforcing the research claim.
**Effort:** 8 d · **Blocks:** everything

---

**T-001 · Restructure into a `nidan/` package** — ✅ **DONE** (2026-09-05)
```
Phase    0            Depends  —              Est  2 d      Owner  V
Files    nidan/{api,domain,infra,web}/, pyproject.toml
Spec     TECH_SPEC §4.1 · ADR-0009
Accept   1. Existing modules moved: cases→domain/content, bias_detector→domain/assessment/bias,
            clinical_evaluator→domain/assessment/clinical, session_tracker→domain/assessment/topics
         2. domain/ imports nothing from infra/ or api/
         3. `python -m nidan` starts the app with all existing routes working
         4. validate_detectors.py still reports 94% unchanged
Tests    Smoke test hitting every existing route
Done     tests/test_smoke.py (11 route tests) · tests/test_layering.py · import-linter
         contract in pyproject.toml · validation re-run: 94% (51/54), unchanged
```

**T-002 · Test harness and fake LLM gateway** — ✅ **DONE** (2026-09-05)
```
Phase    0            Depends  T-001          Est  2 d      Owner  V
Files    tests/conftest.py, tests/fakes/llm.py
Spec     TECH_SPEC §12
Accept   1. Fake gateway returns canned replies; no test makes a network call
         2. Time is injected; no datetime.now() in domain/
         3. Unit tests for all three detectors, ≥ 90% coverage on domain/assessment
         4. Property tests: a ≤ q; scores ∈ [0,1]; detected ⇒ score > 0
Tests    pytest -m "not slow" green
Done     215 tests (was 53). domain/assessment coverage 100%, domain 99.6%.
         FOUND 2 LIVE DETECTOR BUGS: anchor "mi" matched examine/vomiting;
         alternative "gi" matched angina. Added invariants C-8, C-9.
```

**T-003 · Lexicon disjointness test** ⭐ — ✅ **DONE** (2026-09-05)
```
Phase    0            Depends  T-002          Est  0.5 d    Owner  V
Files    tests/test_case_invariants.py
Spec     DATA_MODEL §8.1 C-4
Accept   1. For every case: anchor_keywords ∩ (any contradictory_clues entry) = ∅
         2. Test fails loudly with the offending terms named
         3. Also asserts C-1,C-2,C-3,C-5,C-6,C-7
Note     This is the test that would have caught the 14%-sensitivity bug before it shipped.
Done     tests/test_case_invariants.py — 36 tests (7 invariants x 5 cases + guard).
         FOUND A LIVE C-4 VIOLATION: case_1 anchor "heart" vs clue "heartburn".
         Built before T-002; the stated dependency does not exist. See build log.
```

**T-004 · CI pipeline with the validation gate** ⭐ — ✅ **DONE** (2026-09-05)
```
Phase    0            Depends  T-002          Est  1 d      Owner  V
Files    .github/workflows/ci.yml, .importlinter
Spec     SECURITY_SPEC §5.1 · TECH_SPEC §9.3
Accept   1. On PR: ruff, mypy(domain strict), import-linter, pytest, pip-audit, gitleaks
         2. Runs validate_detectors.py; BUILD FAILS if accuracy < 94%
         3. Docker image builds
         4. All checks required before merge
Note     The research claim becomes a CI check. No refactor can silently degrade the instrument.
Done     6 CI jobs. validate_detectors.py now EXITS NON-ZERO below 94% (it always
         exited 0 before). Criterion 4 needs a manual repo setting — see
         .github/BRANCH_PROTECTION.md. FOUND: session saving broken since T-001;
         dead google-auth dependency carrying every CVE.
```

**T-005 · Docker + docker-compose** — ✅ **DONE** (verified 2026-09-06)
```
Phase    0            Depends  T-001          Est  1 d      Owner  V
Files    Dockerfile, docker-compose.yml, .dockerignore
Spec     TECH_SPEC §9.1
Accept   1. Multi-stage build; non-root user; healthcheck
         2. compose brings up app + Postgres 16 with pgvector
         3. `docker compose up` gives a working app on a clean machine
Done     Built and run 2026-09-06. PostgreSQL 16.15 + vector 0.8.6 confirmed;
         all routes 200. Port clash with local postgresql@15 solved by the
         POSTGRES_PORT override. Fixed: gunicorn --access-logfile duplicated
         every request in plain text (only visible in a container).
```

**T-006 · Typed configuration** — ✅ **DONE** (2026-09-05)
```
Phase    0            Depends  T-001          Est  1 d      Owner  V
Files    nidan/config.py, .env.example
Spec     TECH_SPEC §9.4
Accept   1. pydantic-settings; app fails fast on boot with a clear message if config is invalid
         2. No secret literal anywhere in the repo (gitleaks green)
         3. .env.example documents every variable
Done     nidan/config.py (pydantic-settings, 6 fields). Invalid config exits 78
         with a message naming the variable. Secret scan: every blob in git
         history, 0 hits. A test fails if .env.example misses a field.
```

**T-007 · Structured logging and Sentry** — ✅ **DONE** (2026-09-05)
```
Phase    0            Depends  T-006          Est  0.5 d    Owner  V
Files    nidan/infra/telemetry/
Spec     TECH_SPEC §10
Accept   1. JSON logs to stdout with request_id, session_id, user_id
         2. Raw question text never logged at INFO; no emails, no keys
         3. Sentry wired, send_default_pii=False, release tagged
Done     nidan/infra/telemetry/. JSON to stdout, contextvar correlation ids,
         redaction, /healthz + /readyz. End-to-end test drives a consultation
         and greps the output for the learner's own words. PHASE 0 COMPLETE.
```

---

# 5. Phase 1 — Persistence and accounts

**Goal:** no data loss on restart; multiple workers safe; accounts real.
**Effort:** 16 d

---

**T-010 · Schema and migrations** — ✅ **DONE** (2026-09-11)
```
Phase    1            Depends  T-005          Est  3 d      Owner  V
Files    nidan/infra/db/models.py, migrations/versions/001..018
Spec     DATA_MODEL §4–7, §9.1
Accept   1. All 19 v1 tables created by migrations 001–018 in order
         2. All constraints present incl. owner_is_exclusive, one_published_version_per_case,
            one_active_sub_per_user
         3. Append-only triggers on session_events and audit_log raise on UPDATE/DELETE
         4. require_clinical_approval trigger blocks publishing without an approving review
         5. `alembic downgrade base` then `upgrade head` succeeds on an empty database
Tests    testcontainers Postgres; one test per constraint asserting it actually rejects
Done     16 migrations (001-016), 21 tables, 6 enums, 11 triggers, 5 RLS policies.
         37 database tests: constraints, append-only triggers, publication gate,
         RLS denial as a non-superuser, and the downgrade/upgrade round-trip.
         017-018 are seed data and belong to T-011. NOTE: criterion 1 says 19
         tables; DATA_MODEL §4-7 defines 21.
```

**T-011 · Seed content and `openapi.yaml` skeleton** ⭐ *(sync point S-1)* — ✅ **DONE** (2026-09-12)
```
Phase    1            Depends  T-010          Est  2 d      Owner  V
Files    migrations/017,018, openapi.yaml
Spec     DATA_MODEL §9.2 · API_CONTRACT
Accept   1. 27 examinations, 86 investigations, 40 topics, 523 phrases seeded from cases.py
         2. Engine version 1.0.0 seeded with current thresholds, is_current=true
         3. 5 existing cases migrated as case_versions v1, status='draft'
         4. openapi.yaml committed with all v1 paths and schemas (may return 501)
Note     Unblocks the frontend track. Do not let this slip.
Done     Migrations 017 (27/86/40/523 seeded), 018 (engine 1.0.0), 019 (5 cases
         as v1 DRAFT). openapi.yaml: 18 paths, 22 operations, 28 error codes.
         Found and fixed a T-010 test-fixture bug that truncated the newly
         seeded cases. Yogesh can now generate a client and start T-032.
```

**T-012 · Repository layer and tenant scoping** — ✅ **DONE** (2026-09-12)
```
Phase    1            Depends  T-010          Est  2 d      Owner  V
Files    nidan/infra/db/repositories/
Spec     TECH_SPEC §4.1
Accept   1. Repository base requires an actor context; no query bypasses it
         2. RLS policies applied and tested — a second user's rows are invisible
         3. Anonymous-session path isolated and separately tested
```

**T-013 · Event-sourced session state** ⭐ — ✅ **DONE** (2026-09-12)
```
Phase    1            Depends  T-012          Est  3 d      Owner  V
Files    nidan/domain/session.py, nidan/infra/db/repositories/session.py
Spec     ADR-0003 · DATA_MODEL §6.2
Accept   1. SESSION_STORE deleted entirely
         2. Every action appends an event before the response is returned
         3. UNIQUE(session_id, seq) collision retried cleanly, never interleaved
         4. Killing the process mid-consultation loses nothing; resume works
         5. App runs with 2 gunicorn workers with no session bleed
Tests    Concurrency test: 10 parallel appends produce seq 1..10 with no gaps or duplicates
```

**T-014 · Supabase Auth integration** — ✅ **DONE** (2026-09-13)
```
Phase    1            Depends  T-012          Est  2 d      Owner  V
Files    nidan/api/auth.py, nidan/infra/auth/
Spec     ADR-0002 · API_CONTRACT §2.2, §3
Accept   1. JWT verified against JWKS, cached 10 min
         2. @require_auth and @require_tier('pro') decorators
         3. Expired token → 401 token_expired
         4. Profile created on POST /me, idempotent
         5. Backend never handles a password
```

**T-015 · Anonymous trial sessions** — ✅ **DONE** (2026-09-13)
```
Phase    1            Depends  T-013,T-014    Est  1.5 d    Owner  V
Files    nidan/api/trial.py
Spec     PRD FR-2 · DATA_MODEL §6.1
Accept   1. POST /trial/sessions creates a session with anonymous_id, sets httpOnly cookie
         2. One trial per browser; second attempt → 409 trial_already_used
         3. POST /me with anonymous_id claims it within 30 days; 422 after
         4. owner_is_exclusive constraint never violated
```

**T-016 · Assessment from events** ⭐
```
Phase    1            Depends  T-013          Est  2 d      Owner  V
Files    nidan/domain/assessment/engine.py
Spec     TECH_SPEC §4.4 · DATA_MODEL §6.3–6.4
Accept   1. assess(events, case_content, engine_version) is a pure function
         2. Thresholds read from engine_versions, not from constants in code
         3. session_results written with engine_version_id
         4. bias_detail includes counters (DATA_MODEL §8.5)
         5. Replaying the same events yields byte-identical results
Tests    Golden-file test over the 16 pilot sessions asserting stored == recomputed
```

**T-017 · Free-tier allowance and case selection**
```
Phase    1            Depends  T-014          Est  1.5 d    Owner  V
Files    nidan/domain/selection.py
Spec     PRD FR-3, FR-10.1 · DATA_MODEL §11.1–11.2
Accept   1. Random published case the user has not completed; falls back to least-recent
         2. Allowance counts every session started this month incl. abandoned
         3. Limit reached → 403 monthly_limit_reached with resets_at
         4. Reserved case does not reroll on refresh
```

**T-018 · Pilot data backfill**
```
Phase    1            Depends  T-016          Est  1 d      Owner  V
Files    scripts/backfill_pilot.py
Spec     DATA_MODEL §9.3
Accept   1. 16 sessions imported with 8 profiles keyed on research_pid
         2. Synthesised events carry provenance:"backfilled"
         3. Results match the original JSON exactly
         4. Idempotent — re-running creates no duplicates
```

---

# 6. Phase 2 — Admin console P0

**Goal:** clinicians can review cases without reading code.
**Effort:** 11 d · **This is the milestone that matters most.**

---

**T-020 · Admin shell and auth**
```
Phase    2            Depends  T-014          Est  1 d      Owner  Y
Files    nidan/web/admin/
Spec     UX_SPEC §12 · ADR-0006
Accept   1. Jinja + HTMX shell, admin-only, desktop-only
         2. Every admin action writes to audit_log
```

**T-021 · Case editor** ⭐
```
Phase    2            Depends  T-020,T-011    Est  5 d      Owner  Y
Files    nidan/web/admin/cases/
Spec     UX_SPEC §12 A-02 · DATA_MODEL §8.1 · API_CONTRACT §9
Accept   1. Sectioned form: patient, truth, trap, history, clues, exams, investigations, persona
         2. Editing a published version creates a new draft; published content immutable
         3. Live validation of C-1..C-7; SAVE IS BLOCKED on C-4 with the overlapping terms named
         4. Unsaved-changes guard on navigate away
         5. Token counter on the persona prompt
Note     C-4 enforcement here is the structural fix for the 14%-sensitivity class of bug.
```

**T-022 · Playtest with live instrumentation** ⭐
```
Phase    2            Depends  T-021,T-016    Est  4 d      Owner  Y
Files    nidan/web/admin/playtest/
Spec     UX_SPEC §12 A-03
Accept   1. Split view: student UI left, instrumentation right
         2. Right panel shows per-question matched topics, counters (q,a,m,c,k/K),
            live detector state, and clues explored
         3. Leakage warning appears when a reply reveals an unasked required topic
         4. Ephemeral — playtest sessions never appear in user data or analytics
         5. Reset without leaving the page
Note     This is how a non-programmer sees WHY a detector fired. Highest-value admin screen.
```

**T-023 · Clinical review workflow** ⭐
```
Phase    2            Depends  T-022          Est  2 d      Owner  Y
Files    nidan/web/admin/reviews/
Spec     PRD FR-12.4–12.5 · DATA_MODEL §5.2, §8.4
Accept   1. Assign a version to a reviewer; reviewer opens it in Playtest
         2. Rubric 1–5 on plausibility, consistency, trap validity, solvability
         3. approve / changes_requested / rejected with comments
         4. Any dimension < 4 cannot be recorded as approved
         5. Publish is blocked without an approving review (409, and the DB trigger holds)
Note     Completing this unblocks your two clinician reviewers. Pull it as early as possible.
```

---

# 7. Phase 3 — API and web app

**Goal:** a real product a user can use.
**Effort:** 22 d

---

**T-030 · JSON API** ⭐ *(sync point S-2)*
```
Phase    3            Depends  T-016,T-017    Est  6 d      Owner  V
Files    nidan/api/v1/
Spec     API_CONTRACT §4–8
Accept   1. Every v1 endpoint implemented per openapi.yaml
         2. Error envelope on every 4xx/5xx; all codes in the §10 catalogue
         3. Idempotency-Key honoured on /diagnosis
         4. Cursor pagination on collections
         5. Rate limits enforced per API_CONTRACT §2.9
Tests    Contract tests CT-1..CT-9 (API_CONTRACT §11) — CT-1 and CT-5 are mandatory
```

**T-031 · LLM gateway hardening**
```
Phase    3            Depends  T-006          Est  2 d      Owner  V
Files    nidan/infra/llm/
Spec     TECH_SPEC §4.3 · ADR-0011
Accept   1. Per-purpose model routing (patient / feedback / extraction / judge)
         2. Exponential backoff with jitter; circuit breaker after N failures
         3. Every call writes an llm_calls row with tokens, cost, latency
         4. Provider swap is a config change, no code change
         5. Failure on /questions returns 503 patient_unavailable WITHOUT consuming the question
```

**T-032 · Next.js scaffold and auth**
```
Phase    3            Depends  T-011          Est  4 d      Owner  Y
Files    web/
Spec     ADR-0006 · UX_SPEC §3
Accept   1. Next.js + TypeScript; design tokens from UX_SPEC §3.1–3.4 as CSS variables
         2. Types generated from openapi.yaml; CI fails if stale
         3. Supabase auth flow: signup, login, reset, verification (S-02..S-06)
         4. Component library per UX_SPEC §3.5
```

**T-033 · Dashboard and onboarding**
```
Phase    3            Depends  T-032          Est  3 d      Owner  Y
Spec     UX_SPEC S-07, S-08
Accept   1. All four dashboard states: empty, normal, limit reached, unfinished session
         2. Onboarding two steps, skippable
         3. Allowance shown on dashboard only, never during a consultation
```

**T-034 · Consultation screen** ⭐
```
Phase    3            Depends  T-030,T-032    Est  6 d      Owner  Y
Spec     UX_SPEC S-09, S-10, S-11
Accept   1. Three-pane at lg, two-pane at md, blocking message below 768px
         2. All states: idle, awaiting, error, cap reached, blocked input, resuming
         3. Failed reply preserves the typed question and offers retry
         4. NONE PRESENT: question counter, coverage meter, suggested questions, timer
         5. Investigation search filters by name only, never ranked by relevance
         6. Diagnosis modal contains no readiness or completeness hint
         7. Keyboard accessible; conversation is aria-live
Note     Criteria 4–6 are the U2 guarantees. A reviewer should check them explicitly.
```

**T-035 · Real-patient-data guard**
```
Phase    3            Depends  T-034          Est  1 d      Owner  V
Spec     PRD FR-4 · UX_SPEC S-10 · PRD P4
Accept   1. Detects identifiers, DOBs, hospital numbers, named individuals with clinical detail
         2. Blocks the question; 422 patient_data_detected; question NOT consumed
         3. input_blocked event logged with reason only, never the text
```

**T-036 · Feedback screen** ⭐
```
Phase    3            Depends  T-030,T-032    Est  3 d      Owner  Y
Spec     UX_SPEC S-12, S-13
Accept   1. Eight sections in the specified order
         2. Reasoning headings are Diagnostic focus / History completeness / Evidence exploration
         3. Banned vocabulary absent — automated copy test over rendered output
         4. Answer collapsed until requested
         5. Fallback feedback renders identically, with no apology
         6. "Was this helpful?" control writes a rating
```

**T-037 · History and progress**
```
Phase    3            Depends  T-036          Est  3 d      Owner  Y
Spec     UX_SPEC S-14, S-15, S-16
Accept   1. Paginated history; session detail reuses the feedback layout read-only
         2. Progress requires ≥ 3 sessions; empty state below that
         3. Decline shown neutrally, no alarm styling
```

---

# 8. Phase 4 — Commercial readiness

**Goal:** can take money and can be launched safely.
**Effort:** 17 d

---

**T-040 · Leakage monitor** ⭐
```
Phase    4            Depends  T-030          Est  3 d      Owner  V
Spec     TECH_SPEC §5.3 · DATA_MODEL §7.2
Accept   1. Post-reply check flags topics revealed but not asked
         2. leakage_flags rows with severity; admin queue to confirm or dismiss
         3. Confirmed leaks excluded from the research export (DATA_MODEL §11.7)
         4. Adversarial CI suite: fixed extraction prompts run against every case persona;
            a case whose persona leaks a key fact fails the build
Note     Largest threat to measurement validity and currently invisible.
```

**T-041 · Stripe subscriptions**
```
Phase    4            Depends  T-030          Est  4 d      Owner  V
Spec     PRD FR-10 · API_CONTRACT §8
Accept   1. Checkout, portal, webhooks for all five events
         2. Webhooks idempotent by Stripe event id
         3. Regional pricing resolved server-side from country
         4. 7-day grace on payment failure; cancel retains access to period end
         5. one_active_sub_per_user never violated under duplicate webhooks
Tests    Stripe CLI replay incl. duplicate and out-of-order delivery
```

**T-042 · Pricing and account screens**
```
Phase    4            Depends  T-041,T-032    Est  3 d      Owner  Y
Spec     UX_SPEC S-17..S-20
Accept   1. Pricing with monthly/annual toggle; copy describes what Pro adds
         2. Checkout return states: success, cancelled, pending
         3. Settings incl. research consent, default off
         4. Deletion requires typing DELETE; states exactly what is retained
```

**T-043 · AI usage and cost dashboard**
```
Phase    4            Depends  T-031,T-020    Est  2 d      Owner  Y
Spec     TECH_SPEC §10.1 · UX_SPEC A-07
Accept   1. Spend today/month vs budget; cost per completed session
         2. Tokens, latency p50/p95, error and fallback rates by model
         3. Budget alert at 80%; automatic degradation to cheapest model at 100%
```

**T-044 · Master list and lexicon editors**
```
Phase    4            Depends  T-020          Est  3 d      Owner  Y
Spec     UX_SPEC A-05, A-06 · PRD FR-12.7
Accept   1. Examination and investigation CRUD; delete not offered, is_active only
         2. Adding an investigation warns that no existing case returns an abnormal result
         3. Lexicon editor with live match tester
         4. Dead-phrase report (no match in 90 days)
```

**T-045 · Launch readiness**
```
Phase    4            Depends  all above      Est  2 d      Owner  both
Spec     PRD §5.1 · PLATFORM_SPEC §9
Accept   1. Deployed to Render: staging then production, migrations on release
         2. Privacy policy, terms, disclaimers live; consent captured
         3. Metabase connected for analytics
         4. Backup restore verified once, end to end
         5. All 10 cases published with approving clinical reviews
         6. Load test: 50 concurrent consultations without degradation (NFR-6)
```

---

# 9. Phases 5–7 — post-launch

Summarised. Expanded when the phase begins.

## Phase 5 · Measurement upgrade (11 d)
Embedding pipeline and pgvector backfill · hybrid keyword+embedding matcher behind a flag · labelled calibration corpus, **separate from the 18 validation transcripts** · threshold calibration with sensitivity analysis · replay all historical sessions and report the delta.
*Closes the "thresholds not tuned" limitation (`ADR-0013`).*

## Phase 6 · Mobile (20 d)
React Native + Expo sharing the generated API client · consultation and feedback screens · Apple and Google in-app purchase · push notifications · store listings and submission.

## Phase 7 · Case Factory (22 d)
DDXPlus connector · candidate filter with embedding dedup · schema-forced extraction · vocabulary mapping with quarantine · **NLI grounding** (`ADR-0012`) · LLM judge on a different model (`ADR-0011`) · **trap self-test harness** · admin console with funnel reporting.
*Gated on the dataset-licence verification in `PLATFORM_SPEC` §9.1.*

---

# 10. Schedule summary

| Phase | Effort | Cumulative | Milestone |
|---|---|---|---|
| 0 · Foundation | 8 d | 8 d | CI enforces the research claim |
| 1 · Persistence | 16 d | 24 d | No data loss; accounts real |
| 2 · Admin P0 | 11 d | 35 d | **Clinicians unblocked** |
| 3 · API + web | 22 d | 57 d | Usable product |
| 4 · Commercial | 17 d | 74 d | **Launchable** |
| 5 · Measurement | 11 d | 85 d | Thresholds justified |
| 6 · Mobile | 20 d | 105 d | App stores |
| 7 · Case Factory | 22 d | 127 d | Content scales |

**Launch at ~74 developer-days** ≈ 8–9 calendar weeks at two developers with parallelisation, assuming no other commitments.

## 10.1 Minimum viable cut

If launch must come sooner (`PLATFORM_SPEC` §11.1):

| Keep | Cut | Saves |
|---|---|---|
| Phases 0–2 entire | T-043 cost dashboard | 2 d |
| T-030, T-032, T-034, T-036 | T-037 progress screen | 3 d |
| T-040 leakage monitor | T-044 lexicon editor | 3 d |
| T-041, T-042, T-045 | T-035 → simple regex guard | 0.5 d |

**≈ 65 days.** Do not cut T-040 (leakage) or T-023 (clinical review) — one protects the measurement, the other protects users from clinically wrong content.

---

# 11. Risks to the plan

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| BR-1 | **Content authoring is the real critical path.** 5 more cases must be written and reviewed | High | High | Start authoring **now**, in parallel with Phase 0. It is not engineering work and does not compete for developer time |
| BR-2 | T-021/T-022 underestimated — admin UIs always are | Medium | Medium | Ship the editor without polish first; Playtest instrumentation matters more than styling |
| BR-3 | Persona leakage found to be widespread at T-040 | Medium | **High** | Discover it early — run adversarial prompts manually during Phase 2 Playtest, not at T-040 |
| BR-4 | Supabase Auth edge cases (Apple relay emails, account linking) | Medium | Low | Budget a spike day inside T-014 |
| BR-5 | Next.js learning curve | Medium | Medium | S-1 mocking means the frontend can start early and learn while unblocked |
| BR-6 | Stripe webhook races in production | Low | High | Idempotency plus the reconciliation query (`DATA_MODEL` §11.4) run nightly |
| BR-7 | Scope creep from `PRD` §5.3 deferred list | High | Medium | The deferred list is the answer. Point at it |

## 11.1 The risk I would watch

**BR-1.** Every estimate here is engineering effort. Ten published cases, each clinically reviewed, is the actual gate on launch — and it is invisible in a task list because no developer is assigned to it.

**Start writing cases in week one.**

---

*End of Build Plan. Task ids are stable; new work appends rather than renumbers.*
