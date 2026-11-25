# Nidan — project context

A bias-aware virtual patient simulator. Medical trainees interview an LLM-driven
patient, order examinations and tests, submit a diagnosis, and receive feedback on
**how they reasoned** — not just whether they were right.

**Current state:** Phases 0–3 complete and **Phase 4 is 3 of 6 — 32 of 35
tasks, 76 days of 85.** The research is published and validated; the platform
has a schema, a repository layer with tenant scoping, event-sourced sessions,
authentication, anonymous trials, a replayable assessment engine, the
free-tier allowance, the 16 pilot sessions imported into it, the whole admin
console (case editor, Playtest, clinical review), the `/v1` JSON API, a
Next.js web app a learner can sign in to, take a consultation in, and read
feedback from, their own history and progress, a worker that performs the
outbound work behind both 202s, and — as of T-040 — **a persona-leakage
monitor on both question paths, an admin queue that can act on it, and the
de-identified research export it protects.**

**T-040 closed on 24 Nov 2026** and found four things its own criteria
assumed. Two are worth knowing before any Phase 4 task: **RLS binds
`nidan_admin`**, so an admin screen that joins `sessions` renders *empty*
rather than erroring (migration 034 and the rule below), and **`DATA_MODEL`
§11.7's research export did not exist** — it was a query in a document, which
made T-040's own third criterion satisfiable on paper. Its build log §9
records a content problem in eight of the ten cases that has **no task and no
owner**, and §8 records what the suite found about itself on its first full
run.

**T-030 closed on 22 Nov 2026** — 19 days after its code merged, because it
had raised five questions about its own contract and two were blocking. The
last was API-9, GDPR erasure, settled as `ADR-0018`. Its build log §10 is
worth reading before Phase 4: three items in it were found while writing the
log rather than while building the task, and **item 5 is a launch feature with
no owner** (see below).

**Phase 3 closed on 23 Nov 2026** with T-037 (history and progress, Yogesh)
and T-038 (account jobs worker, Vraj). T-038 found two things its own
acceptance criteria assumed and the codebase did not have: **there is no
payment provider** — Stripe is T-041, one phase later — so the erasure's
billing step records `no_provider_configured` rather than claiming a
cancellation; and there was no email infrastructure, so the sender is a port
whose one adapter writes each message to `logs/outbox/` as files. **Nothing
reaches an inbox until `EMAIL_ADAPTER` names a real provider**, and S-20's two
promises are now kept only when that and `SUPABASE_SERVICE_ROLE_KEY` are set —
but a missing one refuses visibly rather than recording the step as done.

**Phase 4, commercial readiness — T-040 done, 5 tasks and 14 d left.** T-041
(Stripe) is the one that retires `api/v1/contract.py`'s remaining three 501s
and fills in `infra/billing.py`'s empty seam.

**T-043 and T-044 were built on 25 Nov 2026** (Yogesh): the AI Ops page
(`/admin/ai`, A-08) with a monthly budget that degrades the gateway, and the
clinical-content and topic-lexicon editors (A-06, A-07). Two things changed
underneath them that are worth knowing: **failed and fallback model calls now
write `llm_calls` rows** (rule below), and **the lexicon editor exports a
migration instead of saving**, because the engine scores from `topics.py`.
**Stripe is deferred past the end-of-November demo** (Vraj, 24 Nov), so T-041
and T-042 are not being built before it.

**The gap with no task: the anonymous trial cannot use `/v1`.** Every
consultation endpoint is `@require_auth`, while `UX_SPEC` S-09/S-10 say
"Auth: Both" — so a trial visitor's only path is the `api/routes.py`
prototype, and `PRD` FR-2 makes the trial a launch feature. Raised in T-030's
build log as debt item 5. **It needs a task and an owner, and with Phase 3
closed it is the only launch feature nobody is holding.**

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
no longer writing cases; it is **review turnaround**, and the console runs on
`localhost`. **Deployment is `T-045` criterion 1** — "deployed to Render:
staging then production, migrations on release" — the last task of Phase 4,
2 d, owned by both. Two earlier versions of this file said no task in any
phase deployed anything, which was wrong both times; it is in the plan, at the
end of the phase now starting. See `REVIEWER_ONBOARDING.md` for what a
reviewer needs once it is up.

**Phase 4 continues with T-041** (5 tasks, 14 d). Clinical review still runs
beside all of it: it is calendar time, and ten reviewed cases is the launch
gate.

---

## ⚠️ Read only what you need

The specs total ~40 000 words. **Do not read them all.** Find your task below and
read only those sections.

| Task | Read |
|---|---|
| Anything at all | This file, then `docs/PROJECT_MAP.md` |
| What is every file in here? | `docs/PROJECT_MAP.md` — the full tree, annotated |
| Why was X chosen? | `docs/spec/adr/` — 18 one-page records. **Check here before re-arguing a decision** |
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
| **Deploying the database to Supabase** | `docs/process/SUPABASE_DEPLOYMENT.md` — there is no file to upload; it is 35 migrations |
| **Signing in to `/admin` locally** | `docs/process/LOCAL_ADMIN_ACCESS.md` — every refusal is an identical 404, so work through it in order |
| **Running the demo** | `docs/process/DEMO_RUN_SHEET.md` — bring-up, the admin cookie, and the three acts, in order |
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

**The one place the spec disagreed with that is settled: `questions_remaining`
is absent, permanently.** `API_CONTRACT` §6 argued for it and cited `UX_SPEC`
S-10 as surfacing it near zero — and S-10's table of what is deliberately
absent *opens* with "Question counter | U2", so §6 was misreading the document
it leaned on. Nothing is lost: the cap is a refusal, not a gauge. 429
`question_limit_reached` carries `{"limit": 40}`, which is what drives S-10's
disabled input, and a client that wants the figure earlier counts `transcript`
entries of `type: question` from the response it already has.
`test_the_cap_stays_derivable_without_a_counter_field` pins that premise,
because if the transcript ever loses its discriminator the argument for
re-adding the field becomes true. (API-6, settled 11 Nov 2026 ·
`API_CONTRACT` §13)

**The 40 is declared twice, and the live one is not the one you would
guess.** `QUESTIONS_PER_SESSION` in `consultation.py` is what refuses the
41st question; `QUESTION_CAP` in `sessions.py` is **referenced by nothing** —
an earlier version of this rule called it "the single home for the 40", which
was wrong when it was written. Change `consultation.py`'s, and if you are
tidying, delete the other rather than wiring it up: the cap belongs beside
the handler that enforces it. (T-030 build log §10, item 1)

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

**The real-patient-data guard never stores what it refused, and the guard
runs on BOTH question paths.** `domain/guard.py` returns a reason code and
never a fragment of the input: `DATA_MODEL` §8.2 says `input_blocked` records
"never the offending text", and storing it would put real patient data into
the table we keep for ever, under the name of protecting it. Three things hold
it — `Detection` carries one catalogued field, `events.py` refuses the append
if the payload has `text`/`content`/`message`/`input`, and
`test_the_blocked_text_reaches_nothing` reads **every** payload back out of
Postgres rather than checking the one event it expects. The 422 names the
category, never the characters. It is wired into `api/v1/consultation.py`
*and* `api/routes.py`, because `PRD` P4 does not exempt anonymous visitors and
the prototype is the only path they have — every `/v1` consultation endpoint
is `@require_auth`. **It is deliberately conservative**: a bare name, a bare
date and an age do not block, because a false block discards the learner's
question (`UX_SPEC` S-10) and teaches them the tool is broken. Tighten it on
evidence from `input_blocked` reasons, not on a hunch. (T-035 · `PRD` P4)

**Backfilled events are marked and must be excluded from timing analysis.**
The 16 pilot sessions carry `provenance: "backfilled"` in every event payload;
their timestamps are synthetic because the JSON never recorded the interleaving.
Any query computing think-time must filter them out. (`DATA_MODEL` §9.3)

**The gateway cannot write its own `llm_calls` row, and that is enforced.**
`pyproject.toml`'s import-linter contract forbids `nidan.infra.llm` from
importing `nidan.infra.db.engine` and **counts indirect imports**, so every
repository is out of reach too. `call_llm` therefore returns an `LLMResult`
— `.text` plus an `LLMCall` — and the **caller** records it inside a scope it
already holds. `infra/feedback.py` is under the same restriction and passes
them up through `FeedbackResult.call`, which is `None` on the rule-based
fallback because nothing was billed. (`tests/db/test_llm_calls.py`)

**The configured model can be retired out from under you, and no test will
say so.** `python test_api.py` is the only check, because T-002 criterion 1 is
that no test makes a network call — so the suite never asks a provider whether
`GROQ_MODEL` still exists. Groq retired `llama-3.3-70b-versatile` on
2026-08-16 and it took until 2026-11-04 to notice. **Run `test_api.py` after
changing a model and before any demo or reviewer session.** It goes through
the real gateway on purpose: when it built its own client it reported "empty
response" for a model the application handled fine. PR-1 is what makes this
survivable — the detectors, the 94.4 % validation and the golden record never
touch a model — but a model change *does* invalidate the leakage tuning of all
ten case personas. (`TECH_SPEC` §5.2 · `pricing.py` carries `PRICES_CHECKED`)

**The patient's model is a reasoning model, and `message.reasoning` must never
be read.** `max_tokens` covers deliberation *and* content on `openai/gpt-oss`,
so `GroqProvider` sends `reasoning_effort="low"` — without it a 60-token
budget went entirely to deliberation and returned a sentence cut off mid-word,
and a truncated reply is worse than a failure because it is logged as a
`patient_reply` and the engine scores it. The deliberation comes back in a
separate field that discusses the system prompt — for the patient, the whole
case including the answer. **Falling back to it when `content` is empty is the
CT-1 leak by a route `case_view.py` does not guard**, so an empty reply raises
and the learner keeps their question.
(`test_the_models_reasoning_never_becomes_the_patients_words`)

**The circuit breaker is process state, and that does not break `ADR-0003`.**
Three consecutive failed *calls* on one `provider:model` open it for 30 s;
after that one probe decides whether it closes or reopens. "Session state is
never held in the process" is about a learner's consultation — replaying the
log must give the same answer on any worker. This holds no session, no learner
and no event, only how a dependency is behaving right now, and losing it on
restart costs a count. It is **per `provider:model`**, because `TECH_SPEC` §5.2
routes feedback to a stronger model than the patient turn and a global breaker
would silence working feedback over a rate-limited patient model. Each of the 2
workers trips its own, and the lock is not decorative: `--workers 2 --threads
4` means four threads share it. `CircuitOpen` is a plain `RuntimeError` so the
callers that already degrade on `Exception` needed no change — 503
`patient_unavailable` without consuming the question, and the rule-based
feedback fallback. (`TECH_SPEC` §5.1 · `tests/test_circuit_breaker.py`)

**`purpose` has five values and `playtest` is not one of them.** Migration
015's CHECK allows `patient`, `feedback`, `extraction`, `judge`, `grounding`.
Playtest passes `purpose="playtest"`, which is right for the log line and
unrecordable — and migration 024 withheld `llm_calls` from `nidan_reviewer`
on purpose, so recording it would mean widening a CHECK *and* granting the
narrowest role INSERT on the billing table, to account for an author's own
turns against a draft. The admin Playtest route logs and records nothing;
`repositories/llm.py` mirrors the five as `PURPOSES` and raises in Python
rather than letting a CheckViolation abort a transaction opened for work that
mattered more.

**A failed or fallback call writes an `llm_calls` row, at $0 (T-043).**
The gateway attaches a `status='failed'` `LLMCall` to the exception it
raises (`gateway.failed_call(e)`), and rule-based feedback returns a
`status='fallback'` one, so the AI Ops page's error and fallback rates have
denominators. Before T-043 neither wrote anything and both rates read 0 %.
Neither row is an event, so the rule below still holds. **The monthly budget
is injected, not imported**: `create_app` registers `infra/budget.py`'s check
with `gateway.set_budget_guard`, because `infra.llm` may not reach the
database. At 100 % of `LLM_MONTHLY_BUDGET_USD` every purpose drops to
`pricing.cheapest_model()`; a failing check fails open.

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
needs new topics, so each is two migrations, not one** — and since T-044 the
second one is generated: `/admin/content/lexicon` lets an author propose
topics and phrases, test questions against the result, and export the
migration **plus** the `TOPIC_KEYWORDS` entries to commit together. It never
writes the lexicon itself, because the engine reads `topics.py` and a saved
phrase would change nothing but the copy. A topic added to `topics.py`
without a migration leaves the database disagreeing with the code, and
`tests/db/test_seed.py` is what says so. Run `build_golden.py` before
committing an export: a lexicon change re-scores every replayed session.

**The master lists are different: the A-06 editor writes the database
directly**, because `/v1` reads `examinations`/`investigations` at request
time. So a live database can now hold items `cases.py` does not, and that is
expected: `cases.py` is the seed for a fresh database. Keys are never
renamed and rows never deleted (migration 036 grants no DELETE), only
retired with `is_active = false`.

**An error code lives in three places and is compared in all three.**
`nidan/api/errors.py` holds `CATALOGUE` as data, `API_CONTRACT` §10 holds
the table, `openapi.yaml` holds the enum. `error()` raises on a code that
is not catalogued, and on a status that contradicts the one §10 gives it —
`error("not_found", ..., 403)` is the §2.7 leak and reads as plausible.
Adding a code means all three in one commit; `tests/test_api_contract.py`
fails otherwise. (CT-6, CT-7)

**Touching `openapi.yaml` means three things in one commit, not one.**
The contract, the code, **and** `web/src/api/schema.ts` — run `npm run gen:api`
in `web/` and commit the result, or the "Web app" CI job fails on
`npm run check:api`. **A description-only edit counts** — the generator copies
them into `schema.ts` comments, which is why settling API-6 touched the
frontend despite changing no field.
And **YAML permits a duplicated key while a contract does not**: T-030 slice 5
added a second `description:` to `DELETE /me` without removing the first, and
because `yaml.safe_load` keeps the last one silently, every assertion in
`tests/test_openapi.py` passed over a file the type generator refused — so a
backend mistake surfaced in the frontend's CI four days later. That test now
parses with a strict loader; `test_the_strict_loader_actually_rejects_a
_duplicate` proves the guard bites.

**A request body the contract declares must be one a handler reads.**
`tests/test_request_body_conformance.py` walks the AST of `api/v1/` for the
keys each handler takes off the JSON body and compares them with the schema
the contract attaches to that operation — in both directions. It exists
because the CT tests guard what must be **absent** from a response, and
nothing checked that the shape we *declare* is the shape we *read*: three
drifts in three consecutive tasks (`diagnosis` for `text`, `helpful` for
`was_helpful`, the whole `Feedback` schema) each passed CI here and failed
only in the frontend's CI. On its first run it found three more, including
`consent_version` — read and required by `PATCH /me`, declared nowhere, so a
generated client **could never give research consent**. It is static, so it
runs in 0.2 s and still runs when Docker is down. If it ever reports a field
`identity.py`-style whitelist filtering makes it miss, fix the walk; a test
with false positives gets switched off. (T-035)

**Every operation `openapi.yaml` declares must answer.** If it is not
built, it is listed in `nidan/api/v1/contract.py` and returns 501 with the
envelope — which is what sync point S-1 means and what did not exist until
T-030. The list only shrinks, and a line left behind after a slice
implements it fails the suite rather than shadowing the real route.

**`session_events` and `audit_log` refuse DELETE, and `audit_log` refuses
UPDATE, including to the table owner.** So a teardown or a cleanup must
TRUNCATE, never DELETE — and a cascade into either table fails the whole
transaction, which is why deleting a profile needs the session tables
truncated first.

**`session_events` permits exactly one UPDATE, and nothing else.** Migration
033 (API-9, `ADR-0018`) replaced the unconditional trigger with one that
allows `payload->'text'` to become `"[redacted]"` provided `id`,
`session_id`, `seq`, `type` and `created_at` are identical and no other key
is added, removed or altered — and refuses everything else. That single
transition is what makes `DATA_MODEL` §10.2's erasure possible, so
`DELETE /me` is a real 202 rather than a 501. **Do not widen it.** The whole
safety argument for the decision is how narrow it is, and
`TestWhatTheTriggerStillRefuses` enumerates eight mutations it still
refuses — including the one that matters, smuggling a second change into the
same statement as the redaction. `audit_log` keeps `forbid_mutation()`,
because the record of an erasure must not be editable by the thing
performing one. (verified against the running database ·
`tests/db/test_erasure.py`)

**The erasure covers four event types and a table §10.2 forgot.** `question`,
`early_diagnosis`, `diagnosis` **and `patient_reply`** all carry `text`; the
repository's predicate is `payload ? 'text'` rather than a list of names, so
a type added later is covered on the day it is added. And
`feedback_texts.lines` is in it, because `PRD` P3 requires feedback to cite
the learner's own questions — without that statement their words survive
verbatim in a table the erasure never looked at. §10.2 named two of the six
places for nineteen days.

**An erased profile is invisible, and that is one filter in one method.**
`ADR-0002` means the token stays valid until T-038's worker deletes the
credential, so for up to 24 h an erased account can still make authenticated
requests. `ProfileRepository.get()` filters `deleted_at IS NULL` and every
learner route reaches the profile through it. `update()` and
`touch_last_active()` are scoped the same way — **the first version was not**,
and a `PATCH /me` wrote the display name back onto the erased row and then
returned 404, so the refusal looked right while the erasure was being undone.
`ensure()` raises `AccountErased` → 409 `account_deleted` rather than
resurrecting the row, because `ON CONFLICT DO NOTHING` makes a resurrection
attempt indistinguishable from a retry.

**A test that copies the repository must exclude `node_modules`.**
`tests/test_validation_gate.py` clones the repo into a tmpdir to prove the
detector gate fails on a degraded threshold. T-032 added `web/`, and from the
first `npm ci` that clone carried 457 MB and ~100 000 files — twice per run.
**The suite went from 80 seconds to over 45 minutes at 0 % CPU with no
output**, which reads as a hang rather than a fault, and nothing failed so
nothing said why; it was found by `lsof`-ing the stuck process. The two
duplicated ignore lists are now one `_IGNORE` constant, and
`test_the_repo_copy_excludes_the_javascript_tree` asserts the exclusion — not
a runtime, which would be flaky. If you add a directory that `npm`, `uv` or a
build tool fills, add it there too. (T-035)

**`audit_log` is the jobs queue, and it refuses UPDATE — so a job cannot be
marked done.** It is done when its per-step completion rows exist, and
`AuditRepository.pending()` is the difference between the two sets. Three
things follow and they are not incidental: a crash between a remote call and
its completion row costs one retry rather than a lost request; a step whose
row exists is never re-attempted, so a retry does not send a second
confirmation email; and adding a step to `STEPS` makes **every past request
pending again for that step alone**, which is what you want and is why each
step must be separately skippable rather than keyed off the request.
`test_every_step_the_vocabulary_declares_has_an_implementation` is what stops
a new step from making every run fail. (T-038 · `tests/db/test_jobs_worker.py`)

**The worker sends the confirmation BEFORE deleting the credential, and the
order is forced.** The address lives in `auth.users`, which Supabase owns and
`nidan_service` has no grant on — so after the deletion there is nothing left
to fetch. `UX_SPEC` S-20 says "sent to the old address before it is removed";
that is a description of the only workable order, not a preference.
`test_the_email_is_sent_before_the_credential_is_deleted` asserts the call
order rather than reading the step list, because the step list is what someone
changing this would edit.

**`SUPABASE_SERVICE_ROLE_KEY` bypasses RLS entirely and belongs to the jobs
worker alone.** `nidan/infra/identity_admin.py` is the only module that reads
it. Never in `web/`, never as any `NEXT_PUBLIC_*` variable, never in
`HANDOFF.md`, not in docker-compose's `app` service, and never in a log line,
an exception message or an `audit_log` row — a `job.step_failed` row survives
the erasure, so a key in one would outlive the account it deleted. **When it
is absent the step refuses**, typed `NotConfigured` (not retryable) rather
than `CredentialDeletionFailed` (retryable), and is never recorded as done:
recording it would make S-20's "within 24 h" permanently and silently false.
(`SECURITY_SPEC` §7.9)

**The export reads no detector column, and that is CT-5 by construction.**
`session_results` has `bias_detail`, `anchoring_detected` and six more, and an
export is a file emailed to the learner — so `PRD` P1 applies to it exactly as
it applies to a response. `repositories/export.py` does not read those columns
at all rather than reading and filtering them. It also omits `research_pid`,
which is the key linking an erased account to retained results: a copy in a
file the learner keeps hands whoever later reads that file the one value that
re-identifies the anonymised dataset. The import-linter contract **"the jobs
worker must not import the web layer"** is what keeps this decision in place —
`import nidan.api.v1.reasoning` would execute `api/v1/__init__.py` and
register every route on a Flask blueprint as a side effect.

**Nothing emails anyone yet, and `EMAIL_ADAPTER` must never fall back.** The
only adapter built writes each message to `logs/outbox/` as files. An unknown
adapter name **raises**, because a deployment that asked for a real provider
and silently got a directory would believe it had sent mail it had not sent,
and the only evidence would be the absence of complaints. `logs/` is gitignored
as a whole directory — `*.log` alone left `logs/outbox/<id>/nidan-export.json`
committable, and that file is a learner's own questions.
(`tests/test_outbox_is_not_committable.py`)

**There is no payment provider, so the erasure's billing step says so.**
Stripe is T-041, one phase later. `NoProvider.cancel()` returns
`no_provider_configured` and the worker records that verbatim. A row claiming
a payment provider was cancelled, written by a system with no payment
provider, is a false statement in the one record that survives an erasure —
and it would read as true for ever, including to whoever eventually asks
whether an erased user was still being billed.

**`DATABASE_URL` lives in `.env` and alembic cannot see it there.** The
application reads `.env` through pydantic-settings; `migrations/env.py` reads
`os.getenv("DATABASE_URL")` and nothing else. So the app can be correctly
configured while `alembic upgrade head` says "No database URL", and the two
statements are both true. Export it, or run through
`scripts/demo_up.sh`, which does. **And check the port against
`POSTGRES_PORT`** — compose publishes the container at whatever that says, and
on a machine where 5432 was taken it is not 5432.

**Compose's `app` service takes port 8000 and serves a stale build.** It has
`restart: unless-stopped`, so it comes back after a reboot, and its image is
baked at build time with **no source mount** — so a demo run against it works,
quietly, on whatever the code looked like when it was last built. That is worse
than a crash. `python -m nidan` runs the working tree; `scripts/demo_up.sh`
stops the container first and says that it did.

**Every case is a draft, so `/v1` cannot start a consultation until one is
published — and that reads as a bug.** `SelectionRepository.candidates()`
returns only published versions, so `POST /v1/sessions` answers
`no_cases_available` (503) and the web app has nothing to serve. The test
suite never sees it: its fixtures publish a case themselves. On a laptop,
`python scripts/publish_for_demo.py --all` fixes it — it goes **through**
migration 007's gate by inserting an approving review, never around it, and
`--undo` reverses it. **It refuses any non-local database**, because the rows
it writes are fabricated approvals and `clinical_reviews` is the evidence for
the launch gate. The reviews it writes are attributed to "Demo Fixture (not a
clinician)" and **do not count** towards the ten reviewed cases.
(`tests/test_publish_for_demo.py` · `COMMANDS.md`)

**A leakage flag never excludes anything by itself — only `confirmed = true`
does, and only a person writes it.** `severity` is triage: the queue sorts on
it and `DATA_MODEL` §11.7's export does not read it at all. `high` means the
learner never asked about the topic anywhere in the session, so coverage
credits them for something they did not do; `low` means they asked earlier and
the patient repeated itself, which cannot change the score. A detector that
could discard its own inconvenient sessions would be the LLM marking by proxy.
(`ADR-0005` · `tests/db/test_research_export.py`)

**`domain/leakage.py` is deliberately SENSITIVE, and `domain/guard.py` is
deliberately conservative. Do not make them consistent.** A false block in the
guard discards the learner's question and teaches them the tool is broken. A
false leakage flag costs an administrator one click, while a miss costs the
validity of every measurement taken through that persona and nothing
downstream would ever reveal it. The asymmetry is the design.

**Signing up a new account cannot work against the local database, and that
is the architecture.** `profiles.id` references `auth.users(id)`, which on a
laptop is migration 001's three-column stub that nothing populates — Supabase
issues the credential in the cloud, and the local stub never hears about it.
So `POST /v1/me` raises `ForeignKeyViolation` and the learner reads "We
couldn't finish setting up your account." It is not a bug in the web app and
no amount of fixing one helps; it resolves itself the day `DATABASE_URL`
points at the Supabase project (`T-045` criterion 1). Until then
`scripts/seed_demo_accounts.py` makes the accounts ahead of time, in both
places, through the **publishable** key and the public signup endpoint —
never the service_role key, which `SECURITY_SPEC` §7.9 gives
`identity_admin.py` alone.

**`ProfileRepository.get()` names `WHERE id = :me`, and removing it is a
privacy bug that looks cosmetic.** Migration 016's `own_profile` really does
scope a bare SELECT to one row — for `nidan_app`. Migration 024 then added
`privileged_profiles_are_mutually_visible` `TO nidan_admin, nidan_reviewer`,
policies are OR'd, and `.first()` started taking an arbitrary privileged row:
every console screen greeted whoever signed in by **another administrator's
name**. Authorization was never affected — `require_role` reads the profile
under `current_actor()`, which stays a plain `AuthenticatedUser` even for an
admin — but any future admin screen that asks "who am I" would have got the
wrong answer. The test that `own_profile` still bites therefore queries
`profiles` directly rather than through `get()`.
(`tests/db/test_repository_scope.py`)

**Every figure on the admin dashboard is read from the database, and the two
an audience expects are absent — one still deliberately.** "142 sessions today", "118
completed", "$1.84", "3 cases awaiting review", "6.2 % feedback fallback" and
"10 published · 2 drafts" were literals in `dashboard.html`, wrong by an order
of magnitude against the data underneath. **Sessions today and completed could
not be replaced**: `sessions` has RLS on, and an admin scope sees only its own
sessions plus the ones migration 034's flag-keyed policy points at, so a count
would be correct SQL and a false statement about usage — admin visibility of
learners' sessions is A-09's to ask for. Do not put a literal back in that
grid. **The feedback fallback rate was the second one and no longer is**:
T-043 made the rule-based fallback write a `status='fallback'` row, so the
rate now has a denominator and `/admin/ai` computes it. A-01 still omits the
card — the justification beside it is stale, not the figure.

**The "+ New case" scaffold must stay valid, because it is the first thing an
author ever sees.** It seeded `aggravating_factors` in `required_topics`,
which is not in the lexicon, so every case created through that button opened
with a C-3 warning already on it — the one screen whose job is to teach what
valid looks like, teaching the opposite.
`TestTheNewCaseScaffold` reads `initial_content` out of the route's AST and
runs it through `_validate_invariants`, so a key added later is checked too.

**The editor's Save button lives outside the HTMX swap, so it needs
`data-can-save` to stay honest.** The validation panel is re-rendered on every
keystroke; `#save-btn` is in the page header and kept its page-load state. The
panel would say "Save Blocked" beside a working button, and clicking it POSTed
the form, got a correct 400, and **replaced the whole editor with the raw JSON
refusal** — the guard was right and the author lost every unsaved edit. The
fragment now carries `data-can-save` and `editor.html` toggles the button on
`htmx:afterSwap`. The disabled button is a courtesy; `save()` re-checks C-4
server side and is the actual guard.

**RLS binds `nidan_admin`, so an admin screen that joins `sessions` renders
EMPTY rather than erroring.** `own_sessions` has no `TO` clause —
`DATA_MODEL` §10.1 says so and migration 025 exists for the same thing on
`profiles`. The leakage queue hit it and looked like "no leaks". Migration
034's two policies are keyed on the flag, not on seniority: an admin may read
a session **because it carries a flag**, and exactly the event the flag points
at, matched on `session_id` AND `seq` — not the learner's questions. **Do not
widen them to "admins may read sessions"**; A-09 should ask for that itself.
And use `current_admin()`, not `current_actor()`, on any route that needs
them: `current_actor()` returns a plain `AuthenticatedUser` even for an
administrator, on purpose. (`tests/db/test_admin_leakage_queue.py`)

**`validate_personas.py` cannot be a pytest test, and exit 3 is a failure.**
T-002 criterion 1 is that no test makes a network call; extracting from a
persona requires calling the model. So it is a root script with its own CI
job, like `validate_detectors.py`. Exit 1 = a persona named its own diagnosis
or quoted its brief; **exit 3 = a probe never reached the provider**, which
fails on purpose because an outage must not read as a clean bill of health.
**`PROBES` and `PROMPT_MARKERS` are frozen — add to the end, never edit.** A
suite whose inputs move cannot tell you whether the persona got worse or the
probes did. And a model change invalidates all ten personas' tuning, which is
why the job also runs weekly: it is the one check whose result can change with
no commit.

**A key fact is matched on whole words, and the reason is a bug the suite had
on its first full run.** `accepted_diagnoses` holds acronyms as short as two
letters — `case_2`'s first entry is `"pe"` — and the first `_leaked_diagnosis`
used plain `in`, so **seven of nine reported leaks were the word "specific"**,
in replies where the persona was *refusing* to diagnose. A gate that fails the
build on correct behaviour gets switched off, which is worse than no gate.
`TestTheShortAcronymBug` is the regression, and it asserts over the whole bank
rather than the one case that exposed it.

**`_RULES` rule 6 exists because of one probe, and `what_to_order` is the
probe that earns its place.** Rule 4 tells the patient to say the doctor would
need to check — and asked *what* the doctor should order, two personas named
the condition the test was for ("to see if it's reflux", "to check for a
urinary infection"). That is `accepted_diagnoses` out of the patient's mouth
by a route rule 5 does not cover, so rule 6 forbids naming a disease or what
a test is "for" at all. **Editing `_RULES` changes all ten personas**, so
re-run the suite and `test_api.py` after touching it; it does not touch the
golden assessment record, which is recomputed from stored events.

**And editing a persona needs a MIGRATION, because the brief is content.**
`system_prompt` is seeded into `case_versions.content` like everything else.
`api/v1/consultation.py` reads it from there; `api/routes.py` and
`validate_personas.py` read it from `cases.py`. So an edit with no migration
fixes the anonymous trial, leaves **every signed-in learner on the old
brief**, and **the persona suite reports a pass** — it probes the code, not
the bank. Rule 6 shipped in that state for an afternoon. Migration 035 is the
pattern: read each row, rewrite the block, recompute `content_hash`, and
refuse if the old block is not there exactly once.
`test_the_brief_in_the_database_is_the_brief_in_the_code` is what fails now;
the round-trip seed test only ever compared the four fields the detectors
read.

**The full persona suite at `--repeat 2` does not fit Groq's free tier.** 160
calls is ~200 000 tokens and the allowance is 200 000 per *day* — the first
attempt died at probe 69 with `CircuitOpen` and exited 3. CI is `--repeat 1`
(80 calls) for that reason, and the weekly schedule is what accumulates
samples. A gate that goes red on the token budget is a gate people learn to
ignore.

**Volunteering is MEASURED, never gated, and do not "fix" that.** The suite's
first two runs reported eight volunteering leaks and then **none** — same
probes, same personas. The patient model runs at `temperature=0.7`, so a
single sample is not a verdict and a gate on one teaches everyone to re-run CI
until it goes green. `--repeat N` measures it; `TECH_SPEC` §5.3 catches it per
consultation with the runtime monitor and the admin queue (defence 1) and
discloses the rate (defence 3). Gating here would be the weakest of the three
defences pretending to be the strongest.

**Eight of ten cases give away a required topic in their own `opening_line`,
and `case_2` gives away four of eight.** `validate_personas.py --overlap`
reports it. Coverage is NOT inflated — it is scored over `question` events and
the opening line is not one — but a learner who reads the opening line and
sensibly does not re-ask is scored as having missed those topics. **It has no
task**, because narrowing `required_topics` changes the golden assessment
record for all 16 pilot sessions and needs a clinician's view. The suite
subtracts these topics before calling anything a leak, so a patient restating
its presenting complaint is not a finding.

**`accepted_diagnoses` is a key fact; `partial_diagnoses` and the anchor are
not.** "heartburn" and "indigestion" are in `partial_diagnoses` and
`contradictory_clues` *requires* the patient to say them when asked. "I think
it's my heart" is `anchor_topic` doing its job — `PRD` P1's design is that the
patient voices a plausible wrong worry. A suite that punished either would
fail every well-written case and push authors to delete the trap.

**A leakage flag stores topic names and never the patient's words.** The queue
reads the reply live from `session_events` at `event_seq`. A copy on the flag
would survive migration 033's erasure — a learner's consultation preserved in
a table the erasure never looks at, which is exactly what `feedback_texts.lines`
already cost us once.

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
    guard.py              the real-patient-data guard — reason codes only (T-035)
    leakage.py            persona leakage — sensitive on purpose (T-040)
    feedback.py           feedback prompt construction (prose only, no marking)
    feedback_view.py      the feedback screen, recomputed from the log
  infra/                everything that touches the outside world
    llm/gateway.py        the single call site for the LLM; returns metrics,
                          cannot write them — see the rule below
    llm/provider.py       the provider protocol; LLM_PROVIDER resolves it
    llm/breaker.py        the circuit breaker — process state, on purpose
    llm/pricing.py        per-model token prices, dated. cost_usd is NOT NULL
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
      llm.py                llm_calls — what each model call cost (T-031)
      progress.py           trends computed on read; user_progress stays empty
      export.py             a learner's own data as JSON. Reads NO detector
                            column and omits research_pid — CT-5 by omission
      audit.py              ...and the jobs queue: pending() is request rows
                            minus per-step completion rows, because audit_log
                            refuses UPDATE
      base.py               repo_scope(actor) — SET LOCAL ROLE + set_config
      events.py             the append-only log; seq collisions retried
      anonymous.py          ⚠️ the one path where RLS is OFF — keep it that way
    storage.py            session JSON read/write (the research export)
    feedback.py           calls the gateway with domain-built prompts
    identity_admin.py     ⚠️ the ONLY user of SUPABASE_SERVICE_ROLE_KEY — the
                          Supabase admin API: delete auth.users, read an address
    billing.py            the payment-provider seam. One adapter: NoProvider,
                          which says `no_provider_configured`. Stripe is T-041
    email/port.py         EmailPort + the Email it sends; `redacted()` is what
                          a log line gets instead of an address
    email/outbox.py       the only adapter — writes each message to a file
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
  jobs/                 the account jobs worker (T-038) — `python -m nidan.jobs`
    runner.py             the two jobs, one step at a time, per-step scopes
    messages.py           the two emails, as pure functions
    __main__.py           `run` and `status`; exit 1 on a failed step
  api/auth.py           @require_auth · @require_tier('pro') · @require_admin
  api/trial.py          the anonymous trial and its httpOnly cookie
  web/                  templates and static assets
  app.py                create_app() factory · __main__.py runs it

tests/                  test_smoke.py (routes) · test_layering.py (ADR-0009)
                        test_db_access.py (no query bypasses the repositories)
                        test_request_body_conformance.py (the contract vs the
                          bodies handlers actually read — AST, no DB)
  db/                   schema tests — constraints, triggers, RLS (real Postgres)
                        test_repository_scope.py · test_anonymous_scope.py
migrations/versions/    35 Alembic migrations ← the schema's source of truth
                        (017, 019, 026-032 are generated from cases.py
                         and topics.py; see the rule below)
docs/build-log/         what was actually built, one doc per finished task
docs/spec/              the build contract — 6 docs + adr/  ← the source of truth
docs/design/            superseded design docs (historical)
docs/detector_validation.md   generated by validate_detectors.py
sessions/               16 real pilot sessions (JSON)
report/                 the research paper (LaTeX + PDF) and presentation
*.py at root            research tooling — validate_detectors, validate_personas,
                        analyze_sessions, test_api
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
pytest                             # 1273 tests (see docs/spec/TEST_STRATEGY.md)
ruff check . --fix                 # style
mypy nidan/domain --strict         # types (domain only)
lint-imports                       # check the domain/infra/api layering contract
python validate_detectors.py       # detector validation — must report >= 94%
python validate_personas.py        # persona leakage — 80 real model calls (T-040)
python scripts/research_export.py -o data.csv   # DATA_MODEL §11.7
python analyze_sessions.py sessions # paired statistics over session JSON
python test_api.py                 # check the LLM key works
python scripts/build_status.py     # regenerate docs/build-log/STATUS.md
python scripts/build_golden.py     # regenerate the golden assessment record
python scripts/backfill_pilot.py   # import the 16 pilot sessions (run-once, idempotent)
python scripts/publish_for_demo.py --all   # publish drafts LOCALLY so /v1 can serve a case
python scripts/seed_demo_accounts.py       # the four demo accounts, Supabase AND the local stub
python scripts/admin_token.py              # a token for /admin, copied to the clipboard
./scripts/demo_up.sh               # db + migrations + cases + warm LLM + API + web app
python -m nidan.jobs status        # the account jobs queue — what is outstanding
python -m nidan.jobs run           # ...and do it (T-038; idempotent)
pip install -e ".[docs]"           # once, for the .docx generator
python scripts/build_docx.py       # regenerate every .docx from its Markdown

# database (T-010) — needs the stack up: docker compose up -d db
alembic upgrade head               # apply all 35 migrations
alembic downgrade base             # tear the schema down
pytest tests/db -q --no-cov        # 476 schema, repository and route tests, real Postgres
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
  them is **open** as of 29 Oct 2026. What they need now is hosting, which is
  `T-045` criterion 1 (Render, staging then production) — the last task of
  Phase 4. Ten reviewed cases is `T-045` criterion 5 and the launch gate.
  **This is settled, not an open question**: the end-of-November demo runs on
  Vraj's own laptop by design, so do not raise hosting as a blocker or offer
  to pull it forward.
- **Content authoring is done, review is not.** All ten cases exist as
  drafts. None can be published until a clinician approves it — the gate is
  a database trigger, not a convention. **Clinical review is now the whole
  of the critical path**, and it is calendar time, not engineering time.
