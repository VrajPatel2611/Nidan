# Nidan — project context

A bias-aware virtual patient simulator. Medical trainees interview an LLM-driven
patient, order examinations and tests, submit a diagnosis, and receive feedback on
**how they reasoned** — not just whether they were right.

**Current state:** Phases 0, 1 and **2 complete — 20 of 34 tasks, 38 days of
83.** The research is published and validated; the platform has a schema, a
repository layer with tenant scoping, event-sourced sessions, authentication,
anonymous trials, a replayable assessment engine, the free-tier allowance, the
16 pilot sessions imported into it, and the whole admin console: case editor,
Playtest, and the clinical review workflow.

**The gate is open.** Phase 2's goal was one sentence — *clinicians can review
cases without reading code* — and T-023 met it on 29 Oct 2026. The two
clinician reviewers are no longer blocked, which matters more than the task
count suggests: **their turnaround is calendar time that runs in parallel with
engineering**, so onboarding them is worth more than starting the next task.

**All ten cases are written.** D-2 closed on 29 Oct 2026, with cases 6-10
authored in a day. **6 and 7 came from designs that had been sitting in
`docs/cases_design.md` since May** — the evidence they were always meant to be
built is in migration 017, which seeded 13 topics that no case used until that
day. 8, 9 and 10 were designed from scratch and their design sections added to
the same file. Every case is `draft`, and none can be published until a
clinician approves it — migration 007's trigger, not a convention.

**So `BUILD_PLAN` §11.1's critical path has moved rather than closed.** It is
no longer writing cases; it is **review turnaround**, and the two clinicians
cannot start because the console only runs on `localhost` and no task in any
of the seven phases deploys it. That is the single thing standing between ten
finished cases and the review they need — see `REVIEWER_ONBOARDING.md`.

**Next: Phase 3 — the API and the web app** (8 tasks, 28 d), with review
running beside it rather than after it. T-030 (JSON API, Vraj) and T-032
(Next.js scaffold, Yogesh) have no dependency on each other and can start
together.

---

## ⚠️ Read only what you need

The specs total ~40 000 words. **Do not read them all.** Find your task below and
read only those sections.

| Task | Read |
|---|---|
| Anything at all | This file, then `docs/PROJECT_MAP.md` |
| What is every file in here? | `docs/PROJECT_MAP.md` — the full tree, annotated |
| Why was X chosen? | `docs/spec/adr/` — 17 one-page records. **Check here before re-arguing a decision** |
| Building a feature | `docs/spec/BUILD_PLAN.md` → find the task → read only its `Spec` refs |
| Schema / migration | `docs/spec/DATA_MODEL.md` — the relevant table section only |
| An endpoint | `docs/spec/API_CONTRACT.md` §4–9 + `openapi.yaml` |
| A screen | `docs/spec/UX_SPEC.md` — that screen's section only |
| Requirements / scope | `docs/spec/PRD.md` §5–6 |
| Writing or running tests | `docs/spec/TEST_STRATEGY.md` §3–5, then §9 |
| Auth, permissions, secrets, anything security | `docs/spec/SECURITY_SPEC.md` §3–4, then §8 |
| Which tasks are done | `docs/build-log/STATUS.md` — generated, see below |
| What a whole phase delivered, and what it taught | `docs/build-log/PHASE-1.md` |
| What was done on a finished task | `docs/build-log/T-xxx-*.md` |
| A command you half-remember | `docs/process/COMMANDS.md` |
| Setting up on Windows | `docs/process/WINDOWS_SETUP.md` |
| **Picking up a Phase 3 task** | `BUILD_PLAN` §7 — T-030 … T-037. There are no Phase 3 briefs; `docs/process/phase-2-briefs/` is historical |
| **Deploying the database to Supabase** | `docs/process/SUPABASE_DEPLOYMENT.md` — there is no file to upload; it is 32 migrations |
| **Signing in to `/admin` locally** | `docs/process/LOCAL_ADMIN_ACCESS.md` — every refusal is an identical 404, so work through it in order |
| **Onboarding a clinical reviewer** | `docs/process/REVIEWER_ONBOARDING.md` — and `REVIEWER_GUIDE.md`, which is the document the clinician actually receives |
| How it fits together | `docs/spec/TECH_SPEC.md` §2–3 |

`docs/design/` holds **superseded** v1/v2 design docs. Historical only — do not
build from them.

---

## The three properties that must never break

Everything else defers to these. A change that breaks one is rejected regardless
of its other merits.

1. **The LLM never marks.** Every flag, score and verdict is deterministic Python.
   The LLM only voices the patient and writes feedback prose. (`ADR-0005`)
2. **Every judgement is traceable.** A flag cites the learner's own questions or
   omissions. No unexplained scores. (`ADR-0004`)
3. **The event log is the source of truth.** Derived state is reproducible from it.
   (`ADR-0003`)

Property 1 is why the pilot's data-integrity check worked: results recomputed from
stored questions matched all 16 sessions exactly.

---

## Rules that are easy to break by accident

**Never show the remaining allowance during a consultation either.** It belongs
on the dashboard, before starting (`PRD` FR-10.2). `GET /me` carries it; no
session payload does. Same reason as below — a visible counter teaches the
counter.

**Never show assessment state during a consultation.** No coverage meter, no
question counter, no topic hints, no completeness nudge before submitting. A
visible metric teaches the metric, not the skill. (`PRD` P2 · contract tests CT-1, CT-2)

**Never use bias vocabulary in user-facing text.** Not "bias", "anchoring",
"premature closure", or "confirmation bias". User-facing headings are
*Diagnostic focus · History completeness · Evidence exploration*. (`PRD` P1 · CT-5)

**A detector result reaches a learner through `api/v1/reasoning.py` and
nowhere else.** The detectors' own `reason` strings contain the banned
vocabulary — "No significant anchoring pattern detected", "Confirmation
bias occurs when…" — so forwarding `bias_detail` ships exactly what CT-5
forbids. The prose is rebuilt from `counters`, which is what `DATA_MODEL`
§8.5 added them for and which is also what `PRD` P3 wants cited: the
learner's own actions. (CT-4, CT-5 · `tests/db/test_v1_conclusion.py`)

**`cases.content()` returns the ROW; the payload is its `content` key.**
Use `cases.case_for_session()`, which returns the **domain's** `Case`
shape — it adds `id` (the slug), promotes `title`, and flattens
`patient_intro` out of `patient.intro`. Passing the row to a serialiser
is silent: for two merged slices the patient came back with every field
None, the LLM got an empty system prompt, and every examination returned
the master normal result because the case-specific block was never found.
Shape assertions all passed. `test_the_case_adapter_supplies_every_key_the
_domain_reads` walks the AST so the next mismatch fails a test.

**A case reaches a client through `api/v1/case_view.py` and nowhere else.**
`PRD` FR-3.4 forbids eight fields in the `case` object and `API_CONTRACT`
§11 calls CT-1 "the leak that would invalidate everything" — a learner who
can read `anchor_keywords` knows what the detector watches for, and every
measurement after that is of something else. The serialiser names the
fields that go in; it never copies the content and deletes the bad keys,
because `case_versions.content` is JSONB and a new key arrives in a
case-editor save with no migration and no review.

**Anchor keywords must never overlap contradictory clues.** This exact bug cost
14 % sensitivity in the confirmation-bias detector. Invariant C-4 in
`DATA_MODEL` §8.1, enforced in CI and in the case editor.

**The backend never handles a password, and never trusts a token's signature
alone.** Supabase issues credentials; we verify `aud` and `iss` as well as the
signature, or a token from any other Supabase project authenticates here.
(`ADR-0002` · `tests/test_auth.py`)

**Session state is never held in the process.** Every handler replays the event
log, acts, appends, and returns. There is no session dictionary, no cache, and
nothing that survives a request — which is why the app runs on 2 gunicorn
workers and why killing it mid-consultation loses nothing. (`ADR-0003` ·
`tests/db/test_routes.py`)

**The admin console refuses with 404, never 403.** A 403 tells someone probing
that an admin console exists. Every refusal — no token, expired token, signed in
without privilege — returns an identical 404 body, because a difference between
them is the same leak in a quieter form. (`UX_SPEC` §12.1 ·
`tests/db/test_admin_access.py`)

**Never open a database connection outside `infra/db`.** Every query runs inside
`repo_scope(actor)`, which assumes a non-superuser role and sets `auth.uid()` for
the transaction. A connection obtained any other way runs with RLS exempt, and
nothing about it looks wrong. (`ADR-0016` · `tests/test_db_access.py`)

**The actor decides the privilege, and the route decides the actor.** Five of
them: `AuthenticatedUser` (`nidan_app`), `AdminUser` (`nidan_admin` — the only
role that may write `cases` and `case_versions`), `ReviewerUser`
(`nidan_reviewer` — reads drafts, inserts `clinical_reviews`, writes no
content), `AnonymousVisitor` and `ServiceActor` (`nidan_service`, RLS bypassed).
Routes pick with `current_actor()`, `current_admin()` and `current_reviewer()`
— per route, not per person, so browsing never carries the privilege to author
and an admin reviewing a case holds the reviewer's smaller role.
(`migrations/023`, `024` · `tests/db/test_case_authoring.py`,
`tests/db/test_clinical_review.py`)

**Backfilled events are marked and must be excluded from timing analysis.**
The 16 pilot sessions carry `provenance: "backfilled"` in every event payload;
their timestamps are synthetic because the JSON never recorded the interleaving.
Any query computing think-time must filter them out. (`DATA_MODEL` §9.3)

**A failed LLM call must not consume the question.** The question event is
appended only AFTER the reply returns, which is the opposite of orthodox
event sourcing and deliberate twice over: `UX_SPEC` S-10 needs the typed
text preserved for retry, and `question_count` feeds the premature-closure
detector (`P1: q < q_min`) — so a question logged with no answer inflates
the count and **suppresses a flag the learner should have seen**. 503
`patient_unavailable`, and nothing written. (`API_CONTRACT` §6 ·
`tests/db/test_v1_consultation.py`)

**The 40-question cap counts questions, not events.** A learner who
examined eight systems and ordered six tests has used none of their
questions; a cap that counted events would punish the thoroughness the
product exists to teach. (`API_CONTRACT` §2.9)

**Never change a detector, a threshold or the lexicon without reading the
golden diff.** `tests/test_golden_assessment.py` pins the engine's output for
all 16 pilot sessions. When it fails, regenerate with
`python scripts/build_golden.py`, read which learners' results moved, and commit
the diff with the change. Regenerating to make a red build green throws away the
only record of what moved.

**New content is a new migration, never a regenerated one.** Both generators —
`generate_case_migration.py` for cases, `generate_seed_migration.py` for the
master lists and the topic lexicon — used to take no arguments and always
rewrite 019 and 017. Re-running one over an applied revision rewrites a
migration no database will ever run again, and the file still looks generated
and still imports cleanly, so nothing fails. Both now require `--revision`
and `--down-revision` and refuse to overwrite without `--force`.
(`DATA_MODEL` §9.1)

**The topic lexicon is full.** Cases 6 and 7 used the last of the 40 topics
migration 017 seeded. 027, 029 and 031 added thirteen more, plus five
investigations that did not exist (colonoscopy, FIT, HLA-B27 and two imaging
keys). **Every remaining case
needs new topics, so each is two migrations, not one** — and T-044, the
lexicon editor that would make this a screen instead, is Phase 4.
A topic added to `topics.py` without a migration leaves the database
disagreeing with the code, and `tests/db/test_seed.py` is what says so.

**An error code lives in three places and is compared in all three.**
`nidan/api/errors.py` holds `CATALOGUE` as data, `API_CONTRACT` §10 holds
the table, `openapi.yaml` holds the enum. `error()` raises on a code that
is not catalogued, and on a status that contradicts the one §10 gives it —
`error("not_found", ..., 403)` is the §2.7 leak and reads as plausible.
Adding a code means all three in one commit; `tests/test_api_contract.py`
fails otherwise. (CT-6, CT-7)

**Every operation `openapi.yaml` declares must answer.** If it is not
built, it is listed in `nidan/api/v1/contract.py` and returns 501 with the
envelope — which is what sync point S-1 means and what did not exist until
T-030. The list only shrinks, and a line left behind after a slice
implements it fails the suite rather than shadowing the real route.

**`session_events` and `audit_log` refuse UPDATE and DELETE, including to
the table owner.** Migration 002's `forbid_mutation` is unconditional, so
a teardown or a cleanup must TRUNCATE, never DELETE — and a cascade into
either table fails the whole transaction, which is why deleting a profile
needs the session tables truncated first. **`DATA_MODEL` §10.2's erasure
cannot run**: it UPDATEs `session_events`, so `DELETE /me` is a 501 and
API-9 is the open decision. (verified against the running database ·
`tests/db/test_v1_progress.py`)

**Detector accuracy must stay ≥ 94 %.** `validate_detectors.py` runs in CI and
fails the build below that. Do not "fix" a detector without re-running it.

---

## Repository layout

```
nidan/
  domain/               pure logic — no Flask, no Groq, no I/O
    content/cases.py      all 10 clinical cases + master exam/investigation lists
    assessment/bias.py    the three detectors  ← the core IP
    assessment/engine.py  assess(events, case, engine) — pure, replayable
    assessment/thresholds.py  the constants, as data (engine_versions)
    assessment/clinical.py  diagnosis and coverage scoring
    assessment/topics.py    TOPIC_KEYWORDS (53) + extract_topics
    selection.py          which case, and how much of the month is left
    session.py            session state — create, update, and replay(events)
    events.py             the 8 event types and their payload shapes
    feedback.py           feedback prompt construction (prose only, no marking)
    feedback_view.py      the feedback screen, recomputed from the log
  infra/                everything that touches the outside world
    llm/gateway.py        the single call site for the LLM
    auth/jwks.py          Supabase's signing keys, cached 10 min
    auth/tokens.py        JWT verification — aud and iss, not just the signature
    db/actor.py           who is asking — decides the DB role and auth.uid()
    db/engine.py          ⚠️ the only connection pool; private to infra/db
    db/repositories/      the only place SQL is written (ADR-0016)
      trial.py              claiming a trial into an account (one UPDATE)
      results.py            session_results + engine_versions
      selection.py          candidates, allowance count, case history
      audit.py              every admin action, append-only
      cases.py              reads for learners; authoring writes need AdminUser
      reviews.py            review assignments and the rubric; T-023
      catalog.py            the universal menus; no case-specific column
      idempotency.py        the §2.8 key store; hashes the body, never keeps it
      progress.py           trends computed on read; user_progress stays empty
      base.py               repo_scope(actor) — SET LOCAL ROLE + set_config
      events.py             the append-only log; seq collisions retried
      anonymous.py          ⚠️ the one path where RLS is OFF — keep it that way
    storage.py            session JSON read/write (the research export)
    feedback.py           calls the gateway with domain-built prompts
  api/routes.py         Flask blueprint "web" — the prototype. Reads cases from
                        cases.py, NOT the published bank; survives until T-034
  api/errors.py         the error envelope + the §10 catalogue AS DATA — shared
                        with the admin console, so it is not inside v1/
  api/v1/               the JSON API at /v1 (ADR-0006, T-030)
    blueprint.py          the Blueprint alone, so route modules import acyclically
    identity.py           API_CONTRACT §4 · /me (POST, GET, PATCH)
    catalog.py            §5 · the two universal menus — CT-3 lives here
    case_view.py          ⚠️ the ONLY place a case becomes a response — CT-1
    sessions.py           §6, §7 · POST + GET /sessions, GET /sessions/{id}
    consultation.py       §6 · questions, examinations, investigations
    conclusion.py         §6 · diagnosis, feedback, rating, abandon
    reasoning.py          ⚠️ the ONLY place a detector becomes text — CT-4, CT-5
    idempotency (infra)   §2.8 · Idempotency-Key, 24 h replay — CT-8
    pagination.py         §2.5 cursors — never offsets
    account.py            §4, §7 · /progress, /me/export
    contract.py           the 501s openapi.yaml declares, and the JSON 404/405
  api/auth.py           @require_auth · @require_tier('pro') · @require_admin
  api/trial.py          the anonymous trial and its httpOnly cookie
  web/                  templates and static assets
  app.py                create_app() factory · __main__.py runs it

tests/                  test_smoke.py (routes) · test_layering.py (ADR-0009)
                        test_db_access.py (no query bypasses the repositories)
  db/                   schema tests — constraints, triggers, RLS (real Postgres)
                        test_repository_scope.py · test_anonymous_scope.py
migrations/versions/    32 Alembic migrations ← the schema's source of truth
                        (017, 019, 026-032 are generated from cases.py
                         and topics.py; see the rule below)
docs/build-log/         what was actually built, one doc per finished task
docs/spec/              the build contract — 6 docs + adr/  ← the source of truth
docs/design/            superseded design docs (historical)
docs/detector_validation.md   generated by validate_detectors.py
sessions/               16 real pilot sessions (JSON)
report/                 the research paper (LaTeX + PDF) and presentation
*.py at root            research tooling — validate_detectors, analyze_sessions, test_api
```

The layering rule is not a convention, it is tested: `tests/test_layering.py`
and the import-linter contract in `pyproject.toml` both fail if `domain/`
reaches into `infra/` or `api/`.

---

## Commands

```bash
source venv/bin/activate
pip install -e .                   # once, after cloning

python -m nidan                    # run the app (needs GROQ_API_KEY in .env)
docker compose up --build          # app + Postgres 16/pgvector on a clean machine
pytest                             # 913 tests (see docs/spec/TEST_STRATEGY.md)
ruff check . --fix                 # style
mypy nidan/domain --strict         # types (domain only)
lint-imports                       # check the domain/infra/api layering contract
python validate_detectors.py       # detector validation — must report >= 94%
python analyze_sessions.py sessions # paired statistics over session JSON
python test_api.py                 # check the LLM key works
python scripts/build_status.py     # regenerate docs/build-log/STATUS.md
python scripts/build_golden.py     # regenerate the golden assessment record
python scripts/backfill_pilot.py   # import the 16 pilot sessions (run-once, idempotent)
pip install -e ".[docs]"           # once, for the .docx generator
python scripts/build_docx.py       # regenerate every .docx from its Markdown

# database (T-010) — needs the stack up: docker compose up -d db
alembic upgrade head               # apply all 32 migrations
alembic downgrade base             # tear the schema down
pytest tests/db -q --no-cov        # 342 schema, repository and route tests, real Postgres
```

---

## Conventions

- **Python**: `snake_case`; `domain/` must never import `infra/` or `api/` (`ADR-0009`)
- **Database**: `snake_case`, plural tables, `TIMESTAMPTZ` always, UUID PKs for
  domain entities, `BIGSERIAL` for append-only logs
- **Docs**: `DATA_MODEL.md` and `openapi.yaml` change in the **same commit** as the
  code. ADRs are **never edited** — supersede with a new record. **The Markdown
  is the source of truth**; the `.docx` copies are generated by
  `scripts/build_docx.py` and must never be edited by hand.
- **Spelling**: British English in user-facing copy and docs

---

## Decisions

**All 8 original `⟨DECIDE⟩` items are settled** (`PRD` §11, decided 9–11 Sep 2026):

| | |
|---|---|
| Persona | Clinical-phase students and early trainees, years 3–5 |
| Launch cases | 10 — **all 10 authored** (29 Oct 2026). All 10 still need clinical review |
| Free tier | 3 sessions/month, configured not schema |
| Price | $8–12/mo, $60–80/yr — exact figure at T-041 |
| Regional pricing | Yes, at launch |
| Funnel targets | Accepted as provisional hypotheses |
| Launch market | **Global English-speaking** — settles Stripe, not the DB region |
| Product name | **Nidan** |

**D-9 clinical convention** — settled 12 Sep 2026: **Commonwealth, unchanged.**
Every lab value already carries its interpretation and reference range, so the
units are not a barrier. Cases 6–10 followed that pattern and any future case
must: SI units, annotated with meaning and normal range. Add a US equivalent
only where a value has no annotation to carry it — blood gases are the one
such case.

**S-4 Supabase region** — settled 28 Oct 2026, `ADR-0017`: **Central EU
(Frankfurt), `eu-central-1`.** Keeping the data in the EEA removes the GDPR
Chapter V transfer obligation for EU users rather than satisfying it, and the
obligation is one-directional — no non-EU user is constrained by the choice.
The cost is 120–150 ms of latency from India, which the LLM call dwarfs. **A
Supabase project cannot change region**; moving means a new project and a
migration.

**No ⟨DECIDE⟩ items remain open.**

---

## Two laptops — the handoff file

Vraj (backend) and Yogesh (frontend/admin) work on separate laptops with one
Claude account. Claude on one laptop **cannot see the other's chats or memory**,
so work crosses between them through `HANDOFF.md` on the `handoff` branch — a
branch with no shared history with `main`: no pull request, no CI.

- **At the start of every session**, before task work:
  `git fetch origin handoff && git show origin/handoff:HANDOFF.md`
  Tell the person what is open in their inbox, and whether it blocks the task.
- **When something turns up that the other person must do**, add it to their
  inbox and push. Edit through a worktree (`git worktree add ../nidan-handoff
  handoff`), never by checking out `handoff` in this folder — it has none of the
  project's files.
- The rules for writing items are at the top of `HANDOFF.md`. **No secrets** in it.

---

## Context for working with me

- The research is **complete and published** — do not redo it.
- The pilot found coverage rose 45.3 % → 79.7 % (*p* = 0.036) but had **no control
  group**, so no causal claim. Do not overstate it.
- Two clinician reviewers are available. The T-021 → T-023 gate that blocked
  them is **open** as of 29 Oct 2026. **What blocks them now is hosting**: the
  console runs on `localhost` and `BUILD_PLAN` has no deployment task in any
  phase. Ten reviewed cases is the launch gate, and nobody can start.
- **Content authoring is done, review is not.** All ten cases exist as
  drafts. None can be published until a clinician approves it — the gate is
  a database trigger, not a convention. **Clinical review is now the whole
  of the critical path**, and it is calendar time, not engineering time.
