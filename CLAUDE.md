# Nidan — project context

A bias-aware virtual patient simulator. Medical trainees interview an LLM-driven
patient, order examinations and tests, submit a diagnosis, and receive feedback on
**how they reasoned** — not just whether they were right.

**Current state:** Phases 0 and 1 complete — 16 of 34 tasks, 26 days of 83.
The research is published and validated; the platform now has a schema, a
repository layer with tenant scoping, event-sourced sessions, authentication,
anonymous trials, a replayable assessment engine, the free-tier allowance, and
the 16 pilot sessions imported into it.

**Next: Phase 2 — the admin console.** `BUILD_PLAN` calls it the milestone that
matters most, and its goal is one sentence: *clinicians can review cases without
reading code.* **T-023 is the gate** — until it exists no case can be published,
case selection has nothing to select, and the two clinician reviewers cannot
look at a case at all. Content authoring, which `BUILD_PLAN` §11.1 rates the
real critical path, starts there.

---

## ⚠️ Read only what you need

The specs total ~40 000 words. **Do not read them all.** Find your task below and
read only those sections.

| Task | Read |
|---|---|
| Anything at all | This file, then `docs/PROJECT_MAP.md` |
| What is every file in here? | `docs/PROJECT_MAP.md` — the full tree, annotated |
| Why was X chosen? | `docs/spec/adr/` — 16 one-page records. **Check here before re-arguing a decision** |
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

**Never open a database connection outside `infra/db`.** Every query runs inside
`repo_scope(actor)`, which assumes a non-superuser role and sets `auth.uid()` for
the transaction. A connection obtained any other way runs with RLS exempt, and
nothing about it looks wrong. (`ADR-0016` · `tests/test_db_access.py`)

**Backfilled events are marked and must be excluded from timing analysis.**
The 16 pilot sessions carry `provenance: "backfilled"` in every event payload;
their timestamps are synthetic because the JSON never recorded the interleaving.
Any query computing think-time must filter them out. (`DATA_MODEL` §9.3)

**Never change a detector, a threshold or the lexicon without reading the
golden diff.** `tests/test_golden_assessment.py` pins the engine's output for
all 16 pilot sessions. When it fails, regenerate with
`python scripts/build_golden.py`, read which learners' results moved, and commit
the diff with the change. Regenerating to make a red build green throws away the
only record of what moved.

**Detector accuracy must stay ≥ 94 %.** `validate_detectors.py` runs in CI and
fails the build below that. Do not "fix" a detector without re-running it.

---

## Repository layout

```
nidan/
  domain/               pure logic — no Flask, no Groq, no I/O
    content/cases.py      the 5 clinical cases + master exam/investigation lists
    assessment/bias.py    the three detectors  ← the core IP
    assessment/engine.py  assess(events, case, engine) — pure, replayable
    assessment/thresholds.py  the constants, as data (engine_versions)
    assessment/clinical.py  diagnosis and coverage scoring
    assessment/topics.py    TOPIC_KEYWORDS + extract_topics
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
      base.py               repo_scope(actor) — SET LOCAL ROLE + set_config
      events.py             the append-only log; seq collisions retried
      anonymous.py          ⚠️ the one path where RLS is OFF
    storage.py            session JSON read/write (the research export)
    feedback.py           calls the gateway with domain-built prompts
  api/routes.py         Flask blueprint "web" — the prototype
  api/v1.py             the JSON API at /v1 (ADR-0006)
  api/auth.py           @require_auth · @require_tier('pro')
  api/trial.py          the anonymous trial and its httpOnly cookie
  web/                  templates and static assets
  app.py                create_app() factory · __main__.py runs it

tests/                  test_smoke.py (routes) · test_layering.py (ADR-0009)
                        test_db_access.py (no query bypasses the repositories)
  db/                   schema tests — constraints, triggers, RLS (real Postgres)
                        test_repository_scope.py · test_anonymous_scope.py
migrations/versions/    21 hand-written Alembic migrations ← the schema's source of truth
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
pytest                             # 555 tests (see docs/spec/TEST_STRATEGY.md)
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
alembic upgrade head               # apply all 21 migrations
alembic downgrade base             # tear the schema down
pytest tests/db -q --no-cov        # 180 schema, repository and route tests, real Postgres
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
| Launch cases | 10 — **5 still to author**, the critical path |
| Free tier | 3 sessions/month, configured not schema |
| Price | $8–12/mo, $60–80/yr — exact figure at T-041 |
| Regional pricing | Yes, at launch |
| Funnel targets | Accepted as provisional hypotheses |
| Launch market | **Global English-speaking** — settles Stripe, not the DB region |
| Product name | **Nidan** |

**D-9 clinical convention** — settled 12 Sep 2026: **Commonwealth, unchanged.**
Every lab value already carries its interpretation and reference range, so the
units are not a barrier. When authoring cases 6–10, follow that pattern: SI
units, annotated with meaning and normal range. Add a US equivalent only where
a value has no annotation to carry it — blood gases are the one such case.

**One question remains open:**

- **Supabase region** (`SECURITY_SPEC` S-4) — one database, one jurisdiction,
  GDPR consequences. Settle before launch

Neither blocks T-010: the schema does not encode a price, a limit or a region.

---

## Context for working with me

- The research is **complete and published** — do not redo it.
- The pilot found coverage rose 45.3 % → 79.7 % (*p* = 0.036) but had **no control
  group**, so no causal claim. Do not overstate it.
- Two clinician reviewers are available but **blocked until the case editor and
  Playtest exist** (`BUILD_PLAN` T-021 → T-023). That gate matters more than it looks.
- **Content authoring is the real critical path**, not engineering. Five more cases
  must be written and clinically reviewed before launch.
