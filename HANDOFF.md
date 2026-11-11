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

- [ ] **Y-18** (2026-11-11, from Vraj) · **API-6 is leaning one way. Do not
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
