# Nidan handoff — Yogesh ⇄ Vraj

Two laptops, one Claude account, no shared chat history. Claude on one laptop
cannot see or message Claude on the other. **This file is how work crosses
between them.** It lives on its own branch, `handoff`, which shares no history
with `main`: no pull request, no CI, no merge conflicts with code.

---

## For Claude — read this part every session

**At the start of a session**, before any task work:

```bash
git fetch origin handoff
git show origin/handoff:HANDOFF.md
```

Tell the person what is open in **their** inbox. If an item blocks the task
they asked for, say so before starting.

**At the end of a session**, or the moment something is found that the other
person must do, add it to **their** inbox and push:

```bash
git fetch origin handoff
git worktree add ../nidan-handoff handoff     # first time only, on each laptop
cd ../nidan-handoff && git pull --ff-only
# edit HANDOFF.md
git commit -am "handoff: <one line>" && git push origin handoff
```

Never check out `handoff` in the main working folder: it has none of the
project's files, and switching to it would look like the whole repo vanished.

**Rules**

- Write to the *other* person's inbox. Your own items are theirs to send you.
- One item = what, why, where (file / branch / PR), and what "done" looks like.
  Written so the other Claude can act on it cold, with no chat history.
- Number items `V-n` (for Vraj) and `Y-n` (for Yogesh). Never reuse a number.
- When an item is done, move it to **Done** with the date and the commit or PR.
  Do not delete items.
- **No secrets.** No keys, tokens, passwords, `.env` values. This is on GitHub.
  Say "sent privately" and send them some other way.
- Dates as YYYY-MM-DD. British English.

---

## Inbox — for Vraj

- [x] **V-12** (2026-11-23, from Yogesh) · *Answered 2026-11-23 — see Y-27.* · **Two more stale *response*
  schemas, one of which broke the T-033 dashboard — fixed. The conformance
  test now needs its other half.** Branch `feat/t-037-history-progress`
  (`89f60ae`).

  1. **`SessionPage`** said `items[].{id, diagnosis_verdict}` and a top-level
     `next_cursor`; `list_sessions` and `API_CONTRACT` §7 send
     `data[].{session_id, verdict, coverage_pct, ended_at}` and
     `pagination{next_cursor, has_more}`. My T-033 dashboard was built from
     the schema, so **against the real API it would have listed no sessions,
     no resume banner, no streak** — its tests passed because they used the
     same wrong shape. Reconciled, regenerated, dashboard fixed.
  2. **`Progress`** had a `trends` map; `read_progress` and §7 send the two
     streaks, `has_sufficient_data`, `coverage_series`, `reasoning_trends`
     `{id,label,last10_rate,prev10_rate,direction}` and
     `verdict_distribution`. Reconciled.

  **Your `test_request_body_conformance.py` is exactly right and covers the
  request half.** All five drifts I hit were the other kinds: two request
  bodies (now covered by your test) and **three response bodies**, which
  nothing checks. The response side is where a client is silently wrong rather
  than refused — a missing request field gets a 422, a renamed response field
  just reads as `undefined`. Worth a response twin: run each implemented
  route's happy path in the DB tests and validate the JSON against the
  operation's 2xx schema (`jsonschema` against the resolved component). I have
  not added it — your tests, your call.

  Also, answering yours:
  - **Y-23 — confirmed**, no objection to T-032/033/034/036 marked DONE at
    merge. I have left T-037 unmarked for you to mark at merge the same way.
  - **Y-25** — S-20 is not in T-037 (it is S-17…S-20's task), so the new copy,
    the 202 and `account_deleted` will be handled there. Noted, not lost.
  - **Y-26 — done**: `publish_for_demo.py --all` ran on my laptop, 10 published,
    attributed to the demo fixture. First time a consultation can start here.
  - **Y-24** — confirmed: the suite is ~3.5 min now on Windows (was 5–7).

  Done when you have looked at 1–2 and decided on the response test.

- [x] **V-11** (2026-11-29, from Yogesh) · *Answered 2026-11-22 — see Y-22.* · **`openapi.yaml`'s feedback
  contract had drifted — fixed — and this is the third drift in three tasks,
  so it is worth a test.** Branch `feat/t-036-feedback` (`18502cc`).

  1. **`Feedback` schema** described `diagnosis_verdict`, a top-level
     `correct_diagnosis`, `narrative`, `generator: model|fallback`, and had no
     `summary`, `coverage` or scorecards. `API_CONTRACT` §6 and
     `conclusion.py` agree with each other (`verdict`, `summary`,
     `tutor_feedback{lines,generator}`, `coverage`, both scorecards,
     `reasoning{id,label,flagged,status_line,reason}`, `answer`), and
     migration 012 allows `llm|rule_fallback`. I rewrote the schema to match.
  2. **Rating body** said `helpful`; `rate_feedback` reads `was_helpful` (and
     §6 says so). Fixed. `comment` was declared and not read — dropped.
  3. **`tests/test_openapi.py`**: `test_feedback_headings_are_the_neutral_ones`
     and `test_feedback_carries_the_learners_own_evidence` pinned the stale
     names (`heading`, `evidence`). Same purpose, now checking `label`/`id`
     and `reason`. Please look these over — they are yours.

  **The pattern:** T-034's `DiagnosisCreate.diagnosis` (V-10), and now these
  two. Every one passed CI and failed only when a client was built from the
  types, because nothing checks a body against its schema — the CT tests guard
  what must be *absent*, not that the declared shape is what is sent. A
  test that validates each implemented route's real response (and the request
  bodies its handler reads) against `openapi.yaml` would have caught all three
  on the day. Yours to decide whether to add.

  Done when you have looked at 1–3 and decided on the test.

- [x] **V-10** (2026-11-22, from Yogesh) · *Answered 2026-11-22 — see Y-22.* · **Three things from T-034 — one
  contract fix I made, one decision, one backend gap.** Branch
  `feat/t-034-consultation` (`b48b54e`).

  1. **`openapi.yaml` named the diagnosis field wrongly — fixed.**
     `DiagnosisCreate` said `required: [diagnosis]`; `API_CONTRACT` §6,
     `conclusion.py` (`body.get("text")`) and all 14 calls in
     `tests/db/test_v1_conclusion.py` use `text`. A client built from the
     generated types got `diagnosis_empty` every time. I changed the schema to
     `text`, regenerated `schema.ts` in the same commit, and
     `test_openapi.py` / `test_api_contract.py` still pass. Nothing compares
     request-body schemas against what the handlers read — the response side
     got CT tests, the request side did not — so this kind of drift is
     invisible until a client calls. Worth a test that posts the schema's
     example body to each endpoint?
  2. **`DiagnosisCreate.confidence_post` is declared and never read.**
     `PRD` FR-3 has a pre-case confidence; if a post-diagnosis one is wanted,
     `conclusion.py` should store it; if not, the field should go. I left it.
  3. **The anonymous trial cannot get past its first screen through `/v1`.**
     `POST /v1/trial/sessions` starts one, but every consultation endpoint —
     `GET /sessions/{id}`, questions, examinations, investigations,
     diagnosis — is `@require_auth`, so the trial cookie alone gets 401.
     `UX_SPEC` S-09/S-10 say "Auth: Both". T-034 is therefore signed-in only:
     an anonymous visitor at `/case/{id}` is sent to log in. The prototype's
     Flask routes still serve the trial; the web app cannot until these
     accept the `anonymous_id` cookie (through `anonymous_scope`, I assume).

  Done when (1) is looked at, (2) is decided, and (3) has an owner and a
  task — it is not in `BUILD_PLAN`.

- [x] **V-9** (2026-11-15, from Yogesh) · *Answered 2026-11-22 — see Y-22.* · **Please review two small additions
  to `/v1/me` made in T-033.** Yogesh agreed to them rather than wait. Branch
  `feat/t-033-dashboard-onboarding` (`d2eeb33`); `openapi.yaml` and
  `web/src/api/schema.ts` changed in the same commit, per the rule.

  1. **`PATCH /me` accepts `{"onboarded": true}`.** Nothing ever set
     `onboarded_at` — not `POST /me`, not `PATCH /me` (`_WRITABLE` lacked it),
     no trigger — so `UX_SPEC` §6.1.5's "onboarding incomplete → /welcome"
     sent every sign-in back to S-07 for ever. `ProfileRepository.update()`
     now pops the flag and adds `onboarded_at = COALESCE(onboarded_at, now())`:
     server-stamped like `consent_at`, kept on a second call, `false` refused
     with 422. Both answering and skipping S-07 send it (`PRD` FR-2.7).
  2. **`GET /me` returns `allowance_resets_at`** — `allowance.resets_at`,
     which `read_profile` already computed and threw away, for S-08's "Your
     next free case unlocks on {date}". Null for Pro, like
     `sessions_remaining_this_month`. Sent rather than recomputed in
     TypeScript because of `month_start`'s own warning about the timezone.

  6 tests in `tests/db/test_v1_reads.py`; 988 pass. **One loose end that is
  yours:** `API_CONTRACT` §4 still describes `GET /me` as returning an
  `allowance` object and `active_session_id`, neither of which the
  implementation or `openapi.yaml` ever had. The dashboard does not need
  `active_session_id` — the active session is in `GET /sessions` — so it may
  be simplest to correct §4 to match.

  Done when you have approved these or changed them.

- [x] **V-8** (2026-11-10, from Yogesh) · *Answered 2026-11-11 — the project answers again; see Y-17.* **The Supabase project does not
  resolve — please restore it. This blocks T-032's live test, the reviewers'
  `/admin` sign-in, and anything else that verifies a token.**

  Yogesh's laptop now has the anon key (sent privately — thank you). It is
  genuine: `role: anon`, issued 2026-10-28, project ref
  `xtrqmusmardmmzsptuwa`. But **`xtrqmusmardmmzsptuwa.supabase.co` is
  NXDOMAIN** — checked through the laptop's resolver, Google (8.8.8.8) and
  Cloudflare (1.1.1.1), all three "non-existent domain", which is the same
  answer an invented ref gets. `supabase.co` itself resolves, so it is not
  this network.

  Likeliest cause: **the project was paused** — the free plan pauses a project
  after about a week without activity, and it was created 28 Oct. Or it was
  deleted. Either way, only the dashboard can say.

  1. Open the Supabase dashboard and check project `Nidan`. If paused,
     **Restore**. If it is gone, a new project means new keys, a new ref, and
     the 32 migrations again (`SUPABASE_DEPLOYMENT.md`) — and the region must
     still be `eu-central-1` (`ADR-0017`).
  2. Tell me here when `https://xtrqmusmardmmzsptuwa.supabase.co/auth/v1/settings`
     answers (with the `apikey` header), or send the new ref/key if it changed.
  3. To stop it pausing again before launch: either a scheduled ping, or a
     paid plan once the reviewers start — worth deciding, because a paused
     project in the middle of a reviewer's session reads as "the app is
     broken".

  While it is down, the web app now says so: "We can't reach the sign-in
  service right now" rather than "That email or password doesn't match" —
  that bug turned up because of this.

  Done when the project answers and V-7's dashboard settings are in.

- [ ] **V-7** (2026-11-04, from Yogesh) · **Three things from T-032 — one
  file fixed on your side of the line, and the Supabase dashboard settings the
  web app needs.** Branch `feat/t-032-nextjs-scaffold` (`e42c287`).

  1. **`openapi.yaml` was invalid YAML, and I fixed it.** `DELETE /me` had two
     `description:` keys — T-030 slice 5 (`3c124ec`) added the "Still returns
     501" text above the original without removing it. PyYAML keeps the last
     duplicate silently, so `test_openapi.py` passed; the type generator's
     strict parser refused the file. I merged the two into one description,
     nothing lost, and `test_openapi.py` still passes. **Please check the
     wording is what you meant.** The new "Web app" CI job runs
     `npm run check:api`, which is now the only strict parse the contract gets —
     a duplicated key anywhere will fail it.
  2. **Changing `openapi.yaml` now means regenerating the web types.** Run
     `npm run gen:api` in `web/` and commit `web/src/api/schema.ts` with the
     contract change, or the "Web app" job goes red. That includes API-6.
  3. **Supabase dashboard, for the web app's sign-in (yours — no code needed):**
     - **Authentication → URL Configuration → Redirect URLs:** add
       `http://localhost:3000/auth/callback` (and the production URL later).
       Every email link and OAuth return lands there.
     - **Providers:** enable Google and Apple, or their buttons answer "We
       couldn't reach Google. Try again or use email."
     - **Confirm email:** tell me whether it is on. It decides whether S-03's
       "unverified email: login succeeds" can ever happen — with it on, Supabase
       refuses the login and the app routes to S-06 instead.
     - **Leaked-password protection**, if the plan includes it — the app's own
       common-password list is short on purpose.

  Done when the dashboard settings are in and you have looked at the
  `openapi.yaml` wording.

## Inbox — for Yogesh

- [ ] **Y-30** (2026-11-24, from Vraj) · **Stripe is DEFERRED. The end-of-November
  demo is the only target now, and that changes what is worth your time.**

  Vraj's decision, 24 Nov: **T-041 (Stripe) is not being built before the
  demo**, so **T-042 (pricing and account screens) is off your list too** — it
  depends on T-041 and there is nothing to price against. Nothing breaks by
  leaving it: `nidan/infra/billing.py` is a seam whose one adapter,
  `NoProvider`, honestly reports `no_provider_configured`, and
  `api/v1/contract.py` keeps answering 501 on the three billing operations.
  Do **not** start T-042. Do not build a pricing screen "just for the slide" —
  a screen that implies a payment flow we do not have is worse than its
  absence in front of an examiner.

  **What is yours, in priority order:**

  **1. T-044 · Master list and lexicon editors** — `UX_SPEC` **A-06**
  (clinical content) and **A-07** (topic lexicon). Not A-05/A-06; see Y-28 for
  why the plan's references were wrong. Depends only on T-020, which is
  merged, so it is unblocked now.

  This is the higher-value one and the reason is concrete: **the topic lexicon
  is full.** Cases 6 and 7 used the last of the 40 topics migration 017
  seeded, and 027/029/031 have since added thirteen more by hand. Every
  remaining case therefore needs **two migrations instead of one**, and the
  editor is what turns that into a screen. `/admin/content` exists as a shell;
  the master lists (examinations, investigations) and `topic_lexicon` /
  `topic_phrases` are the tables.

  **Watch the invariant:** a topic added through the editor must not leave the
  database disagreeing with `nidan/domain/assessment/topics.py`.
  `tests/db/test_seed.py` is what says so, and it now has two more assertions
  of the same kind (see Y-29) — read them before deciding how the editor
  writes. **C-4 also applies**: anchor keywords must never overlap
  contradictory clues, enforced in CI and in the case editor.

  **2. T-043 · AI usage and cost dashboard** — `UX_SPEC` **A-08** (AI
  operations). `/admin/ops` exists as a shell. `llm_calls` has the rows:
  tokens, `cost_usd` (NOT NULL), latency, `purpose`, per model. Depends on
  T-031 and T-020, both merged.

  Two things to know before you build it:

  * **`purpose` has five legal values and `playtest` is not one of them.**
    Migration 015's CHECK allows `patient`, `feedback`, `extraction`, `judge`,
    `grounding`. The admin Playtest route records nothing on purpose, so an
    author's own turns against a draft are absent from the cost figures —
    that is correct, not a gap, and the dashboard should not imply it is
    total spend.
  * **T-043 owes the leakage RATE**, which is §5.3's third defence. I built
    the queue (`/admin/leakage`) and made the dashboard's unreviewed *count*
    real — the `0.9% leakage rate` stat card that used to sit there was
    invented, and I replaced it with queue depth rather than leave a fabricated
    number on an admin screen. A real rate is flags per reply over a window,
    and it is A-08's. `leakage_flags` has the rows (0 right now — it only
    fills as consultations run).

  **3. Use `current_admin()`, not `current_actor()`, on any panel that joins
  `sessions` or `session_events`.** Repeated from Y-28 because it will cost
  you an hour on A-08 specifically. `own_sessions` has **no `TO` clause**, so
  it binds `nidan_admin` too, and `current_actor()` returns a plain
  `AuthenticatedUser` even for an administrator, by design. **The symptom is an
  empty screen, not an error.** Migration 034 adds two narrow policies keyed
  on a leakage flag existing; if an A-08 panel needs more than the flagged
  rows it needs its own policy in its own migration. **Do not widen mine to
  "admins may read sessions".**

  **4. If you touch `openapi.yaml` at all, that is three things in one
  commit** — the contract, the code, and `web/src/api/schema.ts` via
  `npm run gen:api` in `web/`. A description-only edit counts. Otherwise the
  "Web app" CI job fails on `npm run check:api`.

  **What I am doing meanwhile**, so we do not collide: a full dress rehearsal
  of the demo path on my laptop (signup → logout → login → consultation →
  feedback, then `/admin` → create case → review → publish), fixing whatever
  breaks, plus a written run sheet. Backend and `nidan/web/admin/` only. If I
  need to touch anything under `web/` I will put it in your inbox rather than
  edit it.

  **Done when:** you have picked T-044 or T-043, said which in Vraj's inbox so
  we are not both in `nidan/web/admin/`, and read `UX_SPEC` A-06/A-07/A-08
  rather than what `BUILD_PLAN` used to point at. Tick this and delete it.

- [ ] **Y-29** (2026-11-24, from Vraj) · **Run `alembic upgrade head` after
  you pull T-040 — there is a migration 035, and skipping it makes the web
  app's patient quietly worse rather than broken.** Branch
  `feat/t-040-leakage-monitor`, now at `9085295` (two commits; Y-28 pointed at
  the first one).

  **What it does.** The patient's shared brief in
  `nidan/domain/content/cases.py` (`_RULES`) gained a **rule 6**: never name
  a disease, or say what a test would be "for". The persona suite caught two
  of the ten personas answering "what tests should I order?" by naming their
  own diagnosis — "to see if it's reflux", "to check for a urinary infection".

  **Why it is a migration and why you have to run it.** `system_prompt` is
  seeded into `case_versions.content`, and **`/v1` reads the brief from the
  database** while the old `api/routes.py` prototype reads it from
  `cases.py`. So the Python edit on its own fixes only the anonymous trial.
  The web app goes through `/v1`, which means **without 035 your local
  consultations run the old five-rule brief** and the patient can still hand
  the learner the answer. Nothing errors; it just leaks.

  There is nothing for you to change in `web/` — no API shape moved, no
  `openapi.yaml` edit, so no `npm run gen:api`.

  **A pattern worth keeping, if you ever touch a persona or `_RULES`:** the
  edit needs a migration that rewrites the stored briefs and recomputes
  `content_hash`. 035 is the template. Two new tests in
  `tests/db/test_seed.py` fail if the code and the bank disagree — they did
  not exist before, which is why rule 6 shipped half-applied for an afternoon.

  **Done when:** `alembic current` says `035 (head)`, `pytest tests/db/test_seed.py`
  passes, and a consultation in the web app gets a patient that declines to
  say what a test is for. Tick this and delete it.

- [ ] **Y-28** (2026-11-24, from Vraj) · **T-038 is MERGED (PR #52) — Phase 3
  is complete on `main`. Phase 4 has started: T-040 is done and open as a PR.
  Three things are yours, and the first one will save you a day of building
  the wrong screen.** Branch `feat/t-040-leakage-monitor` (`14f67f7`).

  **1. `BUILD_PLAN`'s `UX_SPEC` references for BOTH of your Phase 4 tasks were
  off by one.** This is the important one.

  | Task | `BUILD_PLAN` said | It is actually |
  |---|---|---|
  | T-043 · AI usage and cost dashboard | A-07 | **A-08 · AI operations** |
  | T-044 · Master list and lexicon editors | A-05, A-06 | **A-06 · Clinical content** and **A-07 · Topic lexicon** |

  `UX_SPEC` §12 numbers them A-01 dashboard, A-02 case bank, A-03 case editor,
  A-04 Playtest, **A-05 review queue**, A-06 clinical content, A-07 topic
  lexicon, A-08 AI operations, A-09 users and support. A-05 is the review
  queue you already built in T-023. Both references are corrected in
  `BUILD_PLAN` on my branch with a note; **read A-06/A-07/A-08, not what the
  plan used to say.** Found while briefing Phase 4, not while building.

  **2. Start with T-043 or T-044, not T-042.** T-042 (pricing and account
  screens) depends on T-041 (Stripe), which is mine and not started. T-043
  depends on T-031 and T-020 and T-044 depends on T-020 — all merged, so both
  are unblocked right now. Your call which; T-044 unblocks case authoring
  (every remaining case currently needs two migrations because the topic
  lexicon is full), T-043 unblocks cost visibility.

  **3. T-040 left you two things inside your own tasks.**

  * **T-043 owes a leakage RATE.** I built `/admin/leakage` — the queue, under
    AI Ops — and made the dashboard's `unreviewed_leakage` count real. It was
    the literal `2` in `nidan/web/admin/routes.py`, and the dashboard's
    `0.9% leakage rate` stat card was invented too; I replaced that card with
    queue depth. **A real rate is flags per reply over a window, and it is
    A-08's**, i.e. yours. `leakage_flags` has the rows.
  * **Use `current_admin()`, not `current_actor()`, on any A-08 panel that
    joins `sessions` or `session_events`.** This cost me an hour. `own_sessions`
    in migration 016 has **no `TO` clause**, so it binds `nidan_admin` as well
    — and `current_actor()` returns a plain `AuthenticatedUser` even for an
    administrator, by design. The symptom is **an empty screen, not an
    error**: my leakage queue rendered "Nothing to review" with a flag sitting
    in the table. Migration 034 adds two narrow policies (`TO nidan_admin`,
    keyed on a leakage flag existing), but they only help a scope that
    actually assumed the role. If an A-08 panel needs more than the flagged
    rows, it needs its own policy in its own migration — **do not widen mine
    to "admins may read sessions".**

  **Also worth knowing, and not yours:** eight of the ten cases reveal at
  least one of their own `required_topics` in their `opening_line`, and
  `case_2` reveals four of eight (`python validate_personas.py --overlap`,
  pure, no model calls). Coverage is not inflated — it is scored over
  `question` events — but a learner who reads the opening line and sensibly
  does not re-ask is scored as having missed those topics. It has **no task
  and no owner**; fixing it moves the golden assessment record for all 16
  pilot sessions, so it needs a clinician. Raised in T-040's build log §9.

  **And the anonymous trial still cannot use `/v1`.** Still no task, still a
  launch feature (`PRD` FR-2). It is the only launch feature nobody holds.

  **Done when:** you have read `UX_SPEC` A-06/A-07/A-08 rather than the old
  references, and told me which of T-043/T-044 you are taking so I do not
  duplicate it.

- [ ] **Y-27** (2026-11-23, from Vraj) · **T-038 is merged-pending and Phase 3
  is complete. Your V-12 is answered: yes to the response conformance test,
  and it is mine. Two things change for you, one of them in copy you have not
  written yet.** Branch `feat/t-038-account-jobs-worker` (`52471ed`).

  **1 · V-12, both halves — looked at, and thank you.** `SessionPage` and
  `Progress` were both wrong in `openapi.yaml` and your fixes match
  `list_sessions`/`read_progress` and `API_CONTRACT` §7. Nothing to change.

  The `SessionPage` one is the worst drift we have had, and worth naming for
  the record: your T-033 dashboard was built from the schema, so against the
  real API it would have shown no sessions, no resume banner and no streak —
  **and its tests passed, because they used the same wrong shape.** That is
  the failure mode a schema is supposed to prevent, working in reverse.

  **2 · The response conformance test: yes, build it, and I am taking it.**
  Your reasoning is right and the asymmetry is the point — a missing *request*
  field gets a 422, a renamed *response* field just reads as `undefined`, so
  the client is silently wrong rather than refused. Five drifts, three of them
  responses, nothing watching that side.

  I will write the twin of `test_request_body_conformance.py`: run each
  implemented route's happy path in the DB tests and validate the JSON against
  the operation's 2xx schema, `jsonschema` against the resolved component.
  **Do not start it** — I do not want two of them. If it is not pushed within
  a few days, chase me.

  One thing I want it to do that the request version does not: fail on a
  response field the schema does **not** declare, not only on a declared one
  that is missing. `case_versions.content` is JSONB, so a new key can arrive
  from a case-editor save with no migration — which is the CT-1 shape, and
  `case_view.py` is the only thing standing in front of it.

  **3 · `DELETE /me` and `POST /me/export` now actually complete.**
  `python -m nidan.jobs run` performs the outbound work: the export is built
  and emailed, and an erasure's confirmation email, payment-provider
  cancellation and Supabase credential deletion all happen. The API responses
  did **not** change — still 202, same bodies — so **no `gen:api`, no
  `schema.ts` change, nothing for you to regenerate.** `openapi.yaml` is
  untouched in this branch.

  **4 · S-20's copy, for whenever you build T-042.** Y-25 was right that S-20
  belongs to the pricing-and-account-screens task, not T-037. When you get to
  it, the spec has changed under you in a good way: the two lines
  `UX_SPEC` S-20 §8.7 used to describe as *"promises the product cannot
  keep"* are now kept — the confirmation email and "removed within 24 h" for
  the credential. Read that section before writing the screen; I rewrote the
  paragraph.

  The honest caveat, which the spec now states: both depend on configuration I
  hold, not on your screen. Nothing reaches an inbox until `EMAIL_ADAPTER`
  names a real provider (the only adapter built writes each message to a file
  under `logs/`), and the credential is deleted only when the Supabase
  service-role key is set. **Neither failure is silent** — both record a
  failure row and make the worker's exit code non-zero. So the screen can say
  what S-20 says.

  **5 · Do not ever put the Supabase `service_role` key in `web/`.** New
  section `SECURITY_SPEC` §7.9 says why at length; the short version is that
  it bypasses row-level security completely, so every guarantee in `ADR-0016`
  is void for any process holding it. It belongs to the jobs worker's
  environment and nowhere else — **never as a `NEXT_PUBLIC_*` variable of any
  name**, because those are compiled into the browser bundle, and never in
  this file. `web/.env.example` already said so in a comment; it is a spec
  section now because T-038 is the first thing that legitimately needs the
  key.

  **6 · Two commits had gone missing, in case you hit the same thing.** PR #50
  was merged before I pushed `a80991c` (`scripts/demo_up.sh`) and `609cdca` to
  that branch, so neither reached `main` and I only noticed when a
  `COMMANDS.md` edit would not apply. Both are cherry-picked onto this branch.
  Pushing to a branch after its PR is merged puts the commits nowhere.

  **7 · `scripts/demo_up.sh` is new and will probably help you.** One command:
  Postgres, migrations, publishing the draft cases, warming the LLM, the API,
  then `npm run dev`. Ctrl+C stops both. `--api-only` skips Next.js. It also
  stops the compose `app` container if it is running — that container holds
  port 8000 and **serves a stale baked image with no source mount**, so a
  local run against it works quietly on old code. Worth knowing even if you
  do not use the script.

  Done when you have read §4's `UX_SPEC` change (before T-042, not now) and
  confirmed you are not also building the response test.


- [ ] **Y-26** (2026-11-23, from Vraj) · **If `POST /v1/sessions` has ever
  given you a 503 `no_cases_available`, this is why, and there is now a script
  for it.** Every case in the bank is a `draft`;
  `SelectionRepository.candidates()` returns only **published** versions, so
  the web app has nothing to serve. The test suite never sees it because its
  fixtures publish a case themselves — which is exactly why it only shows up
  when you run the app.

  ```bash
  python scripts/publish_for_demo.py --all --dry-run
  python scripts/publish_for_demo.py --all          # then this
  python scripts/publish_for_demo.py --all --undo   # reverses it
  ```

  It goes **through** migration 007's publish gate — inserts an approving
  `clinical_reviews` row with the full rubric, then flips the status, so the
  trigger still has to agree. Nothing disables a trigger. The review is
  attributed to `Demo Fixture (not a clinician)` and says in its own comment
  that it does not count towards the launch gate, because
  `clinical_reviews` is the evidence for "ten clinician-reviewed cases" and a
  fabricated row in there must be recognisable as one.

  **It refuses any non-local `DATABASE_URL`** — localhost, 127.0.0.1, ::1, `db`
  or a socket. Do not reach for `--i-know-this-is-not-local`; it exists so the
  refusal can be tested.

  Verified on my machine afterwards: 10 candidates, `choose_case` returns a
  case, and `case_for_session` gives real values (patient name, age, intro) —
  not the dict-of-Nones that T-030 slice 4 shipped.

  **Done when** you can start a consultation in the web app locally. Nothing
  for you to change in code.

- [ ] **Y-25** (2026-11-22, from Vraj) · **`DELETE /v1/me` is live, it answers
  202 and not 204, and S-20's copy has changed.** API-9 is settled —
  `ADR-0018`, the eighteenth record. Pull `main` and regenerate nothing: I ran
  `npm run gen:api` and committed `web/src/api/schema.ts`, so `check:api` is
  green on the merged result.

  **What changed for the frontend**

  ```jsonc
  // DELETE /v1/me  ·  body is REQUIRED
  { "confirmation": "DELETE" }        // exactly this; "delete" is a 422

  // 202 Accepted
  { "status": "erased",
    "retained": ["anonymised results", "research pseudonym"],
    "completes_within_hours": 24 }
  ```

  - **202, not 204.** The database erasure finishes before the response; three
    outbound calls (Supabase credential, payment provider, confirmation email)
    do not. Sign out, show the toast, do not wait for anything.
  - Two new schemas: `AccountDeletion`, `ErasureAccepted`.
  - One new error code: **`account_deleted` (409)**, returned by `POST /me` if
    someone signs up again after erasing. Worth a message rather than a
    generic failure — they will be confused, and it is final.
  - `404` is now a documented response on `DELETE /me` (no profile, or already
    erased).
  - **`retained` is server-sent on purpose.** `UX_SPEC` S-20 calls saying what
    survives "the ethical core of this screen", so render the list from the
    response rather than hard-coding it, and the screen cannot drift from
    §10.2.

  **S-20's copy changed, so the screen needs an edit.** One line became two:

  ```
  ✕  Everything you and the patient typed is redacted,
     and so is the feedback written about it
  ```

  It used to say "The questions you typed are permanently redacted". The
  erasure turned out to cover more than §10.2 described — four event types,
  not two, plus `feedback_texts`, because feedback cites the learner's own
  questions by design (`PRD` P3). Wider, not narrower, so the promise is
  stronger than before.

  **Two things on that screen the product still cannot do**, both mine: the
  confirmation email, and deleting the Supabase credential inside 24 h. Until
  that worker ships, an erased account can still present a valid token — every
  `/v1` route answers the ordinary 404, so nothing leaks, but the sign-in page
  will not tell them the account is gone. I have added **T-038 · Account jobs
  worker** (Phase 3, 2 d, mine) which does it along with API-10's export, so
  **Phase 3 is now 9 tasks, not 8.** It does not block T-037 or anything of
  yours.

  **Done when** S-20 reads the new copy, handles 202 rather than 204, renders
  `retained` from the response, and `POST /me` has a message for
  `account_deleted`.

- [ ] **Y-1** (2026-10-28, setup) · Repoint the remote — the repo was renamed.
  Note the capital N; the old URL still works but every push prints a redirect
  warning: `git remote set-url origin https://github.com/VrajPatel2611/Nidan.git`

- [ ] **Y-2** (2026-10-28, from Vraj) · **T-023 backend is built and MERGED —
  V-1, V-2 and V-3 are all cleared, and nothing is blocking you.** PR #26 went
  into `main` as `6680642`. **`git pull` and it is there.** Verified on the
  merged result: 654 tests pass (235 against real Postgres), ruff, mypy,
  import-linter and the detector check all green. Then:

  ```python
  from nidan.api.auth import current_reviewer, current_admin, require_reviewer
  from nidan.infra.db.repositories import repo_scope

  with repo_scope(current_reviewer()) as db:          # @require_reviewer routes
      db.reviews.assigned_to_me()                     # "Assigned to me" tab
      db.reviews.pending()                            # "All pending" tab
      db.reviews.completed()                          # "Completed" tab
      db.reviews.for_version(version_id)              # reviews of one version
      db.reviews.is_author(version_id, reviewer_id)   # the reviewer≠author warning
      db.reviews.record(version_id, decision="approved",
                        scores={"clinical_plausibility": 5,
                                "internal_consistency": 4,
                                "trap_validity": 5, "solvability": 4},
                        comments="...")               # returns the review id

  with repo_scope(current_admin()) as db:             # @require_admin routes
      db.reviews.assign(version_id, reviewer_id)      # assigning is admin-only
      db.reviews.unassign(version_id, reviewer_id)
      db.reviews.has_approval(version_id)             # grey out Publish with this
      db.cases.publish(version_id)                    # may raise, see below
  ```

  Four things to know:

  1. **`current_reviewer()`, not `current_actor()`, on every `@require_reviewer`
     route.** That is what V-1 was: `current_actor()` runs as `nidan_app`, which
     cannot see a draft or insert a review. An admin on the review queue also
     gets `current_reviewer()` — reviewing is reviewing. Use `current_admin()`
     only for assigning and publishing.
  2. **Catch `RubricViolation`** from
     `nidan.infra.db.repositories.reviews`. It is raised for an approval with
     any dimension below 4, a `changes_requested`/`rejected` with no comment, a
     missing dimension, or a score outside 1–5. The message names what is wrong
     and is safe to show. You still disable the Approve button in the form —
     this is the backstop, not the user experience.
  3. **Catch `PublicationBlocked`** and **`AlreadyPublished`** from
     `nidan.infra.db.repositories.cases` around `publish()` — they are your 409.
     The first means no approving review; the second means another version of
     that case is already published. `publish()` is idempotent, so a double
     click is harmless.
  4. `record()` takes the reviewer from the scope. There is no `reviewer_id`
     argument, on purpose.

  Done when `nidan/web/admin/reviews/` can list the three tabs, assign, record a
  review and publish.

  **One migration to apply before the app will run:** `alembic upgrade head`
  takes your local database from 023 to 024. Without it every review route
  fails on a missing `review_assignments` table and a missing `nidan_reviewer`
  role, which will not look like a migration problem.

- [ ] **Y-3** (2026-10-28, from Vraj) · **Stop using the Downloads copies of the
  briefs.** Merged — PR #25, `docs/process/phase-2-briefs/`. `git pull` and read
  them there from now on.

  Only two files are left: `00_START_HERE.md` and `03_T-023_clinical_review.md`.
  The T-020, T-021 and T-022 briefs are **deleted** now those tasks are merged —
  a finished brief is one more document that can be picked up by mistake, which
  is exactly what went wrong on T-020. What was built is in the build logs.

- [ ] **Y-4** (2026-10-28, from Vraj) · **Signing in to `/admin` locally — now
  documented and verified.** Read `docs/process/LOCAL_ADMIN_ACCESS.md` on
  `main`, not the Notes section below, which is superseded. I took a real
  Supabase token through to a 200 on `/admin` today, and the doc is what
  actually worked rather than what should have.

  The Supabase project exists: **`Nidan`, `eu-central-1` (Frankfurt)**, decided
  in `ADR-0017`. `SUPABASE_URL` is public and is in the doc; the **anon key** is
  **sent privately**, and you only need it for the one `curl` that mints a
  token. The `service_role` key is never used — do not put it in `.env`.

  **Three things will bite you, and all three look like a permissions problem**,
  because `UX_SPEC` §12.1 makes every admin refusal an identical 404:

  1. **Your local database is at 021.** `platform_role` arrived in 022, and that
     is the column `require_role` reads, so `/admin` cannot work at any token
     until you run `alembic upgrade head`. Note the host port is **5433**, not
     5432 — compose remaps it.
  2. **Rebuild the image, do not restart it.** `docker compose up -d --build
     app`. A stale image serves older code: mine predated T-014 and had no
     `nidan.infra.auth` at all.
  3. **Tick "Auto Confirm User"** when you create your account in the Supabase
     dashboard, or the token request fails with `email_not_confirmed`.

  Give yourself `platform_role = 'reviewer'` once as well as `'admin'`. That is
  the role the review queue is actually for, and `current_reviewer()` is what
  those routes must open their scope with — see Y-2.

- [ ] **Y-5** (2026-10-28, from Vraj) · **Pull `main` before you start T-023:
  the admin console was broken in Docker and you would have hit it.**
  `pyproject.toml` declared `web/templates/*.html`, which does not recurse, so
  an installed build shipped 4 of 25 templates and 2 of 4 JavaScript files.
  Everything under `admin/` was missing — **your case editor and Playtest
  included**. It showed up as a 500 on `/admin` reading `TemplateNotFound:
  admin/dashboard.html`, which points at the template rather than at the
  pattern that failed to collect it.

  Nothing caught it because `pip install -e .` resolves templates from the
  source tree: the suite passed and local runs worked. Only a packaged build
  failed. Fixed with recursive globs, and `tests/test_packaging.py` now asserts
  every asset is collected. **If you add a new template subdirectory, that test
  is what will tell you.**

- [ ] **Y-6** (2026-10-29, from Vraj) · **Two cases to put through the review
  queue — they are the first real content the console has had.** Branch
  `feat/cases-6-7`, stacked on `feat/reviewer-onboarding`; merge the onboarding
  one first. Migration **026** seeds them as v1 drafts:

  | slug | title | what it tests |
  |---|---|---|
  | `headache-hypertension` | The Headache That Is Not Stress | the diagnosis is on the blood-pressure cuff — a learner can take a flawless history and miss it by not examining |
  | `wheezing-child-asthma` | The Wheezing Child | two voices: the chatbot plays the child or his mother, depending on who is addressed |

  **`wheezing-child-asthma` is the one to Playtest first.** It is the only case
  with two speakers, and nothing in T-022 was built with that in mind. If the
  patient panel assumes one name, or the transcript does not make clear who is
  answering, that is a real finding and worth raising before a clinician meets
  it. The prompt tells the model to default to the mother and answer as the boy
  when he is addressed directly.

  Done looks like: both open in Playtest, both reach the rubric form, and a
  review can be recorded against each.

- [ ] **Y-7** (2026-10-29, from Vraj) · **Where will the reviewers actually
  reach the console?** This is a decision, not a task, and it is now the only
  thing between the clinicians and their first review.

  The console runs on `localhost:8000` and there is **no deployment task
  anywhere in `BUILD_PLAN`** — all seven phases, T-045 is "launch readiness",
  not hosting. No `fly.toml`, no `render.yaml`, no Procfile. Two clinicians
  cannot review cases on a laptop in Ahmedabad.

  Nothing about a *case* needs deploying — cases are rows, and migrations 019
  and 026 already seed all seven as drafts. What needs a URL is the Flask app
  that already exists. Two steps, in order: `SUPABASE_DEPLOYMENT.md` for the 26
  migrations against the Supabase project, then the container somewhere with
  `DATABASE_URL` pointing at it. The app is stateless by construction
  (`ADR-0003`), so this is about half a day, not a project.

  **This is not T-032.** The learner-facing Next.js app is Phase 3 and
  unrelated; what the reviewers need is `/admin`, which is built.

  Vraj to decide the host. Flag it if it blocks you.

- [ ] **Y-8** (2026-10-29, from Vraj) · **All ten cases now exist.** Branch
  `feat/final-three-cases`, three commits, stacked on nothing — it branches
  from `main` at PR #32. Migrations 027-032: three new cases plus the lexicon
  and master-list rows they needed.

  | slug | title | the trap |
  |---|---|---|
  | `syncope-aortic-stenosis` | The Faint That Was Not a Faint | the patient offers it himself, and his two drugs support it |
  | `rectal-bleeding-colorectal-cancer` | The Bleeding That Was Already Explained | **the anchor is TRUE** — he really has haemorrhoids |
  | `back-pain-axial-spondyloarthritis` | The Back Pain That Was Better By Lunchtime | no single answer gives it away; it is a pattern |

  Nothing for you to build. Two things to know:

  1. **The review queue now has ten drafts in it, not seven.** Worth a look at
     `/admin/reviews` to check the list still reads well at that length — it
     was designed when there were five.
  2. **`rectal-bleeding-colorectal-cancer` is the one to Playtest.** Its rectal
     examination deliberately returns two findings in one block of text —
     haemorrhoids AND a mass. If the examination panel truncates, collapses or
     summarises that text, the case stops working entirely, and it is the only
     case where the formatting carries the teaching point.

- [ ] **Y-9** (2026-11-03, from Vraj) · **T-030 is DONE and merged. T-034 and
  T-036 are unblocked.** `main` at PR #41. 18 of the 23 operations in
  `openapi.yaml` are live; the other 5 answer **501 with the error envelope**,
  not a 404, so you can build against them today and they will light up.

  **Read `openapi.yaml`, not my description of it** — T-032 criterion 2
  generates your types from that file and CI fails if they are stale.

  **The `Session` schema changed, and it will change your generated types.**
  It had drifted from `API_CONTRACT` §6 and nothing compared the two, so both
  were "right". Reconciled to §6:

  | was | is now |
  |---|---|
  | `id` | `session_id` |
  | `patient` (flat, no title) | `case: { title, patient, opening_line }` |
  | `transcript[].{role,text,at}` | `transcript[].{seq,type,text,at}` |
  | `examinations_performed` | `examinations_done` |
  | `investigations_ordered` | `investigations_done` |
  | — | `sequence_index`, `last_activity_at`, `is_repeat` |

  **Four things the server already guarantees, so do not re-implement them:**

  1. **CT-1** — no response ever carries `correct_diagnosis`,
     `anchor_keywords`, `required_topics`, `contradictory_clues`,
     `system_prompt` or five more, during a consultation. One serialiser,
     `api/v1/case_view.py`. The `answer` block on `GET /feedback` is the
     deliberate exception, after the diagnosis is in.
  2. **CT-2** — no coverage, no topic hints, no `matched_topics` reaches a
     live consultation. The question response carries the reply and nothing
     about how the learner is doing.
  3. **CT-3** — the catalogue endpoints carry no `category` and no `is_key`.
     Same 27 examinations and 91 investigations on every case.
  4. **CT-5** — no response body contains "anchoring", "premature closure" or
     "confirmation bias". `reasoning[]` arrives with both an `id`
     (`diagnostic_focus` …) and a ready-to-render `label` ("Diagnostic
     focus"), so you do not need a mapping table.

  **Two API details worth knowing before you draw S-10 and S-12:**

  - **There is no question counter in any response**, deliberately — see
    Y-10. When the learner hits the 40-question cap they get
    `429 question_limit_reached` with `details.limit`. That refusal is
    currently the only signal, so "approaching zero" has nothing to read yet.
  - **`verdict` can be `"anchored"`** and that word must not reach the
    screen (`PRD` P1). It is a machine value, like `diagnostic_focus`; the
    label is yours to choose in `UX_SPEC`.

- [ ] **Y-10** (2026-11-03, from Vraj) · **Five open contract questions, and
  two of them shape T-036. Please look before you build the feedback screen.**
  All five are written up in `API_CONTRACT` §13 with the evidence; this is the
  index.

  | # | Question | Why it is yours |
  |---|---|---|
  | **API-6** | Does `questions_remaining` belong on a session response? | §6 says yes and argues it; `test_openapi.py` names the field in its forbidden set under `PRD` P2/CT-1/CT-2, so somebody decided the other way. **Implemented as absent.** `UX_SPEC` S-10 wants the cap surfaced as it nears zero, and right now there is nothing to surface |
  | **API-8** | `answer.trap_explanation` | §6's feedback example shows it. **No such field exists** — not in `case_versions.content`, not in `cases.py`, nowhere. Returning `answer.anchor_topic` instead, which is real. A written trap explanation is content authoring for all ten cases plus a schema change |
  | API-9 | `DELETE /me` cannot execute `DATA_MODEL` §10.2 | §10.2 UPDATEs `session_events`, which migration 010 makes append-only — verified that even the table owner is refused. GDPR decision, four options. 501 for now |
  | API-10 | `POST /me/export` returns 202 and nothing builds the export | 202 means "accepted"; the worker and the mail do not exist and have no task |
  | API-7 | §6 says `session_already_concluded`, §10 says `session_concluded` | Typo in §6. The catalogue governs; nothing to do but correct the prose |

  **API-6 and API-8 are the two that will shape your screens.** Deciding them
  after T-036 means rebuilding part of it.

---

- [ ] **Y-11** (2026-11-04, from Vraj) · **T-031 is DONE and merged-pending —
  branch `feat/t-031-gateway-accounting`, two commits, PR not yet opened.**
  This unblocks **T-043** (AI usage and cost dashboard, yours, Phase 4): it now
  has real data. Every model call writes an `llm_calls` row with
  `purpose`, `provider`, `model`, `prompt_tokens`, `output_tokens`,
  `cost_usd NUMERIC(10,6)`, `latency_ms`, `status`, `attempt`, `created_at` and
  a nullable `session_id`.

  Three things to know before you build that screen:

  1. **`purpose` has five values** — `patient`, `feedback`, `extraction`,
     `judge`, `grounding` (migration 015's CHECK). `playtest` is **not** one,
     and Playtest turns are deliberately **not** recorded: migration 024
     withheld `llm_calls` from `nidan_reviewer` on purpose. So "cost per
     session" is honest, and total spend excludes your own playtesting.
  2. **Anonymous trial calls ARE recorded**, against their trial session. Any
     per-user breakdown must cope with `sessions.user_id IS NULL`.
  3. **`cost_usd` is 0 for a model missing from `nidan/infra/llm/pricing.py`**,
     and the gateway logs `llm.model_not_priced`. Treat a zero cost beside a
     non-zero token count as "unpriced", not "free" — a dashboard that sums it
     silently under-reports.

  `/readyz` also now returns `checks.llm_circuits_open`, a list of
  `provider:model` keys whose circuit breaker is open. Useful for A-07's health
  strip. It is reported, not gating — readiness stays `ready`.

  **Done when:** nothing for you to do yet; this is context so T-043 is not
  designed against guesses. Read `docs/build-log/T-031-llm-gateway-hardening.md`
  when you pick it up.

- [x] **Y-12** (2026-11-04, from Vraj) · ~~**Playtest's patient is currently
  broken on every machine, and it is not your code.**~~ **RESOLVED same day —
  see Y-13 for what you must do, and Done for why. The "do not change
  `GROQ_MODEL`" instruction below is now OBSOLETE: you DO need to change it.** The configured default
  model `llama-3.3-70b-versatile` returns **404 model_not_found** from the live
  Groq API. The key can reach eleven models and **none of them is a Llama chat
  model** — `openai/gpt-oss-120b`, `openai/gpt-oss-20b` and `qwen/qwen3.8-27b`
  are the usable chat ones; the rest are speech, TTS or classifiers.

  Symptom you would otherwise spend an hour on: Playtest's **Ask** returns
  503 and the panel shows "The patient could not respond", while everything
  else in `/admin` works perfectly. `python test_api.py` says the same thing in
  one line — run that first.

  The test suite does not catch it and should not: T-002 criterion 1 is that no
  test makes a network call, so nothing ever asks a real provider whether the
  model exists.

  **This also blocks the clinician reviewers** — they judge a case by playing
  it, and playing it needs a patient.

  Vraj is checking the Groq console (model access / Meta licence acceptance /
  plan tier) before anything is changed in code. The replacement model is
  `TECH_SPEC` §5.2's decision — "leakage rate first, then cost, then latency" —
  not a default to guess at.

  **Done when:** Vraj reports back. **Do not change `GROQ_MODEL` on your side
  to work around it** — two laptops silently running different patient models
  would make every leakage observation incomparable. Override is
  `GROQ_MODEL` / `GROQ_MODEL_PATIENT` in `.env` when the time comes.

- [ ] **Y-13** (2026-11-04, from Vraj) · **Change `GROQ_MODEL` in your `.env`,
  or Playtest's patient will keep returning 503.** This supersedes Y-12.

  **Groq retired `llama-3.3-70b-versatile` on 2026-08-16** (Free and Developer
  tiers). It was not an access setting and there is nothing to re-enable — the
  whole Llama chat line is gone from the account. The replacement is
  `openai/gpt-oss-120b`, Groq's own named one, and it is **cheaper on both
  meters**: $0.15/$0.60 per million against $0.59/$0.79. One patient turn costs
  about $0.000035.

  ```bash
  git pull                      # main, once the T-031 PR is merged
  # then in your .env, change this one line:
  #   GROQ_MODEL=openai/gpt-oss-120b
  python test_api.py            # must print "OK: the patient replied"
  ```

  `.env.example` carries the new value and the reason; your own `.env`
  overrides it, so pulling is not enough.

  **Three things that matter for your screens:**

  1. **It is a reasoning model.** `max_tokens` covers the model's deliberation
     *and* its reply, so `GroqProvider` sends `reasoning_effort="low"`. Without
     it a 60-token budget went entirely to deliberation and returned a sentence
     cut off mid-word. If you ever add a call site, do not set `max_tokens`
     tight.
  2. **Never read `message.reasoning`.** On these models it discusses the
     system prompt, and for the patient that is the whole case including the
     correct diagnosis. Falling back to it when `content` is empty would put
     the answer in the patient's mouth, and it would not pass through
     `case_view.py`, so CT-1 would not catch it. There is a named test; leave
     it alone.
  3. **The ten personas were tuned against the retired model.** The detectors
     are unaffected (PR-1 — they are deterministic Python over stored
     questions, and the 94.4% validation and golden record did not move), but
     the patient's *voice and leakage discipline* will differ. **Worth a pass
     through Playtest on a couple of cases before a reviewer sees one** — and
     tell Vraj if a patient volunteers too much.

  **Done when:** `python test_api.py` prints OK on your machine and Playtest's
  Ask returns a reply.

- [ ] **Y-14** (2026-11-04, from Vraj) · **You are first now — start T-032.**

  Deliberate sequencing decision, not a default. Phase 3 has ~20 days left and
  **19 of them are yours**; Vraj has 1 (T-035, which nothing waits on). Nothing
  he builds moves the semester-end demo, so he is standing aside until your
  track is moving.

  **Your run, in order:** T-032 (4 d) → T-033 (3 d) → T-034 (6 d) → T-036
  (3 d) → T-037 (3 d).

  **T-032 is unblocked today** — it depends only on T-011, which is done.
  Nothing from Vraj is needed to begin.

  Two things that land before you need them:

  - **Before you touch Playtest or any patient reply: pull `main` and make
    sure the T-031 merge is in it.** Y-13's `.env` change is necessary but not
    sufficient — the `reasoning_effort` fix that makes the new model return a
    usable reply is in that branch. Without it the patient comes back empty or
    truncated and it will look like your problem.
  - **API-6 is being settled this week.** It decides whether
    `questions_remaining` appears on the session response, which is the
    consultation screen's question-counter. You do not hit it until T-034, ~7
    working days in. **Do not design the T-034 header around either answer
    until Vraj has confirmed it** — see Y-10.

  **Done when:** T-032's four criteria are met and it is merged.

- [ ] **Y-15** (2026-11-11, from Vraj) · **V-7 answered: the `openapi.yaml`
  wording is right, and the hole that let it through is closed on our side.**

  1. **Your merge of the two `description:` keys is approved as it stands.**
     Faithful, nothing lost, and putting the original text under "Once it
     runs:" makes it read correctly in context. No change wanted.

  2. **You should not have been the one to find it, and now you won't be.**
     `tests/test_openapi.py` used `yaml.safe_load`, which keeps the last of a
     duplicated key silently — so all nine of its assertions passed over a
     file your type generator refused. A backend mistake failed in your CI.
     The fixture now parses with a strict loader and two tests guard it,
     including one that proves the guard bites. Branch
     `fix/openapi-strict-parse`. **`npm run check:api` is no longer the only
     strict parse** — but keep it, it catches things PyYAML would not.
     I also scanned the whole contract for other duplicates: none.

  3. **The `gen:api` rule is now in `CLAUDE.md`**, so the next contract change
     from this side arrives with `web/src/api/schema.ts` regenerated in the
     same commit rather than reaching you as a red build.

  4. **API-6 is still open and I know it is blocking your T-034 header.**
     Answer coming before you need it; when it lands it will arrive with the
     regenerated types, per (3).

  **Done when:** nothing for you — this is an answer, not a request.

- [ ] **Y-16** (2026-11-11, from Vraj) · **V-8: your Supabase diagnosis is
  confirmed independently, including the part you could not check.**

  I re-resolved `xtrqmusmardmmzsptuwa.supabase.co` from this laptop, Google
  and Cloudflare — **NXDOMAIN on all three**, while `supabase.co` and
  `api.supabase.com` resolve normally. So it is not your network, not the key,
  and not a typo in the ref.

  **And NXDOMAIN does not distinguish paused from deleted** — Supabase's own
  KB says a *paused* project stops serving its hostname and returns NXDOMAIN
  too (https://supabase.com/kb/troubleshooting/nxdomain-error-connecting-to-a-
  supabase-project). So your "only the dashboard can say" was exactly right;
  do not read the NXDOMAIN as evidence the project is gone.

  The backend's `.env` points at the same ref, so **if it is a Restore,
  nothing changes for either of us** — same ref, same keys, no resend. Expect
  DNS to take a minute or two to come back after restoring.

  If it turns out to be deleted, you will get a new ref and key from me
  privately, and the 32 migrations get re-run (`SUPABASE_DEPLOYMENT.md`,
  region stays `eu-central-1` per ADR-0017).

  **Your "We can't reach the sign-in service right now" fix is the right
  call** and worth keeping permanently — a paused project mid-session would
  otherwise read to a clinician as "wrong password".

  **Done when:** I report back that the project answers. Until then, treat
  T-032's live sign-in test as blocked rather than broken.

- [ ] **Y-17** (2026-11-11, from Vraj) · **Supabase answers again — unblock
  your sign-in testing. Two things to watch when you do.**

  **1. The project is live.** `xtrqmusmardmmzsptuwa.supabase.co` now resolves
  on this laptop, `8.8.8.8` and `1.1.1.1` (`104.18.38.10`, `172.64.149.246`),
  and `/auth/v1/health` answers over HTTPS with
  `sb-project-ref: xtrqmusmardmmzsptuwa` — the gateway recognises the ref and
  routes it, which a paused project does not do. Same ref, same anon key,
  **nothing in your `.env.local` changes.** Pull and try S-01 → S-22 again.

  **2. Your redirect URL probably needs a globstar, not the exact path.**
  `callbackUrl()` appends query params — `?next=…&tz=…`, and `?type=signup`
  or `?type=recovery` on the email flows. Supabase's redirect docs document
  wildcards (`*` stops at `/`, `**` crosses it) but **say nothing about how
  query strings are compared**, and in their glob syntax a bare `?` is itself
  a single-character wildcard. So a literal `http://localhost:3000/auth/callback`
  entry may not match the URL your app actually sends.
  https://supabase.com/docs/guides/auth/redirect-urls

  I am adding **both** `http://localhost:3000/auth/callback` and
  `http://localhost:3000/**` (the docs recommend the globstar for local
  development). If a flow still bounces with `redirect_to` mismatch, compare
  the URL in the browser address bar against the list rather than assuming the
  provider is misconfigured — that is the only way to settle it.

  **3. OAuth needs more than the Supabase toggle.** Google and Apple each
  need their own client ID/secret in the Supabase provider panel, and their
  consent screen needs
  `https://xtrqmusmardmmzsptuwa.supabase.co/auth/v1/callback`
  as an authorised redirect URI. I am enabling the toggles; if either provider
  errors with `invalid_client` it is the upstream console, not your code.

  **4. Email confirmation: I will tell you which way it is set** when I am in
  the dashboard. It decides whether your S-03 "check your inbox" state can
  happen at all, so do not harden that path until you hear.

  **Done when:** you have taken a real account through S-01 → S-22 against
  the live project and said so here.

- [x] **Y-18** (2026-11-11, from Vraj) · *Settled the same day — see Y-19.* **API-6 is leaning one way. Do not
  build on it yet, but know the direction.**

  Recommendation going to Vraj: **`questions_remaining` stays absent.** The
  reason it can resolve that way without losing `UX_SPEC` S-10 is that
  **you can already derive it** — `Session.transcript` is an array of
  `TranscriptEntry` with a `type`, so counting `type == "question"` gives the
  figure from data the response already carries, across reloads and resumes.
  Nothing new on the wire, and the 40 lives in one place as it does now.

  If that is how it lands, S-10 shows **nothing** until the cap is close and
  then a warning — not a running "n of 40", which is the counter `PRD` P2
  forbids. **Wait for the settled answer before you wire the warning**, and
  when it comes it is a docs-and-comments change, so **no `schema.ts`
  regeneration and no red CI for you.**

  **Done when:** Vraj posts the settled answer here.

- [ ] **Y-19** (2026-11-11, from Vraj) · **API-6 is SETTLED. Build S-10's cap
  behaviour — and it is simpler than Y-18 suggested.**

  **`questions_remaining` is absent, permanently.** Branch
  `decide/api-6-questions-remaining`, commit `b42ba44`.

  **What decided it, because it is worth knowing before you ever want the
  field back.** `API_CONTRACT` §6 argued for it and justified that with "the
  UI surfaces it only when it approaches zero (`UX_SPEC` S-10)". **S-10 says
  the reverse** — its table *"What is deliberately absent, listed so no one
  adds them"* opens with the row *Question counter | U2*. §6 was misreading
  the one document it cited, so there was never really a disagreement: S-10,
  `PRD` P2 and `tests/test_openapi.py` all already said no. §6 is corrected.

  **So build it this way, and it needs nothing new from the API:**

  - **At the cap:** the 40th question's successor returns **429
    `question_limit_reached`** with `details: {"limit": 40}`. That drives
    S-10's disabled input and its note — "You've asked 40 questions, that's
    plenty. Examine, investigate, or give your diagnosis when ready."
  - **No counter, at any point.** Not "6 left", not "34 of 40", not a
    progress ring that fills. S-10's absent-list is the authority and U2 is
    the reason.
  - **Optional polish only:** if you would rather disable the box after the
    40th answer than let someone type a 41st into a live field and get a
    refusal, count `transcript` entries whose `type` is `"question"`. It is
    already in the session response, so it survives reload and resume. This
    is a nicety, not a requirement — **the 429 is authoritative** and the
    server-side cap is the only enforcement.

  **Nothing breaks for you.** The `Session` schema never carried the field, so
  there is no type change. `schema.ts` is regenerated in the same commit
  because the generator copies descriptions into comments — **2 comment lines,
  no types.** `npm run typecheck`, `lint` and `check:api` all pass on it. You
  do not need to regenerate anything.

  **Done when:** S-10 handles the 429 and shows no counter.

- [ ] **Y-20** (2026-11-11, from Vraj) · **One loose end from T-032, yours to
  decide.** `python scripts/build_docx.py` generates a
  `docs/build-log/Nidan_T-032_Build_Log.docx` that is **untracked** — nobody
  has run the generator since T-032 merged. I left it out of the API-6 commit
  because it is not mine to add. Either commit it with your next push or say
  you would rather the build logs not carry .docx copies; every other
  finished task has one, so right now T-032 is the odd one out.

  Note for whenever you do run it: it rewrites **all 46** .docx files, because
  a .docx is a zip and the timestamps churn. Commit only the ones whose
  Markdown you actually changed, or the diff is 45 binary files of noise.

  **Done when:** you have committed it or said no.

- [ ] **Y-21** (2026-11-22, from Vraj) · **Start T-037 now. It does not depend
  on T-035 — you are not waiting for me.**

  I had assumed the same thing you did, so I checked `BUILD_PLAN` §7:
  **T-037 depends on T-036**, which is merged. T-035 is `Depends T-034`, and
  nothing in Phase 3 depends on T-035. So the two remaining tasks are
  independent and **Phase 3 closes when the slower of them finishes**, not
  after both in sequence. T-037 is 3 d and T-035 is 1 d, so you are the
  critical path — please start rather than wait.

  **What I am doing meanwhile**, so you are not surprised by commits in your
  area: T-035, the real-patient-data guard. It is backend only, and **you have
  already built its entire frontend half in T-034** — the modal, the
  `patient_data_detected` → `{state: "blocked"}` mapping in `consultation.ts`,
  and the test that mocks the 422. Nothing on the server has ever returned
  that code; T-035 makes it fire. **Your client is the fixed contract here**,
  so if anything I do would change the shape you handle, you will hear it from
  me before it merges rather than from CI.

  One thing it adds that touches you: the **schema-conformance test you asked
  for twice** (V-10.1, V-11's "the pattern"). You were right that three drifts
  in three tasks is a pattern and that nothing checks the declared shape
  against what is actually sent. I am folding it into T-035. It should mean
  the fourth drift fails on my laptop instead of in your CI.

  Your three contract fixes and the two `/v1/me` additions — I am reviewing
  them properly and will answer V-9, V-10 and V-11 in one go, not as a
  one-line "approved".

  **Done when:** T-037 is open and moving.

- [ ] **Y-22** (2026-11-22, from Vraj) · **V-9, V-10 and V-11 all answered.
  Your three contract fixes are approved, you were right about the test, and
  it found four more drifts on its first run.**

  **T-035 is done** — branch `feat/t-035-patient-data-guard`. Phase 3 is now
  **6 of 8**, and T-037 is the only thing left in it.

  ### Your fixes: all three approved, unchanged

  1. **`DiagnosisCreate` `diagnosis` → `text`** (V-10.1) — correct. §6,
     `conclusion.py` and all 14 calls in `test_v1_conclusion.py` agree with
     you.
  2. **Rating `helpful` → `was_helpful`, `comment` dropped** (V-11.2) —
     correct.
  3. **The `Feedback` schema rewrite** (V-11.1) — correct, and I checked it
     against `conclusion.py` field by field. Your two reworked tests
     (`label`/`id` and `reason`) are right; thank you for not just renaming
     the assertions to pass.

  ### You were right about the test, and it earned its keep immediately

  Folded into T-035: `tests/test_request_body_conformance.py`. It walks the
  AST of `api/v1/` for the keys each handler takes off the JSON body and
  compares them with the schema the contract attaches to that operation, both
  directions. Static — no database, no app, 0.2 s — so **it still runs when
  Docker is down**, which is exactly when a contract change gets made in a
  hurry.

  Your diagnosis of the cause was exactly right and worth repeating: the CT
  tests guard what must be **absent** from a response, and nothing checked
  that the shape we *declare* is the shape we *read*.

  **Three real drifts on the first run, and one of them is a bug you should
  know about:**

  - **`PATCH /me` reads `consent_version` and the contract never declared
    it.** The handler *requires* it when `consent_research` is true, so a
    client generated from `openapi.yaml` had no way to send it and **could
    never give research consent at all**. Declared now. If you built a consent
    toggle in T-033 and it seemed not to work, this is why.
  - **`POST /me` accepts seven fields the contract never mentioned** —
    `identity.py` validates POST and PATCH against one `_WRITABLE` set, so you
    could have set a display name at sign-up without a second PATCH. Declared
    now.
  - **`confidence_post` declared on the diagnosis body, never read** — V-10.2,
    which you raised and left. **Removed.** Storing it needs a column or an
    event field, a migration, and a decision about the research export; a
    field you can send that the server silently discards is worse than no
    field, because it looks like it works. Confidence *calibration* (pre
    vs post) is a real teaching signal and `PRD` FR-3 already has the "pre"
    half — if we want it, it deserves a task, not a silent key.

  **And one false positive, which was mine, fixed before committing** — the
  walk did not understand `identity.py`'s `{k: v for k, v in body.items() if
  k in _WRITABLE}` idiom and reported six invented problems on `PATCH /me`. It
  resolves module-level string sets now. It had also silently skipped the
  busiest endpoint in the API, because Flask spells the parameter
  `<uuid:session_id>` and the contract spells it `{id}` — there is now a guard
  test that fails if the walk stops matching routes, since otherwise every
  assertion passes over an empty set.

  **`schema.ts` is regenerated in the same commit**: 16 insertions, 1
  deletion. Every insertion is an **optional** field and the one deletion is
  `confidence_post`, which your client never sent — so **T-034 and T-036 are
  unaffected** and `typecheck`, `lint` and `check:api` are clean. No action
  for you.

  ### V-9: both `/v1/me` additions approved, and your loose end is fixed

  `PATCH /me {"onboarded": true}` and `GET /me`'s `allowance_resets_at` are
  both right, and the server-stamped `onboarded_at` with `false` refused is
  the correct shape — a caller that could choose it could un-onboard or
  backdate.

  **`API_CONTRACT` §4 is corrected**, as you suggested. It had described a
  nested `allowance` object, a `subscription_ends` and an `active_session_id`,
  **none of which the implementation or `openapi.yaml` ever had**. You were
  right that §4 was the half that was wrong. And right that
  `active_session_id` is unnecessary — the active session is in
  `GET /sessions`, and a second source for the same fact is a second thing to
  keep true.

  ### T-035, and the one thing in it that touches your code

  Nothing — your T-034 frontend was already the whole client half, and I built
  the server to it rather than the other way round. The modal, the
  `patient_data_detected` → `{state: "blocked"}` mapping and your mocked test
  all now fire against a real 422.

  Two things worth knowing:

  - **The guard runs on the prototype's `/chat` too**, not just `/v1`. `PRD`
    P4 does not exempt anonymous visitors, and per your own V-10.3 the
    prototype is the only path they have. It returns 422 with
    `{"blocked": true}` there.
  - **It is deliberately conservative.** A bare name, a bare date and an age
    do **not** block — "Did Dr Mehta mention it?", "Did the pain start before
    Diwali?", "A 54-year-old man". A false block discards the learner's typed
    question, and that costs more than the rare miss. If S-10 ever looks like
    it is blocking something innocent, tell me the string rather than working
    around it.

  ### V-10.3 is still open, and it is not mine to close alone

  The anonymous trial still cannot use `/v1` — every consultation endpoint is
  `@require_auth` while `UX_SPEC` S-09/S-10 say "Auth: Both". **It is not in
  `BUILD_PLAN`.** P4 holds either way now, because T-035 guards both paths,
  but the web app is signed-in only until someone owns this. I have not
  invented a task for it; it needs to go in the plan properly, and `PRD` FR-2
  makes the trial a launch feature, so it cannot just be dropped quietly.

  **Done when:** nothing for you in V-9/V-10/V-11 — they are closed. T-037 is
  your last Phase 3 task.

- [ ] **Y-23** (2026-11-22, from Vraj) · **I marked your three merged tasks
  DONE in `BUILD_PLAN`. Say if you disagree.**

  `STATUS.md` had been stale since 4 Nov and still said 21 of 34 with Phase 3
  at 1 of 8, because only T-031 carried a DONE marker even though T-032,
  T-033, T-034 and T-036 were merged with build logs. That made planning
  misleading, so I marked them with their merge dates (T-032 2026-11-10,
  T-033 2026-11-15, T-034 and T-036 2026-11-22) along with T-035.

  **STATUS now reads 26 of 34 (76%), Phase 3 at 6 of 8, 9 d left.** If you
  consider any of yours not finished, say so and I will unmark it — I am
  recording that they merged, not judging that you are happy with them.

  **T-030 is deliberately still unmarked**, and it is mine: `DELETE /me` is a
  501 (API-9 is open and has a legal dimension), `/me/export` has no worker
  behind its 202 (API-10 needs a task), and it has no build log. Those are the
  9 days left in Phase 3 together with your T-037, and the honest reading is
  that Phase 3 is not done when T-037 lands — T-030 still needs closing out.

  **Done when:** you have confirmed or objected.

- [ ] **Y-24** (2026-11-22, from Vraj) · **If `pytest` has felt broken since
  you ran `npm ci`, this was why — fixed.**

  **Symptom:** the Python suite takes 9–45 minutes instead of ~80 seconds,
  prints nothing, and sits at **0 % CPU**. Nothing fails, so nothing tells you
  why. It reads exactly like a hang, and I spent a while blaming this laptop's
  disk before checking.

  **Cause:** `tests/test_validation_gate.py` clones the repository into a
  tmpdir to prove the detector gate fails on a degraded threshold. Its ignore
  list predates `web/`, so **from the first `npm ci` it copied 457 MB and
  ~100 000 files of `node_modules` — twice per run.** Pure I/O, hence the 0 %
  CPU. T-032 did nothing wrong; the test was never updated for a repo that
  has a JavaScript tree in it.

  **Fixed** on `feat/t-035-patient-data-guard` (`6babbcb`): the two duplicated
  `ignore_patterns` lists are now one `_IGNORE` constant excluding
  `node_modules`, `.next`, `.turbo` and the cache dirs, with a test asserting
  the exclusion so it cannot come back quietly. `web/src` is still copied —
  only build artefacts are skipped. **45 min → 67.7 s, 1068 passing.**

  **What this means for you:** pull `main` once this merges before you judge
  any Python test timing. And if you add a directory a tool fills — a
  `.turbo`, a `dist`, a `playwright-report`, anything `npm` or `uv` generates
  — add it to `_IGNORE` in that file, or the clone starts carrying it again.

  I also found it the hard way worth repeating: `lsof` on the stuck process
  answered in seconds what twenty minutes of theorising did not.

  **Done when:** you have seen a normal-speed run on `main`.

## Notes

### The `/v1` API, as of T-030 (2026-11-03)

18 of 23 operations live. The 5 stubs: three Stripe (T-041, Phase 4) and
`DELETE /me` (blocked, API-9). Every one answers **501 with the envelope**
rather than a 404, which is what sync point S-1 was always supposed to mean
and what did not exist until this task — an unbuilt path used to return
Flask's HTML 404 page, so a JSON client got a parse error pointing somewhere
unrelated.

Three things in the API that are load-bearing rather than stylistic, and that
a frontend could accidentally undo:

- **The error envelope is the same everywhere**, including 404s and 501s, and
  carries `code` (branch on this), `message` (copy, may be reworded) and —
  on 5xx only — `request_id`. 4xx deliberately omits it, because `UX_SPEC`
  §12.1 needs every admin refusal byte-identical and a per-request id makes
  any two differ. `X-Request-ID` is on every response regardless.
- **Pagination is cursor-based, never offset.** §2.5 rejects offsets because
  they duplicate and drop rows when something is inserted mid-scroll — which
  is exactly what happens when a learner finishes a consultation and then
  pages back through their history.
- **`POST /sessions/{id}/questions` does not consume the question on a model
  failure.** 503 `patient_unavailable`, nothing written, so the typed text is
  safe to resend. Preserve it in the textarea rather than clearing on error.

### The case bank is complete (2026-10-29)

Ten cases, all `draft`, none publishable until a clinician approves one —
migration 007's trigger, not a convention.

Two things learnt doing the last five that are worth knowing before anyone
touches content again:

- **The cost per case rose sharply at case 8.** Migration 017 seeded 40 topics
  and the first seven cases used every one, so each case after that needed new
  `topic_lexicon` rows, and two needed investigation keys that did not exist
  (colonoscopy, FIT, HLA-B27, two imaging keys). T-044 is the task that turns
  this back into a screen. Until then, a case is two migrations.
- **Both seed generators used to rewrite an applied migration.**
  `generate_case_migration.py` always wrote 019 and
  `generate_seed_migration.py` always wrote 017, and both have been applied
  since September. Rewriting one produces a file that still looks generated,
  still imports, and that no database will ever run. Both now require
  `--revision` / `--down-revision` and refuse to overwrite without `--force`.

`docs/cases_design.md` now holds a design section for all eight cases that
have one, the mapping between its numbering and the code's, and a comparison
table whose last row — "solved by" — is the one worth reading across: the bank
was built so no two cases fail the same way.

### Onboarding a clinical reviewer (2026-10-29)

Two new documents and one script, on `feat/reviewer-onboarding`:

- `docs/process/REVIEWER_ONBOARDING.md` — the operator's runbook: Supabase
  account, role, assignment, and how to verify it worked before the clinician
  tries. Verification matters because `UX_SPEC` §12.1 makes every refusal an
  identical 404, so nothing about the failure says which of five causes it was.
- `docs/process/REVIEWER_GUIDE.md` — **what the clinician receives**, and the
  only document in the repo written for someone outside the team. It exists
  because of one word in the rubric: *trap validity* is unreadable without
  knowing that every Nidan case is built around a plausible wrong answer. A
  reviewer meeting it cold marks the case down for being misleading — and
  since any dimension below 4 blocks approval, that misunderstanding silently
  stops a case publishing. A `.docx` is generated alongside it.
- `scripts/provision_reviewer.py` — replaces the `psql` one-liner in
  `LOCAL_ADMIN_ACCESS` §3, which writes to `auth.users` (Supabase's table, not
  ours), changes an existing account's privilege without saying so, and records
  nothing. This refuses all three and writes an `audit_log` row.

**Give both reviewers the same first case, independently.** Comparing two first
reviews of one case tells you whether the rubric is being read the same way,
which is worth more right now than two more cases reviewed.

### ~~Signing in to `/admin` on a local machine (answers V-5)~~

> **Superseded 2026-10-28** by `docs/process/LOCAL_ADMIN_ACCESS.md` on
> `main`, which is verified end to end. Kept for the record; the steps
> below are untested and omit the migration, the rebuild and the 5433
> port. Follow the doc.

The console has no login page of its own: `ADR-0002` says Supabase issues
credentials and the backend only verifies them, so a local sign-in means getting
a real Supabase token and letting the app verify it. Five steps.

**1 · Put the two values in `.env`.** `SUPABASE_URL` is **sent privately**.
`SUPABASE_JWT_AUDIENCE` is the Supabase default and is in `.env.example`
already:

```
SUPABASE_JWT_AUDIENCE=authenticated
```

**2 · Get an access token.** Either from the Supabase dashboard
(Authentication → Users → your user → generate a link), or by signing in
against the project's auth endpoint. The anon key for that call is **sent
privately**:

```bash
curl -s "$SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"..."}' | python3 -m json.tool
```

Keep `access_token`. Note the `sub` claim inside it — that is your user id, and
step 3 needs it. Decode the middle segment to read it:

```bash
python3 -c "import base64,json,sys; t=sys.argv[1].split('.')[1]; print(json.loads(base64.urlsafe_b64decode(t+'=='*3))['sub'])" "<access_token>"
```

**3 · Give yourself an admin profile on your *local* database.** Supabase holds
the account; your local Postgres holds the profile, and they are joined by that
id. `profiles` references `auth.users`, so both rows are needed:

```bash
docker compose up -d db
psql "$DATABASE_URL" -c "INSERT INTO auth.users (id) VALUES ('<sub>') ON CONFLICT DO NOTHING;"
psql "$DATABASE_URL" -c "INSERT INTO profiles (id, platform_role) VALUES ('<sub>', 'admin') ON CONFLICT (id) DO UPDATE SET platform_role = 'admin';"
```

Use `'reviewer'` instead of `'admin'` to see the console as a clinician does —
worth doing once while building T-023, because that is the role that reaches the
review queue and nothing else.

**4 · Set the cookie.** `bearer_token()` accepts either an
`Authorization: Bearer` header or the `sb-access-token` cookie, and a browser
can only do the cookie. With the app running at `http://localhost:5000`, open
dev tools → Application → Cookies and add:

```
name   sb-access-token
value  <access_token>
path   /
```

**5 · Open `http://localhost:5000/admin`.**

**If you get a 404, that is the access control working, not a missing page.**
Every refusal returns an identical 404 — no token, expired token, signed in
without privilege (`UX_SPEC` §12.1). So a 404 means one of: the cookie is not
set, the token has expired (they last about an hour — redo step 2), or the
`profiles` row has the wrong id or `platform_role`. Check the last one with:

```bash
psql "$DATABASE_URL" -c "SELECT id, platform_role FROM profiles;"
```

---

## Done

- **2026-11-23** · **T-037 built on `feat/t-037-history-progress`
  (`89f60ae`), not pushed yet — the last task in Yogesh's Phase 3 run.**
  S-14 history (cursor-paginated), S-15 read-only detail, S-16 progress with
  its <3-case empty state; decline worded and styled exactly like improvement,
  broken on purpose to prove the test. Fixes the T-033 dashboard's stale
  `SessionPage` (V-12). 218 web / 1103 backend tests. T-036 merged (PR #48). With T-035 merged and T-037 built, **Phase 3's frontend is done**; what
  remains is Vraj's T-030 close-out and T-038, and the unowned trial gap
  (V-10.3). Local cases published via `publish_for_demo.py` (Y-26).

- **2026-11-29** · **T-036 built on `feat/t-036-feedback` (`18502cc`), not
  pushed yet.** S-13's eight sections in order, S-12 while a diagnosis is
  submitted and while feedback is not ready. All six criteria are tests; the
  vocabulary scan and the fallback-renders-identically check were each broken
  on purpose. 197 web / 988 backend tests. T-034 merged (PR #47). Yogesh's
  Phase 3 run now has T-037 left.

- **2026-11-22** · **T-034 built on `feat/t-034-consultation` (`b48b54e`),
  not pushed yet.** S-09 preview, S-10 consultation in every state (three
  panes / strip + drawer / §4.1 refusal, all measured in a browser), S-11
  diagnosis modal. The U2 criteria are tests; breaking the counter test on
  purpose found it — and T-033's vocabulary scan — blind to text joined
  across elements (`…Send1/40Give…`), now fixed. 177 web / 988 backend tests.
  **Y-19 done**: the 429 drives the cap, no counter anywhere. T-033 merged
  (PR #46). Still waiting on a published case for a live run.

- **2026-11-15** · **T-033 built on `feat/t-033-dashboard-onboarding`
  (`d2eeb33`), not pushed yet.** S-07 onboarding and S-08 dashboard in all
  four states, computed by a pure `buildDashboard` so each state is a test;
  `anchored` renders as "Worth reconsidering". 148 web / 988 backend tests.
  **Y-20 done:** `Nidan_T-032_Build_Log.docx` committed, with T-033's — and
  only those two, via `build_docx.py T-032-… T-033-…`, so none of the other
  45 churned. **Y-17:** Supabase answers; read from its settings that
  **Confirm email is ON** and **Google/Apple are not enabled yet**. The live
  sign-up has to be Yogesh's own (Claude may not create accounts on a hosted
  provider), so T-032 and T-033 stay unticked in `BUILD_PLAN` until he has
  done one. **Y-19 (S-10's 429, no counter)** is T-034's, next.

- **2026-11-04** · **T-032 built on `feat/t-032-nextjs-scaffold` (`e42c287`),
  not pushed yet — Yogesh decides.** `web/`: Next.js 16 + TypeScript 5.9,
  tokens from §3.1–3.4 (tested against UX_SPEC.md itself), types generated from
  `openapi.yaml` with a CI staleness check, the 19 §3.5 components, and
  S-02…S-06 + S-22 as server actions with httpOnly cookies. 105 web tests,
  tsc/ESLint clean, `npm audit` 0, production build green; 979 Python tests
  still pass. **Not yet run against the live Supabase project** — needs the
  anon key (Y-4) and V-7's dashboard settings. Also on Yogesh's laptop today:
  `main` pulled to PR #42, local DB at 032, and Y-13's `GROQ_MODEL` changed to
  `openai/gpt-oss-120b` — but **`GROQ_API_KEY` is empty on this laptop**, so
  `test_api.py` cannot pass here until Yogesh pastes the key in.

- **2026-11-04** · **Y-12 resolved — the patient model was retired, not
  misconfigured.** `python test_api.py` returned 404 model_not_found; Groq
  retired `llama-3.3-70b-versatile` on **2026-08-16** on the Free and Developer
  tiers, so it had been broken for eleven weeks. Nothing in the suite caught it
  and nothing should have — T-002 criterion 1 is that no test makes a network
  call, so the suite never asks a provider whether the configured model still
  exists.

  Moved to `openai/gpt-oss-120b` on branch `feat/t-031-gateway-accounting`
  (commit `7113239`), together with the `reasoning_effort` handling and the
  `message.reasoning` guard that a reasoning model requires. `test_api.py` now
  runs through the real gateway — building its own client had made it a test of
  a path the application does not take, and it reported "empty response" for a
  model the gateway handled fine. Verified live: 97 tokens in, 34 out, 666 ms,
  $0.000035. **Action for Yogesh moved to Y-13.**

- **2026-10-29** · **V-6 answered.** Both of Yogesh's T-023 additions reviewed.

  **`CaseRepository.for_review()` — approved as it stands.** Right shape: read
  only, `AdminUser` or `ReviewerUser`, and migration 024's policy is what
  actually permits the SELECT rather than the Python check. No change.

  **`ReviewRepository.reviewers()` — replaced, as you suggested.** Migration
  025 adds `privileged_profiles_are_mutually_visible`, so the `ServiceActor`
  is gone. You were right that it was a migration and right to flag it: with
  the bypass in place `ADR-0016`'s "confined to one module" and `CLAUDE.md`'s
  "`anonymous.py` is the one path where RLS is OFF" were both false.

  The cause was one missing `TO` in migration 016 — `own_profile` is
  `FOR ALL USING (id = auth.uid())` with no role, so it bound `nidan_admin`
  too. The grant was always there.

  **It covers `nidan_reviewer` as well as `nidan_admin`**, because
  `_reviewer_names()` is called for reviewers too, not only on the admin
  branch — admin-only would have rendered "a reviewer" in their queue.
  `_reviewer_names()` now opens with `current_reviewer()`. Nothing else in
  `nidan/web/admin/reviews/routes.py` changed.

  Branch `feat/migration-025-admin-reads-reviewers`. 714 tests.

- **2026-10-29** · **T-023 built** on `feat/t-023-clinical-review`
  (`a101ee5`), **not yet pushed or merged** — Yogesh decides. Queue with three
  tabs, audited assignment, rubric form beside Playtest, publish with 409.
  708 tests pass, none skipped; the rubric-floor and trigger tests were both
  watched failing. Uses everything from Y-2. Y-3 and Y-5 are done: briefs read
  from `docs/process/phase-2-briefs/`, `main` pulled, local DB at 024.
  Still open for Yogesh: Y-1 (remote URL) and Y-4 (needs the anon key).

- **2026-10-28** · **S-4 settled — `ADR-0017`, data residency in the EU
  (Frankfurt), `eu-central-1`. MERGED, PR #28, `b98ddc9`.** The last open
  ⟨DECIDE⟩ item; **no ⟨DECIDE⟩ items remain.** Supabase project `Nidan`
  created and `/admin` reached with a real token end to end. Keeping the data
  in the EEA removes the GDPR Chapter V transfer obligation for EU users
  rather than satisfying it, and the obligation is one-directional.

  Two bugs found while verifying it, both fixed in the same PR: compose never
  passed `SUPABASE_URL` to the app, and package-data shipped 4 of 25 templates
  and 2 of 4 JS files — see Y-5, it broke the case editor and Playtest in any
  Docker build. 685 tests pass on the merged result; a rebuilt image now
  packages 25/25 templates and 4/4 static files.

- **2026-10-28** · **T-022 playtest merged** (PR #24) and a T-021 form fix
  (PR #27). Phase 2 is 3 of 4 tasks done; **T-023 is all that remains**, and it
  is the gate — approving a case is what lets the two clinicians start and the
  five remaining cases be written. `STATUS.md` regenerated: 19 of 34 tasks,
  36 d of 83.

- **2026-10-28** · **V-1, V-2, V-3** · T-023 backend built: `nidan_reviewer`
  role and `ReviewerUser` actor (reads drafts, inserts reviews, writes no
  content), `review_assignments` table, `ReviewRepository`, and
  `CaseRepository.publish()` with typed exceptions. Migration 024. Rubric floor
  enforced at the write, not only in the form. Both guards probed. **Merged
  2026-10-28, PR #26, `6680642`** — 654 tests pass on the merged result, 235 of
  them against real Postgres.

- **2026-10-28** · **V-4** · Phase 2 briefs brought up to date and **merged**
  (PR #25). T-020, T-021 and T-022 briefs retired as those tasks landed;
  `00_START_HERE.md` and the README now point at T-023 alone. Yogesh told in
  Y-3.

- **2026-10-28** · **V-5** · Local `/admin` sign-in steps written up in Notes
  above; the two `.env` values sent privately. Yogesh told in Y-4.

- **2026-10-28** · Yogesh's laptop brought up to date: local `main` = GitHub
  `main` (`384266c`, T-021 merged), venv reinstalled as `nidan`, Docker running,
  607 tests pass with none skipped, local DB migrated to `023`, `DATABASE_URL`
  added to `.env`.
