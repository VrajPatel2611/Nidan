# Nidan — Technical Specification

---

## Contents

**1. Document control**

&nbsp;&nbsp;&nbsp;&nbsp;1.1 Scope and boundaries  
&nbsp;&nbsp;&nbsp;&nbsp;1.2 Supersedes  
**2. System overview**

&nbsp;&nbsp;&nbsp;&nbsp;2.1 What the system does  
&nbsp;&nbsp;&nbsp;&nbsp;2.2 Three load-bearing properties  
&nbsp;&nbsp;&nbsp;&nbsp;2.3 Context  
**3. Architecture**

&nbsp;&nbsp;&nbsp;&nbsp;3.1 Component model  
&nbsp;&nbsp;&nbsp;&nbsp;3.2 Request lifecycle  
&nbsp;&nbsp;&nbsp;&nbsp;3.3 Consultation data flow  
**4. The assessment engine**

&nbsp;&nbsp;&nbsp;&nbsp;4.1 Interface  
&nbsp;&nbsp;&nbsp;&nbsp;4.2 Topic extraction  
&nbsp;&nbsp;&nbsp;&nbsp;4.3 The three detectors  
&nbsp;&nbsp;&nbsp;&nbsp;4.4 Validation  
&nbsp;&nbsp;&nbsp;&nbsp;4.5 The defect this validation found  
**5. LLM gateway**

&nbsp;&nbsp;&nbsp;&nbsp;5.1 Responsibilities  
&nbsp;&nbsp;&nbsp;&nbsp;5.2 Model selection  
&nbsp;&nbsp;&nbsp;&nbsp;5.3 Persona integrity — the largest residual risk  
**6. Admin console**

&nbsp;&nbsp;&nbsp;&nbsp;6.1 Why it matters more than it sounds  
&nbsp;&nbsp;&nbsp;&nbsp;6.2 Architecture  
&nbsp;&nbsp;&nbsp;&nbsp;6.3 The two screens that carry the value  
&nbsp;&nbsp;&nbsp;&nbsp;6.4 Threshold impact preview  
&nbsp;&nbsp;&nbsp;&nbsp;6.5 Build strategy  
**7. Case Factory**

&nbsp;&nbsp;&nbsp;&nbsp;7.1 Principle  
&nbsp;&nbsp;&nbsp;&nbsp;7.2 Pipeline  
&nbsp;&nbsp;&nbsp;&nbsp;7.3 Blocking constraint  
**8. Frontend and mobile**

&nbsp;&nbsp;&nbsp;&nbsp;8.1 The UX constraints that are architectural  
**9. Deployment**

&nbsp;&nbsp;&nbsp;&nbsp;9.1 Packaging  
&nbsp;&nbsp;&nbsp;&nbsp;9.2 Platform  
&nbsp;&nbsp;&nbsp;&nbsp;9.3 Environments  
&nbsp;&nbsp;&nbsp;&nbsp;9.4 CI/CD  
&nbsp;&nbsp;&nbsp;&nbsp;9.5 Database operations  
**10. Observability**

&nbsp;&nbsp;&nbsp;&nbsp;10.1 Metrics that matter  
**11. Security and privacy**

&nbsp;&nbsp;&nbsp;&nbsp;11.1 Position  
&nbsp;&nbsp;&nbsp;&nbsp;11.2 Support access  
&nbsp;&nbsp;&nbsp;&nbsp;11.3 Legal position  
**12. Testing strategy**

**13. Non-functional requirements**

**14. Research operations**

**15. Open technical questions**


---

---

# 1. Document control

| Field | Value |
|---|---|
| **Document** | Nidan Technical Specification |
| **Version** | v1.0 |
| **Status** | Draft — consolidates `design/SYSTEM_DESIGN.md` and `design/PLATFORM_SPEC.md` |
| **Owners** | Vraj Patel, Yogesh Bagotia |

## 1.1 Scope and boundaries

This document describes **how the system works**. It deliberately does not repeat what belongs elsewhere:

| For | See |
|---|---|
| What we are building and why | `PRD.md` |
| Why a technology was chosen | `adr/` — 15 records |
| Every table and column | `DATA_MODEL.md` |
| Every endpoint | `API_CONTRACT.md` + `openapi.yaml` |
| Every screen | `UX_SPEC.md` |
| What to build in what order | `BUILD_PLAN.md` |

**Decisions are referenced, not re-argued.** Where this document states a choice, the reasoning is in the cited ADR. If you disagree with a choice, supersede the ADR rather than editing this document.

## 1.2 Supersedes

`design/SYSTEM_DESIGN.md` (v1) and `design/PLATFORM_SPEC.md` (v2) are superseded in full. They remain in the repository as historical record of how the design evolved — in particular the frontend reversal recorded in `ADR-0006`.

---

# 2. System overview

## 2.1 What the system does

A learner interviews an LLM-driven virtual patient, orders examinations and investigations from an undifferentiated universal menu, and submits a diagnosis. The system records every action and, at conclusion, applies a deterministic rule engine that detects three cognitive biases, then returns Socratic feedback.

**The measurement is the product.** Every architectural decision defers to that.

## 2.2 Three load-bearing properties

These are the properties everything else protects. A change that breaks one of them is rejected regardless of its other merits.

| # | Property | Enforced by |
|---|---|---|
| **PR-1** | **The LLM never marks.** Every flag, score and verdict is deterministic Python | `ADR-0005` · architecture, §4 |
| **PR-2** | **Every judgement is traceable.** A flag cites the learner's own actions | `ADR-0004` · `bias_detail.reason` and `.evidence` |
| **PR-3** | **The event log is the source of truth.** Derived state is reproducible from it | `ADR-0003` · append-only triggers |

PR-1 is what made the pilot's data-integrity check possible: results were recomputed from stored questions and all 16 sessions matched exactly. That check remains a CI test (`BUILD_PLAN` T-016).

## 2.3 Context

```
   Learner ────────►┌──────────────────────────────┐
                    │        Nidan Platform        │
 Clinical    ──────►│                              │
 reviewer           │  Next.js web · Flask API     │◄───► LLM providers
                    │  Jinja admin · Assessment    │      (per-purpose routing)
   Admin   ────────►│                              │
                    └───────────┬──────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  PostgreSQL + pgvector │
                    │      (Supabase)        │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼────────────┐
                    │   Case Factory (P7)    │◄─── public medical datasets
                    └────────────────────────┘
```

---

# 3. Architecture

## 3.1 Component model

Modular monolith (`ADR-0009`). One deployable, enforced internal layering.

```
nidan/
├── api/            HTTP layer — routing, request/response schemas
│   └── v1/
├── domain/         Pure logic. No I/O. Fully unit-testable.
│   ├── assessment/     topics · bias · clinical · engine
│   ├── session.py      state reconstruction from events
│   ├── selection.py    case allocation, allowance
│   └── content.py      case invariants (C-1..C-7)
├── infra/          I/O boundaries
│   ├── db/             SQLAlchemy models, repositories
│   ├── llm/            provider gateway
│   ├── auth/           JWT verification
│   └── telemetry/
├── web/            Jinja templates — admin console only
└── factory/        Case Factory (Phase 7)
```

**`domain/` must not import from `infra/` or `api/`.** Enforced by import-linter in CI (`BUILD_PLAN` T-004). This is what keeps the assessment engine testable without a database and replayable for recomputation.

## 3.2 Request lifecycle

```
HTTP request
   │
   ├─ JWT verified (JWKS, cached)              infra/auth
   ├─ Profile loaded, tier resolved            infra/db
   ├─ Rate limit checked                       api
   ├─ Idempotency key checked                  infra/db
   │
   ├─ Session reconstructed from events        domain/session  ← PR-3
   ├─ Business logic executed                  domain/
   ├─ LLM called if needed                     infra/llm
   ├─ Event appended                           infra/db
   │
   └─ Response serialised per openapi.yaml     api
```

## 3.3 Consultation data flow

```
STAGE 1 — during the consultation
  learner types a question
        └─► session_events(type=question)
                 └─► topic extraction, stored on the reply event
        └─► LLM patient call ──► session_events(type=patient_reply)
                 └─► leakage check ──► leakage_flags (if triggered)

  learner selects an examination or investigation
        └─► session_events(type=examination | investigation)

STAGE 2 — on diagnosis submission
  session_events replayed ──► session state
        ├─► bias detectors        ─┐
        ├─► clinical evaluator     ├─► session_results (+ engine_version_id)
        └─► feedback generator    ─┘         │
                                              └─► feedback_texts
        └─► user_progress updated in the same transaction

STAGE 3 — offline
  session_results ──► analytics, research export, case difficulty monitoring
```

**Note what is absent from Stage 1: no assessment state is ever returned to the client during a consultation.** That is `PRD` P2, enforced by contract tests CT-1 and CT-2.

---

# 4. The assessment engine

The core intellectual property. Everything else is scaffolding around it.

## 4.1 Interface

```python
@dataclass(frozen=True)
class EngineVersion:
    version: str
    detector_version: str
    lexicon_version: str
    encoder_model: str | None
    thresholds: Thresholds        # every constant, from the database

def assess(events: list[Event],
           case: CaseContent,
           engine: EngineVersion) -> AssessmentResult
```

**Pure function.** Same inputs → same outputs, always. No clock, no randomness, no network.

**Thresholds are inputs, not constants.** This is what makes threshold calibration a data operation rather than a code change (`ADR-0004`, `DATA_MODEL` §6.4).

## 4.2 Topic extraction

Currently case-insensitive substring matching against 523 curated phrases across 40 topics.

```
question ──► normalise ──► for each topic: any phrase ⊆ question?
                                  └─► topic marked covered (once per message)
```

Coverage = |required_topics ∩ covered| / |required_topics|.

**Known limitation:** lexical matching misses paraphrase. Every error in detector validation traced here. The hybrid embedding upgrade is `ADR-0013`, Phase 5.

The upgrade preserves PR-2: evidence becomes *"'does a rich evening dinner set it off?' matched 'meal relationship' (similarity 0.81)"* — arguably more informative than a keyword hit.

## 4.3 The three detectors

Each returns `{detected, score, rule_fired, reason, evidence, counters}`.

Let `q` = questions, `a` = questions matching anchor keywords, `m` = questions matching alternatives, `c` = coverage fraction, `k`/`K` = contradictory clues explored.

| Detector | Rules (OR'd) | Score |
|---|---|---|
| **Anchoring** | A1: `q ≥ 4 ∧ a/q > 0.60` · A2: `a ≥ 3 ∧ m = 0` | `max(a/q, 0.85)` |
| **Premature closure** | P1: `q < q_min` · P2: `c < 0.60` | `max(1−q/q_min ⌊0.1⌋, 1−c)` |
| **Confirmation bias** | C1: trap diagnosed ∧ `k = 0` · C2: `q ≥ 5 ∧ k/K < 0.25` | `max(0.90, 1−k/K)` |

**Why OR and not AND:** each rule catches a different failure mode and neither subsumes the other. A1 catches heavy skew across many questions; A2 catches few questions with zero breadth. AND-ing them would miss the second pattern entirely.

**Why `max` for the score:** severity should reflect the strongest available evidence, and should be monotonic as evidence accumulates.

**The guards** (`q ≥ 4`, `q ≥ 5`, score floor `0.1`) prevent small-sample artefacts and prevent a *detected* flag carrying a near-zero score, which would read as self-contradictory.

## 4.4 Validation

18 hand-labelled transcripts across all five cases, four reasoning styles including deliberately paraphrased adversarial cases. Executed through the **production** pipeline, not a reimplementation.

| Detector | Sensitivity | Specificity | Accuracy |
|---|---|---|---|
| Anchoring | 100 % | 100 % | 100 % |
| Premature closure | 100 % | 88 % | 94 % |
| Confirmation bias | 100 % | 82 % | 89 % |
| **Overall** | | | **94 %** (51/54) |

**Zero false negatives across all three.** Sensitivity is weighted above specificity deliberately: a missed bias is a missed teaching moment, whereas a false alarm merely asks a learner to justify reasoning that was already sound.

All three errors occurred on the two paraphrase-adversarial transcripts — the known lexical limitation, not a rule defect.

**This suite runs on every pull request and fails the build below 94 %** (`BUILD_PLAN` T-004). The research claim is a CI check.

## 4.5 The defect this validation found

The first confirmation-bias detector achieved 14 % sensitivity, missing 6 of 7 biased transcripts.

**Cause:** contradictory clues were stored as free-text sentences that shared vocabulary with the anchor keywords. A learner asking *"any family history of heart problems?"* matched the clue *"father diabetes no family cardiac heart history"*, so the system counted them as having explored disconfirming evidence when they had not.

**Fix:** clues rewritten as curated keyword sets disjoint from the anchor vocabulary. Sensitivity 14 % → 100 %, no regression elsewhere.

**Structural prevention:** invariant C-4 (`DATA_MODEL` §8.1) is now checked in CI (`BUILD_PLAN` T-003) and blocks saving in the case editor (T-021). The class of bug is made impossible rather than merely fixed.

---

# 5. LLM gateway

## 5.1 Responsibilities

Single module owning every model call (`ADR-0011`).

```python
def complete(*, messages, system, max_tokens, temperature,
             purpose: Literal["patient","feedback","extraction","judge","grounding"],
             session_id: UUID | None) -> LLMResult
```

| Responsibility | Detail |
|---|---|
| **Per-purpose routing** | Cheap/fast for the high-volume patient turn; stronger model for once-per-session feedback; different models for Factory extraction and judging |
| **Retry** | Exponential backoff with jitter on 429/5xx/empty |
| **Circuit breaker** | After N consecutive failures, stop calling for a cool-down and serve the fallback. Prevents a provider outage making every request hang before failing |
| **Cost accounting** | Every call writes `llm_calls` — tokens, cost, latency, status |
| **Prompt versioning** | Personas are behaviourally significant; version recorded on every session |
| **Fallback** | Rule-based feedback when the model is unavailable, so no consultation ends without guidance |

**Prompt and response bodies are never stored** — only metadata. Storing them would duplicate learner text into a second location for no analytical gain.

## 5.2 Model selection

Determinism note: the patient runs at temperature 0.7 and is **not** deterministic. The **marking** is (PR-1). Conflating these is the most common misunderstanding of the architecture.

| Purpose | Requirement | Current | Selection criterion |
|---|---|---|---|
| Patient | Fast, cheap, disciplined about withholding | Llama 3.3 70B via Groq | **Leakage rate first**, then cost, then latency |
| Feedback | Pedagogical quality, obeys constraints | Same | Upgrade to a stronger model before launch |
| Extraction | Strict schema adherence | — | Phase 7 |
| Judge | Holistic clinical plausibility | — | **Must differ from extraction** — correlated errors otherwise |
| Grounding | Textual entailment | — | NLI model, not an LLM (`ADR-0012`) |

**Pre-launch action:** run a persona-discipline bake-off across candidate models using the adversarial extraction prompts, and select on measured leakage rate.

## 5.3 Persona integrity — the largest residual risk

The patient's *"only reveal when directly asked"* rule is prompt engineering, which is soft. If the model volunteers information, coverage measures the model rather than the learner, and the measurement is invalid.

**Three defences:**

1. **Runtime detection.** After each reply, check whether it revealed a required topic the question did not ask about. Flag to an admin queue; confirmed leaks are excluded from research export.
2. **Adversarial CI.** A fixed set of extraction attempts run against every case persona; a case whose persona leaks a key fact fails the build.
3. **Disclosure.** Leakage rate reported as a limitation in any publication.

**This is the most under-addressed risk in the project** and is `BUILD_PLAN` T-040.

---

# 6. Admin console

Full screen specification in `UX_SPEC` §12. Architecture notes only here.

## 6.1 Why it matters more than it sounds

Clinical content lives in 2 421 lines of Python, and that is still where the application reads it from. T-011 copied the five cases into `cases` / `case_versions` as version 1, **status draft** — so the content is now in a table a case editor can reach, but nothing edits it and nothing reads it at runtime.

The consequence is unchanged until the editor exists: only a programmer can change a case, clinicians cannot review without reading code, every content fix is a deploy, and a keyword typo is a production incident.

It is also now a hard block rather than an inconvenience. The seeded versions are drafts on purpose (`DATA_MODEL` §9.2), the publication gate refuses to publish without an approving clinical review, and case selection (T-017) filters on `status = 'published'` — so **selection correctly finds nothing until T-023 exists**. Four tasks have hit that wall.

**A content platform separates content from code.** The admin console is how clinical content gets managed by the people qualified to manage it.

## 6.2 Architecture

Jinja + HTMX (`ADR-0006`), served by the same Flask application, admin-authenticated, desktop-only. Deliberately *not* Next.js: it is internal, form-heavy, low-traffic, and building it in the existing stack means it does not block API work.

## 6.3 The two screens that carry the value

**Case editor** — structured form with live invariant validation. C-4 (anchor/clue disjointness) **blocks save**, naming the conflicting terms. Editing a published version creates a new draft; published content is immutable (`ADR-0010`).

**Playtest** — split view with the student UI on one side and live instrumentation on the other: matched topics per question, running counters, detector state, clues explored, leakage warnings. This is how a non-programmer sees *why* a detector fired, and it is what makes clinical review possible.

## 6.4 Threshold impact preview

Changing a threshold silently changes what every future result means. The console shows the consequence before applying: how many historical sessions would newly flag, and what the validation suite reports under the candidate values.

Only possible because of PR-3 — sessions can be replayed. This is the mechanism that closes the "thresholds not empirically tuned" limitation.

## 6.5 Build strategy

Custom for product-specific tools (editor, Playtest, AI ops). **Metabase for analytics** — connects directly to Postgres, saves roughly 8 days of building dashboard screens. Buy the generic, build the specific.

---

# 7. Case Factory

Deferred to Phase 7. Designed now so the schema and vocabulary accommodate it (`DATA_MODEL` §12).

## 7.1 Principle

**A generated case is guilty until proven innocent.** It reaches a learner only after passing every gate. The pipeline optimises for precision: rejecting 90 % of candidates is acceptable; publishing one clinically wrong case is not.

## 7.2 Pipeline

```
 1 Source connector       dataset → normalised record
 2 Candidate filter       rules + embedding dedup          — no LLM
 3 Extraction             schema-forced generation         — LLM
 4 Vocabulary mapping     fuzzy + embeddings, quarantine   — mostly no LLM
 5 Grounding check        NLI entailment                   — ADR-0012
 6 Quality judge          different model from step 3      — ADR-0011
 7 Trap self-test         our own detectors                — NO AI
 8 Case bank              status = candidate
 9 Clinical review        human sign-off                   — PRD FR-12.5
10 Governed publish       policy-gated
```

**Step 7 is the novel contribution.** Every generated case is unit-tested against the same detectors that grade learners: synthetic tunnel-vision, thorough, and rushed transcripts must produce the expected flag pattern. A case whose trap is not detectable is rejected regardless of clinical quality.

**Roughly half the pipeline requires no LLM.** Deduplication and vocabulary mapping use embeddings; grounding uses an NLI model; the trap self-test uses plain code. An all-LLM pipeline is the mark of a prototype.

## 7.3 Blocking constraint

**Dataset licences must be verified for commercial use before any Factory code is written** (`PLATFORM_SPEC` §9.1). Several public medical corpora are non-commercial or prohibit redistribution. The Factory must refuse to publish from a source not marked commercial-safe.

---

# 8. Frontend and mobile

`ADR-0006`. Split by audience because the surfaces have genuinely different constraints.

| Surface | Stack | Rationale |
|---|---|---|
| Consumer web | Next.js + TypeScript | Shares patterns and API client with mobile |
| Mobile | React Native + Expo | Reuses React model; one codebase → iOS + Android |
| Admin | Jinja + HTMX | Internal, form-heavy; does not block API work |
| Analytics | Metabase | Buy, don't build |
| Backend | Flask + typed schemas | `ADR-0007` — no migration benefit |

**Types are generated from `openapi.yaml`** and shared between web and mobile. A backend field rename becomes a build-time error rather than a runtime `undefined`.

## 8.1 The UX constraints that are architectural

Three requirements in `UX_SPEC` are not styling preferences — they protect the measurement and must survive any redesign:

| Constraint | Why |
|---|---|
| No coverage meter, question counter, or hints during a consultation | Showing the metric teaches the metric |
| Investigation search filters by name only, never ranked by relevance | Ranking would leak which tests matter |
| The diagnosis dialog contains no readiness or completeness hint | It would itself be an anti-premature-closure intervention |

Enforced by contract tests CT-1, CT-2, CT-3 (`API_CONTRACT` §11).

---

# 9. Deployment

## 9.1 Packaging

Multi-stage Docker (`ADR-0008`). The embedding model is baked into the image so the first request does not pay a download. Gunicorn with 2 workers × 4 threads — LLM calls are I/O-bound, and multiple workers are only safe because session state left process memory (`ADR-0003`).

## 9.2 Platform

Render or Railway as a Docker web service; Supabase for Postgres, auth and storage. Not Vercel — its serverless model conflicts with a persistent Python service making multi-second LLM calls (`ADR-0008`).

Not AWS/GCP/Azure yet. Move when the PaaS bill passes roughly $500/month or a structural need appears. Containerisation keeps that migration cheap.

## 9.3 Environments

| Environment | Data |
|---|---|
| local | docker-compose Postgres, seeded |
| preview (per PR) | branch database, seeded |
| staging | anonymised copy |
| production | real |

## 9.4 CI/CD

```
PR:    lint · typecheck · import-linter · tests · DETECTOR VALIDATION · security · docker build
main:  the above → push image → staging → smoke → manual approval → production
```

**The detector-validation step is unusual and deliberate:** the build fails if accuracy drops below the published 94 %.

## 9.5 Database operations

Alembic migrations run as a release command before new revisions take traffic. Expand-migrate-contract for all schema changes. **Backup restore verified quarterly** — an unverified backup is not a backup.

---

# 10. Observability

| Concern | Approach |
|---|---|
| Logs | Structured JSON to stdout with `request_id`, `session_id`, pseudonymous `user_id`. Never raw question text at INFO, never emails or keys |
| Errors | Sentry, `send_default_pii=False`, releases tagged |
| Health | `/healthz` liveness; `/readyz` checks database, migrations, model loaded |

## 10.1 Metrics that matter

| Metric | Why | Alert |
|---|---|---|
| p95 patient reply latency | Perceived quality | > 6 s |
| **LLM cost per completed session** | The unit economic | > $0.05 |
| Feedback fallback rate | Model reliability | > 5 % |
| **Persona leakage rate** | Measurement validity | > 2 % |
| Consultation abandonment | UX and data quality | > 25 % |
| Assessment duration | Guards against the embedding upgrade regressing the request path | p95 > 500 ms |

Alerting is deliberately small: error rate, latency, circuit breaker open, budget exceeded, failed migration. Nothing else pages.

---

# 11. Security and privacy

## 11.1 Position

The system holds **educational performance data about identifiable professionals**. It holds no patient data — every patient is synthetic. That removes the medical-device and PHI regimes but does not make the data insensitive: a record showing someone reasoned unsafely is reputationally sensitive.

| Threat | Control |
|---|---|
| Cross-user data access | Row-Level Security keyed on `auth.uid()`, plus application scoping |
| Enumeration of another user's session | 404 rather than 403 (`API_CONTRACT` §2.7) |
| Prompt injection via question input | Questions are user turns; the system prompt is server-side only |
| Learner extracts the diagnosis from the model | Persona rules + leakage detection (§5.3) — imperfect, disclosed |
| Credential compromise | Delegated to Supabase Auth (`ADR-0002`) |
| LLM cost abuse | Per-user and per-session rate limits |
| Real patient data entered | Input guard, blocked and logged without storing the text |

## 11.2 Support access

Inspecting a learner's session requires a stated reason, is written to `audit_log`, is time-boxed to 24 hours, and is visible to the user. **Admins never impersonate**; they view read-only data.

Stricter than most early products, and the right default for professional performance data.

## 11.3 Legal position

**Educational simulation, not clinical guidance.** Maintained in the product, the terms, and store listings. Reinforced by the real-patient-data guard and by mandatory clinical review before publication.

---

# 12. Testing strategy

| Layer | Scope | Target |
|---|---|---|
| Unit | `domain/` — detectors, topics, evaluator, selection | **≥ 90 % coverage** |
| Property | Invariants: `a ≤ q`, scores ∈ [0,1], detected ⇒ score > 0 | key functions |
| Case invariants | C-1..C-7, especially **C-4 disjointness** | every case, every build |
| Integration | Repositories, migrations, **RLS policies actually deny** | main paths |
| Contract | CT-1..CT-9 — the API leak guards | all, mandatory |
| E2E | Full consultation → feedback | 3 happy, 2 failure |
| **Validation** | 18 labelled transcripts | **≥ 94 %, build-blocking** |
| Adversarial | Persona extraction attempts per case | every case |
| Golden file | 16 pilot sessions recompute identically | every build |

**Coverage is enforced on `domain/` only.** Chasing coverage on I/O glue produces tests that assert mocks.

**The two most important tests in the codebase** are CT-1 (session start leaks no case internals) and CT-5 (no response contains bias vocabulary). One protects the measurement; the other protects the learner.

---

# 13. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Patient reply latency | p95 < 6 s |
| NFR-2 | Assessment computation | p95 < 500 ms |
| NFR-3 | Page render (non-LLM) | p95 < 400 ms |
| NFR-4 | Availability | 99.5 % |
| NFR-5 | Zero data loss for completed consultations | 100 % |
| NFR-6 | Concurrent consultations | 50 without degradation |
| NFR-7 | LLM cost per completed session | < $0.05 |
| NFR-8 | Detector accuracy on the validation set | **≥ 94 %** |
| NFR-9 | Accessibility | WCAG 2.1 AA on the learner flow |
| NFR-10 | Recovery point objective | ≤ 24 h |

NFR-6 is deliberately modest. Designing for 10 000 concurrent users would be speculative.

---

# 14. Research operations

The product is commercial; research participation is **opt-in and never default** (`PLATFORM_SPEC` §10.3). A paying user is never silently placed in a control arm.

**Causal claims require a control group.** The pilot showed coverage rising 45.3 % → 79.7 % (*p* = 0.036), but every participant received feedback, so improvement cannot be separated from practice effects. A no-feedback control arm resolves this; a **wait-list design** — controls receive full feedback when the study closes — resolves the ethical objection and is familiar to ethics committees.

Ethics approval is required before any controlled study.

The research export (`DATA_MODEL` §11.7) applies three protections in one query: consent required, leakage-confirmed sessions excluded, pseudonymous identifiers only.

---

# 15. Open technical questions

| # | Question | Recommendation |
|---|---|---|
| TS-1 | Stream patient replies (SSE)? | Not in v1. Revisit if p95 stays above 5 s |
| TS-2 | Read replica for analytics? | Not until analytical queries measurably affect writes |
| TS-3 | Self-host the embedding model or use an API? | Self-host — no per-call cost, no latency, data stays local |
| TS-4 | Partition `session_events`? | No. Revisit past ~50 M rows |
| TS-5 | Multi-region? | No. Users cluster by institution |

---

*End of Technical Specification. Decisions live in `adr/`; supersede rather than edit.*
