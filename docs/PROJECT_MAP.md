# Project map

Everything in this repository, what it is, and whether you need it.

Written because the project has grown to ~45 markdown documents, 24 Word
conversions, 16 architecture decisions and 7,200 lines of Python, and it is no
longer obvious from the folder names what matters.

**If you read one thing here, read §2.** It is the six documents that carry the
project. Everything else is supporting material, history, or generated output.

---

## 1 · The tree

```
A-bias-aware-vp-simulator/
│
├── CLAUDE.md ★             project context, auto-loaded by Claude every session
├── README.md               GitHub landing page
│
├── nidan/ ★                THE APPLICATION
│   ├── domain/             pure logic — no Flask, no Groq, no I/O
│   │   ├── content/cases.py      5 clinical cases, 27 exams, 86 investigations
│   │   ├── assessment/
│   │   │   ├── bias.py ★         the three detectors — the core IP
│   │   │   ├── engine.py ★       assess() — pure, replayable
│   │   │   ├── thresholds.py     the constants, as data
│   │   │   ├── clinical.py       diagnosis verdicts, workup coverage
│   │   │   └── topics.py         TOPIC_KEYWORDS, extract_topics()
│   │   ├── events.py             the 8 event types and payload shapes
│   │   ├── feedback_view.py      the feedback screen, recomputed
│   │   ├── selection.py          which case · monthly allowance
│   │   ├── session.py            session state + replay(events) ★
│   │   ├── feedback.py           feedback prompt building (no marking)
│   │   └── types.py              shared type aliases
│   ├── infra/              everything touching the outside world
│   │   ├── llm/gateway.py        the ONE place we call a model
│   │   ├── auth/ ★                JWKS cache + token verification
│   │   │   ├── jwks.py             cached 10 min; rotation handled
│   │   │   └── tokens.py           aud + iss, not just the signature
│   │   ├── db/ ★                 the ONE place we reach the database
│   │   │   ├── actor.py            who is asking — picks the DB role
│   │   │   ├── engine.py         ⚠ the only pool; private to infra/db
│   │   │   ├── models.py           MetaData only, deliberately no tables
│   │   │   └── repositories/       the only place SQL is written
│   │   │       ├── base.py ★         repo_scope() — SET LOCAL ROLE, auth.uid()
│   │   │       ├── profiles.py       the actor's own profile
│   │   │       ├── sessions.py       consultations, scoped by RLS
│   │   │       ├── events.py ★       the append-only log, with the retry
│   │   │       ├── feedback.py       stored prose (nothing else is stored)
│   │   │       ├── trial.py ★        claiming, in one UPDATE
│   │   │       ├── results.py        session_results + engine_versions
│   │   │       ├── selection.py      candidates · allowance · history
│   │   │       ├── cases.py          published content, read-only
│   │   │       └── anonymous.py ⚠    the one path with RLS OFF
│   │   ├── telemetry/            JSON logs, redaction, Sentry
│   │   ├── storage.py            the research JSON export
│   │   ├── clock.py              the injected clock
│   │   └── feedback.py           calls the gateway
│   ├── api/routes.py       Flask blueprint — the prototype
│   ├── api/v1.py           the JSON API at /v1 (T-014)
│   ├── api/auth.py ★       @require_auth · @require_tier('pro')
│   ├── api/trial.py        the anonymous trial (PRD FR-2)
│   ├── web/                templates and static files
│   ├── config.py           typed settings, validated at boot
│   └── app.py              create_app() · __main__.py runs it
│
├── tests/ ★                540 tests
│   ├── conftest.py               fixtures + the no-network guard
│   ├── fakes/llm.py              the fake model
│   ├── domain/                   unit + property tests
│   ├── db/                       real Postgres in a container
│   │   ├── test_routes.py ★        a consultation, end to end
│   │   ├── test_auth_routes.py ★   the authenticated API
│   │   ├── test_trial.py ★         the trial, and claiming it
│   │   ├── test_engine.py ★        results stored with their engine
│   │   ├── test_allowance.py       selection, limits, reservation
│   │   ├── test_event_concurrency.py ★ 10 parallel appends → seq 1..10
│   │   ├── test_constraints.py     CHECK constraints and indexes
│   │   ├── test_triggers.py        append-only, publication gate
│   │   ├── test_rls.py             the policies are written correctly
│   │   ├── test_seed.py            migrations 017-019 seeded the content
│   │   ├── test_repository_scope.py ★ the policies deny the APPLICATION
│   │   └── test_anonymous_scope.py ★ the path where RLS cannot help
│   ├── domain/test_replay.py ★   derived state is reproducible
│   ├── test_auth.py ★            tokens, without Supabase or Docker
│   ├── test_golden_assessment.py ★★ the 16 pilot sessions, pinned
│   ├── golden/                   the committed assessment record
│   ├── test_case_invariants.py   C-1 … C-9 on the case content
│   ├── test_llm_never_marks.py ★ proves property P1
│   ├── test_layering.py          proves domain/ stays pure
│   ├── test_db_access.py ★       proves no query bypasses the repositories
│   ├── test_db_actor.py          the actor guards, without Docker
│   └── test_validation_gate.py   proves the 94% gate actually fails
│
├── docs/                   see §2–§6 below
├── report/main.tex         the IEEE research paper (LaTeX source)
├── sessions/               16 real pilot sessions (JSON)
├── scripts/build_status.py regenerates the status tracker
│
├── validate_detectors.py ★ the 94% gate — research tooling, not the product
├── analyze_sessions.py     McNemar + Wilcoxon over session JSON
├── test_api.py             check the Groq key works
│
├── Dockerfile              multi-stage, non-root
├── docker-compose.yml      app + Postgres 16 with pgvector
├── docker/postgres-init/   extensions created on first start
├── .github/workflows/ci.yml ★ the six CI checks
├── .github/BRANCH_PROTECTION.md  the manual GitHub setting
├── pyproject.toml          dependencies, coverage gate, layering contract
├── .env.example            every setting documented
└── .gitleaks.toml          secret-scanner allowlist
```

★ = the files that carry the most weight.

---

## 2 · The six documents that matter

If someone asks *"what is this project"*, these answer it. Everything in
`docs/spec/` is the **build contract** — written before the code, and the thing
the code is checked against.

| Document | Words | What it answers | Read it when |
|---|---:|---|---|
| **PRD.md** | 6,200 | What are we building and why? 12 requirements, 5 product principles, 8 open decisions | Scope questions, "should it do X?" |
| **UX_SPEC.md** | 11,900 | Every screen, control, empty state, error state. 21 consumer screens + 10 admin | Building any screen |
| **DATA_MODEL.md** | 6,800 | Every table, column, index, constraint. Real SQL. RLS policies | Any schema or migration work |
| **API_CONTRACT.md** | 3,700 | Every endpoint, request/response shape, error codes, rate limits | Building or calling an endpoint |
| **TECH_SPEC.md** | 4,000 | Architecture. How a request flows, where the layers are, deployment | Understanding how it fits together |
| **BUILD_PLAN.md** ★ | 4,000 | The work, as 34 sequenced tasks with done-definitions | **Start here to build anything** |

**Plus two added during Phase 0:**

| Document | Words | What it answers |
|---|---:|---|
| **TEST_STRATEGY.md** | 3,900 | What each kind of test can and — more importantly — **cannot** catch |
| **SECURITY_SPEC.md** | 4,400 | Who would attack this, what stops them, what to do on a breach |

### And the ADRs — `docs/spec/adr/`

**16 files, one decision each, one page each.** Read these *before* re-arguing
anything. Each says what was decided, what the alternatives were, and why they
lost.

| | |
|---|---|
| 0001 | PostgreSQL with pgvector on Supabase |
| 0002 | Supabase Auth, not custom authentication |
| 0003 | Event-sourced session state |
| **0004** | **Rule-based bias detection, NOT machine learning** |
| **0005** | **The LLM is excluded from the marking path** |
| 0006 | Next.js for the consumer app, Jinja+HTMX for admin |
| 0007 | Retain Flask, do not migrate to FastAPI |
| 0008 | Deploy to Render, not Vercel |
| 0009 | Modular monolith, not microservices |
| 0010 | Cases are immutable and versioned |
| 0011 | Per-job LLM routing |
| 0012 | NLI for grounding, not an LLM |
| 0013 | Prebuilt embeddings first, fine-tune later |
| 0014 | No case retirement — use variants |
| 0015 | Direct-to-consumer, institutional path preserved |

**0004 and 0005 are the two that define the project.** If you explain nothing
else in a viva, explain those: the detectors are deterministic Python, and the
language model never produces a score. That is what makes results reproducible
and defensible.

`ADR_LOG.md` is an index of all 16 in one file.

---

## 3 · `docs/build-log/` — what was actually built

`docs/spec/` is the promise. This folder is the record.

| File | What it is |
|---|---|
| **STATUS.md** ★ | **The progress tracker. 7 of 34 tasks. Start here.** Generated — never edit by hand |
| README.md | The convention: 11 mandatory sections every task doc must have |
| T-001 … T-007 | One document per completed task |

Each task document contains: what was built, the actual commands, **where the
work diverged from the specification and why**, the real error text for every
problem hit, what changed for you, and what debt was left behind.

The "where we diverged" section is the one that stops a mismatch between the
spec and the code looking like a mistake three weeks later.

**Regenerate the tracker after finishing a task:**

```bash
python scripts/build_status.py
```

---

## 4 · `docs/process/` — how we work

| File | What it is |
|---|---|
| **COMMANDS.md** ★ | **Every terminal command, grouped by what you want to do.** §7 is the troubleshooting section — every error we have actually hit, with its fix |
| **WINDOWS_SETUP.md** | **Yogesh's onboarding — install, configure, and the PR workflow now that `main` is protected** |
| AI_BUILD_PROMPT.md | The reusable brief for working with an AI on a project: spec first, one task at a time, stop and report |
| USAGE.md | How to adapt that prompt, and why `CLAUDE.md` matters more than any pasted prompt |

---

## 5 · The rest of `docs/` — supporting material

### `docs/Main Research Paper/` and `docs/Other Research Paper/`

**12 PDFs.** The academic literature the project is built on — patient
simulation with LLMs, anchoring bias, premature closure detection, explainable
clinical reasoning. This is the reading behind the research, not documentation
of the software.

### `docs/design/` — ⚠️ SUPERSEDED

| File | Words | Status |
|---|---:|---|
| PLATFORM_SPEC.md | 12,400 | ⚠️ superseded — cited 15× by current specs |
| SYSTEM_DESIGN.md | 10,900 | ⚠️ superseded — historical record |

**Do not build from these.** Both now open with a SUPERSEDED banner saying so,
in the markdown and the Word versions.

They are kept rather than deleted for two concrete reasons: the current
specifications still **cite `PLATFORM_SPEC` 15 times** for detail not carried
forward (DATA_MODEL, BUILD_PLAN, TECH_SPEC, UX_SPEC), and `TECH_SPEC` §1.2
keeps them deliberately as the record of how the design evolved — which is what
makes the frontend reversal in `ADR-0006` legible.

Deleting them would break 15 live cross-references and lose the reasoning
behind a decision that was reversed.

### Loose files in `docs/`

| File | What it is |
|---|---|
| `detector_validation.md` | **Generated** by `validate_detectors.py`. The 94% result, per detector, per transcript |
| `cases_design.md` | Early design notes on how the 5 clinical cases were constructed |
| `pseudocode.md` | Early algorithm sketches for the detectors |
| `references.md` | Bibliography for the research paper |
| `journal.md` | Working notes from the research phase |
| `Sprint_Plan.docx` | The original coursework sprint plan — historical |

These five predate the build specification. They are useful for the **research**
story (viva, report) and are not the source of truth for the **software**.

---

## 6 · The `.docx` files — what they are for

Every specification, build log and process document has a Word version sitting
next to it. **The `.md` is the source; the `.docx` is a conversion.**

They exist so documents can be opened in Google Docs, shared with a supervisor,
or printed. They are generated by `docs/spec/md2docx.js`:

```bash
NODE_PATH=/opt/homebrew/lib/node_modules node docs/spec/md2docx.js \
  input.md output.docx "Title" "Subtitle" "Status" "Part of"
```

**Edit the `.md`, then regenerate the `.docx`.** Editing a `.docx` directly means
the two disagree and the markdown — which is what everyone actually reads in the
repository — silently becomes wrong.

| Where | Files |
|---|---|
| `docs/spec/` | 9 — PRD, UX, Data Model, API, Tech Spec, Test Strategy, Security, Build Plan, ADRs |
| `docs/build-log/` | 9 — the 7 task logs, the convention, the status tracker |
| `docs/process/` | 3 — commands, build prompt, usage |
| `docs/design/` | 2 — the superseded designs |

---

## 7 · Where to start, by what you are doing

| You want to… | Read, in order |
|---|---|
| **Understand the project at all** | `CLAUDE.md` → this file → `docs/spec/README.md` |
| **Know what is done** | `docs/build-log/STATUS.md` |
| **Build the next thing** | `BUILD_PLAN.md` → find the task → read only its `Spec` refs |
| **Understand a past decision** | `docs/spec/adr/` — find the number |
| **Understand what was already built** | `docs/build-log/T-xxx-*.md` |
| **Run something** | `docs/process/COMMANDS.md` |
| **Explain the research** | `report/main.tex`, `docs/detector_validation.md`, ADR-0004 and ADR-0005 |
| **Prepare for a viva** | ADR-0004, ADR-0005, `TEST_STRATEGY.md` §6, `docs/detector_validation.md` |

---

## 8 · Known gaps in the repository

Stated so they are not discovered at a bad moment.

| Gap | Detail |
|---|---|
| **No compiled PDF of the paper** | `report/` contains only `main.tex`. The built PDF is not in git |
| **No presentation in the repo** | The 16-slide deck is not tracked. If it exists, it is only on a local machine |
| **Phases 5–7 are not itemised** | `BUILD_PLAN` §9 summarises them as prose. 53 further days of work with no task breakdown yet |
| **8 open product decisions** | `PRD` §11 — price, free-tier limit, launch case count, product name. These become gating code, so they need answering before the schema is final |

---

*Generated 8 September 2026. Regenerate the tree if the layout changes.*
