# T-030 · JSON API

| | |
|---|---|
| **Task** | T-030 · JSON API ⭐ *(sync point S-2)* |
| **Phase** | 3 — API and web app |
| **Owner** | Vraj |
| **Estimate** | 6 d |
| **Actual** | 2 d of building (2026-11-01 → 2026-11-03), then **19 days of closeout** |
| **Depends on** | T-016, T-017 |
| **Spec** | `API_CONTRACT` §4–8 · `openapi.yaml` |
| **PRs** | #35, #36, #37, #38, #39, #40, #41 — plus #46 (strict YAML), #47 (API-6), #50 (API-9) |
| **Status** | ✅ Done — 2026-11-22 |

---

## 1 · Summary

`/v1` is the JSON API the Next.js app is built against: **19 of the 22
operations `openapi.yaml` declares**, across nine modules and 1 982 lines, with
an error envelope that cannot return an uncatalogued code, cursor pagination
that cannot be an offset, idempotency on the one irreversible write, and all
nine contract tests from `API_CONTRACT` §11.

The three remaining operations are Stripe (`/billing/checkout`,
`/billing/portal`, `/webhooks/stripe`) and belong to T-041. They answer 501
with the envelope rather than a 404, which is what sync point S-1 means.

**The build took two days and the closeout took nineteen.** That gap is the
honest headline of this log. The code was merged on 3 November; the task could
not be called done until 22 November because it had raised five open questions
about its own contract, two of which were blocking, and the last of them —
API-9, GDPR erasure — needed a decision with a legal dimension rather than
another slice of code.

---

## 2 · The problem

T-029 closed Phase 2 with a working product that only existed as
server-rendered Jinja. `api/routes.py` reads cases from `domain/content/cases.py`
rather than the published bank, holds no contract, returns HTML error pages,
and is the prototype. Nothing a separate frontend could be built against
existed.

`openapi.yaml` had been written at T-011, before any of it was implemented, on
the explicit bargain recorded in the file itself: *"the contract exists first
so the frontend can be built against it (sync point S-1)."* T-032 generates
`web/src/api/schema.ts` from it. So the contract was load-bearing for
somebody else's work before a line of `/v1` existed — and, as slice 1 found,
the mechanism that was supposed to make that bargain work had never been
built.

---

## 3 · Definition of done

Copied verbatim from `BUILD_PLAN` §7:

```
Accept   1. Every v1 endpoint implemented per openapi.yaml
         2. Error envelope on every 4xx/5xx; all codes in the §10 catalogue
         3. Idempotency-Key honoured on /diagnosis
         4. Cursor pagination on collections
         5. Rate limits enforced per API_CONTRACT §2.9
Tests    Contract tests CT-1..CT-9 (API_CONTRACT §11) — CT-1 and CT-5 are mandatory
```

### How each one actually stands

| # | Criterion | Verdict |
|---|---|---|
| 1 | Every endpoint implemented | **Met for this task's scope.** 19 of 22; the three absent are Stripe, owned by T-041, and each answers 501 with the envelope rather than a 404 |
| 2 | Envelope and catalogue | **Met, and enforced rather than asserted.** `CATALOGUE` is data in `nidan/api/errors.py`; `error()` raises on an unknown code *and* on a status that contradicts §10 |
| 3 | Idempotency on `/diagnosis` | **Met.** CT-8. Body hashed, never stored |
| 4 | Cursor pagination | **Met.** `(started_at, id)`, never an offset |
| 5 | Rate limits per §2.9 | **Partially met — see §10.** Two of the six scopes are enforced here, two live elsewhere, and **sessions-started-per-day is not enforced at all** |
| — | CT-1 … CT-9 | **Met.** All nine exist and each was probed by breaking it |

Criterion 5 is the one that was quietly weaker than it looked, and it took
writing this document to notice. That is an argument for writing these at the
time rather than nineteen days later.

---

## 4 · What was built

```
nidan/api/
  errors.py           the envelope + the §10 catalogue AS DATA — 70 lines
                      shared with the admin console, so NOT inside v1/
  v1/
    blueprint.py      the Blueprint alone, so route modules import acyclically
    __init__.py       imports the route modules, then registers the 501s
    identity.py       §4 · /me (POST, GET, PATCH, DELETE)          259 lines
    catalog.py        §5 · the two universal menus — CT-3           90
    case_view.py      §6 · the ONLY place a case becomes a response — CT-1   65
    sessions.py       §6, §7 · POST + GET /sessions, GET /sessions/{id}     264
    consultation.py   §6 · questions, examinations, investigations  323
    conclusion.py     §6 · diagnosis, feedback, rating, abandon      292
    reasoning.py      the ONLY place a detector becomes text — CT-4, CT-5   196
    account.py        §4, §7 · /progress, /me/export, the erasure    220
    pagination.py     §2.5 cursors — never offsets                  103
    contract.py       the declared-but-unbuilt 501s, and JSON 404/405  113
```

**Four modules exist so that there is exactly one of them.** That is the
structural idea of this task and it is worth stating plainly, because each one
replaced a temptation to do the obvious thing in several places:

- `case_view.py` — `POST /sessions` and `GET /sessions/{id}` both return a
  `case` object and `PRD` FR-3.4 forbids eight fields in it. Two serialisers
  would satisfy CT-1 the day they were written and diverge later, and the one
  that diverged would be the one no test covered.
- `reasoning.py` — a detector's `reason` string contains the exact vocabulary
  CT-5 bans. One module means "there is only one boundary" is a fact rather
  than a claim.
- `errors.py` — the catalogue as data, so the rule "a code is never renamed or
  repurposed" is checkable.
- `contract.py` — one place that knows which declared operations are unbuilt,
  and a list that only shrinks.

### Built in five slices

| Slice | Date | PR | What landed |
|---|---|---|---|
| 1 | 11-02 | #35 | The envelope, the catalogue as data, the 501 handler, `api/v1.py` → `api/v1/`. **No new endpoints** |
| 2a | 11-02 | #36 | Catalogue menus, `GET /sessions` pagination, `PATCH /me`. CT-3, CT-9 |
| 2b | 11-02 | #37 | `GET /sessions/{id}`, `case_view.py`. **CT-1** |
| 3 | 11-03 | #38 | The write path — questions, examinations, investigations. CT-2 |
| 4 | 11-03 | #39 | Conclusion, feedback, rating. CT-4, **CT-5**, CT-8 |
| 5 | 11-03 | #40, #41 | `/progress`, `/me/export`. `DELETE /me` blocked |

Slice 1 deliberately shipped no endpoints. Retrofitting an envelope across
sixteen handlers is the expensive version of the same work, and the slice that
feels like it is making no progress is the one that made the other four cheap.

---

## 5 · Step by step

```bash
# the stack, because every /v1 test is against real Postgres
docker compose up -d db
export DATABASE_URL="postgresql+psycopg://nidan:…@localhost:5433/nidan"
alembic upgrade head

# per slice
pytest tests/db/test_v1_reads.py -q --no-cov        # the slice's own tests
pytest tests/test_api_contract.py tests/test_openapi.py -q --no-cov
ruff check . --fix && mypy nidan/domain --strict && lint-imports
pytest -q --no-cov                                  # the whole suite, every time

# the contract and the frontend move together — three things, one commit
cd web && npm run gen:api && npm run check:api && npm run typecheck
```

The habit that mattered most: **probe each contract test by breaking the thing
it guards**, and record what the failure said. A contract test that has never
been seen to fail is a comment.

```bash
# e.g. CT-5, slice 4 — forward bias_detail instead of rebuilding from counters
#   FAILED … - AssertionError: 'anchoring' in response body
```

---

## 6 · Where we diverged from the spec

**`POST /sessions` returns `session_id`, not `id`.** `openapi.yaml`'s `Session`
schema had drifted from `API_CONTRACT` §6 and nothing compared them, so both
were locally "right": `id` for `session_id`, a flat `patient` with no case
title, `{role, text}` transcript entries, `examinations_performed` for
`examinations_done`. The existing `POST /sessions` matched the schema.
Reconciled to §6, because §6 is the prose contract and the schema is what
Yogesh's generated types come from.

**`questions_remaining` is absent.** §6 argued for it; `UX_SPEC` S-10's table
of what is deliberately absent *opens* with "Question counter". Shipped absent
and logged rather than settled in passing — see §7.

**`session_already_concluded` → `session_concluded`.** §6's table and §10's
catalogue disagreed. The catalogue governs, because §10 is the document that
says a code is never renamed. API-7.

**`answer.trap_explanation` does not exist.** §6's feedback example shows it;
nothing in `case_versions.content`, `cases.py` or anywhere else has it.
Returns `answer.anchor_topic`, which is real. Synthesising the prose
server-side would be the LLM-never-marks rule broken in the other direction.
API-8.

**`DELETE /me` returns 202, not §4's 204.** Settled 19 days later as
`ADR-0018`; the reasoning is in §7 and in that record.

**`api/routes.py` was not deleted**, despite its own docstring saying T-030
replaces it. It was the only working end-to-end consultation until T-034
landed, 13 days of Yogesh's work away. It survives for the anonymous trial —
see §10.

---

## 7 · Problems hit

### 7.1 · The 501 that was never built

`openapi.yaml` declares `501 NotImplemented` on every unbuilt operation and
says why. `api/v1.py`'s docstring repeated the claim: *"everything not
implemented here still answers 501"*.

**Nothing implemented it.** An unbuilt `/v1` path returned Flask's default
**HTML 404**. So sync point S-1 never worked, a JSON client got a parse error
pointing somewhere unrelated, and CT-6 and CT-7 failed on every declared
route.

Two documents and a docstring all asserted a behaviour that no code produced,
and the reason nobody noticed is that the assertion was in the place you would
go to check.

The handlers are registered on the **app**, not the blueprint:

```python
@bp.errorhandler(404)     # looks right, silently never fires
```

A 404 for an unmatched URL is raised *during routing*, before Flask has
decided which blueprint the request belongs to — so there is no blueprint
whose handler could run. 405 is the same. Two tests caught it.

### 7.2 · Four error codes had already drifted

§10 says a code "is never renamed or repurposed once shipped", and lived only
in a Markdown table and a YAML enum — nowhere the code could check. Making it
data found four, **each by using it rather than by reading it**:

| Code | What was wrong |
|---|---|
| `service_unavailable` | In the enum, returned by `require_auth` on a JWKS outage, absent from the §10 table |
| `not_implemented` | In neither |
| `consent_version_required` | Referred to by §4, in neither |
| `patient_data_detected` | Added later, by T-035, through the same gate |

`error()` now raises on an uncatalogued code **and on a status that
contradicts §10**. `error("not_found", …, 403)` is the §2.7 information leak,
and both arguments read as perfectly plausible — which is why the status
argument became optional and derived.

### 7.3 · The one that should have shipped broken, and did

**`cases.content()` returns the `case_versions` ROW; the payload is its nested
`content` key.** All six call sites in slices 2b and 3 passed the row to a
serialiser. For two merged PRs:

- the patient came back with **every field `None`**
- the LLM got an **empty system prompt** — no persona at all
- **every examination returned the master normal result**, because the
  case-specific block was never found. No case had any abnormal finding.

Every assertion I had written asked whether a key was *present*.
`set(case["patient"]) == {…}` holds perfectly well when all five values are
`None`, and `assert body["result"]` holds for the normal report. The product
was broken in the way that matters most and nothing was red.

Two things came out of it, and the second is the one that pays:

- `cases.case_for_session()` returns the **domain's** `Case` shape — adds `id`
  (the slug `replay` needs), promotes `title`, flattens `patient_intro` out of
  `patient.intro`. That last one surfaced as a `KeyError` inside the feedback
  builder: a 500 at the moment a learner submits, after doing all the work.
- `test_the_case_adapter_supplies_every_key_the_domain_reads` walks the AST of
  `nidan/domain` for `case["x"]` and `case.get("x")` and asserts the adapter
  supplies all fourteen. Hand-maintaining that list is the bug it exists to
  catch.

**The lesson, which changed how every later slice was tested:** assert
*values* with known answers, not shapes. Slice 5's tests cross a timezone
boundary with an arithmetic answer; the trend test pins a direction over
twenty sessions; the empty-state test checks a figure is `None` rather than
`0.0`. Three tests in slice 4 are marked `SUBSTANCE` and all three would have
failed before the fix.

### 7.4 · CT-5 caught a live leak, not a hypothetical one

The detectors' own `reason` strings contain the words CT-5 forbids:

```
"No significant anchoring pattern detected."
"No premature closure detected — thorough workup completed."
"Confirmation bias occurs when we seek only evidence that supports our
 first instinct."
```

Three of six branches. Forwarding `bias_detail` — the obvious implementation,
and the one the prototype uses — ships all three banned terms to a learner.
`reasoning.py` rebuilds the prose from `counters`, which is what `DATA_MODEL`
§8.5 added them for and what `PRD` P3 wants cited anyway: the learner's own
actions. **Nothing is filtered; the internal text simply never reaches the
boundary**, which is a stronger property than scrubbing.

### 7.5 · And I over-applied it twice

**`anchored` was in my banned list and should never have been.** CT-5 flagged
the progress payload and the term was `anchored` — a `diagnosis_verdict` enum
value that §7's own `verdict_distribution` example carries. §11's CT-5 lists
three terms, `CLAUDE.md` four, **neither lists `anchored`**. I added it in
slice 4 reasoning it was a variant of "anchoring", and produced a guard that
failed the contract it was guarding.

Widening a guard past what the spec says is how it starts producing false
positives, and a false positive is what gets a guard loosened later for the
wrong reason.

**`request_id` on every error broke four tests, and they were right to
break.** §2.6 lists it and `UX_SPEC` S-21 shows it to the user on a 500. But
`UX_SPEC` §12.1 requires every admin-console refusal to be **byte-identical**,
so "no token", "expired token" and "signed in without privilege" are
indistinguishable — and a per-request id makes any two refusals differ. The id
carries nothing, so those tests are a proxy for the property rather than the
property; but the proxy is what would notice a real difference creeping in.
5xx only, which is §2.6's own line.

### 7.6 · Two test guards that held stale copies of what they guarded

**`test_openapi.py`'s equivalence check had stopped checking most
operations.** It derives "is implemented" from the url_map, deliberately, so
it cannot go stale — but it compared Flask's `/sessions/<uuid:session_id>`
against the contract's `/sessions/{id}`, so **every parameterised path looked
unimplemented** and the test went on requiring a 501 it would never notice had
become wrong. Found because `GET /sessions/{id}` was implemented and the test
stayed green.

**`test_no_network.py` kept its own hard-coded copy of the patch list.**
`fake_llm` patches each `call_llm` import site explicitly and that test exists
to fail when the list goes stale — so adding a site to `conftest` and not to
the test reported *"imports call_llm but conftest does not patch it"* about a
module conftest **did** patch. Both now read `LLM_IMPORT_SITES` from
`tests/app_config.py`.

A guard with its own copy of the truth is a second thing to keep in sync, and
it fails in the most confusing direction: telling you the code is wrong when
the guard is.

### 7.7 · The append-only trigger, three times

1. **Slice 3** — a teardown that deleted a profile cascaded `profiles` →
   `sessions` → `session_events` and hit *"Table session_events is
   append-only."* TRUNCATE bypasses row triggers, which is what a teardown
   wants and what application code must never be able to do.
2. **Slice 5's export test** — the same thing on `audit_log`. Migration 002's
   `forbid_mutation` is applied by 015 as well as 010.
3. **Slice 5's `DELETE /me`** — the wall slice 3 predicted in writing: *"Worth
   remembering for slice 5: `DELETE /me` will hit the same wall."*

### 7.8 · The nineteen-day closeout

Three of the five open questions this task raised had to be settled before it
could be called finished, and each needed something other than code.

**API-6 · `questions_remaining`** — settled 11 Nov. The contract contradicted
itself: §6 argued for the field and cited `UX_SPEC` S-10 as surfacing it near
zero, and S-10's table of what is deliberately absent **opens** with
"Question counter | U2". §6 was misreading the document it leaned on. Absent,
permanently; the cap is a refusal, not a gauge, and a client that wants the
figure counts `transcript` entries of `type: question`.

**A duplicated YAML key reached the frontend's CI four days later.** Slice 5
added a second `description:` to `DELETE /me` without removing the first.
`yaml.safe_load` keeps the last one silently, so **every assertion in
`tests/test_openapi.py` passed over a file the type generator refused** — a
backend mistake that surfaced only in `npm run check:api`. That test now
parses with a strict loader, and
`test_the_strict_loader_actually_rejects_a_duplicate` proves the guard bites.

**T-035's new conformance test found three more drifts in this task's work.**
`tests/test_request_body_conformance.py` walks the AST of `api/v1/` for the
keys each handler takes off the JSON body and compares them with the schema
the contract attaches to that operation, in both directions. The CT tests
guard what must be **absent** from a response; nothing checked that the shape
we *declare* is the shape we *read*. On its first run it found
`consent_version` — read and required by `PATCH /me`, declared nowhere — so a
client generated from the contract **could never give research consent at
all.**

**API-9 · GDPR erasure** — settled 22 Nov as `ADR-0018`, and the reason it
took nineteen days is that it was not a coding problem. §4 says `DELETE /me`
"executes `DATA_MODEL` §10.2"; §10.2's erasure UPDATEs `session_events`;
migration 010 makes that table append-only with a trigger that refuses even
the table owner. Returning 204 having anonymised only the profile would claim
an erasure that did not happen, so slice 5 shipped a 501 and logged four
possible resolutions, none of which a request handler should pick.

Settling it also found that §10.2 itself redacted **two of the four**
text-bearing event types and never mentioned `feedback_texts`, where `PRD` P3
*requires* the learner's own questions to be quoted back. The hardest half of
the erasure was guarded by a database trigger; the easy half was simply
absent.

---

## 8 · Verification

```
pytest -q --no-cov                        1089 passed in 105.9 s
  of which, this task's surface:           149 passed in  35.5 s
    tests/db/test_v1_reads.py               28
    tests/db/test_v1_conclusion.py          26
    tests/db/test_v1_consultation.py        19
    tests/db/test_v1_progress.py            14
    tests/db/test_erasure.py                23
    tests/test_api_contract.py              13
    tests/test_openapi.py                   12
    tests/test_request_body_conformance.py    3

ruff check .                              All checks passed
mypy nidan/domain --strict                no issues, 16 source files
lint-imports                              2 contracts kept, 0 broken
cd web && npm run check:api               schema.ts matches openapi.yaml
             npm run typecheck            clean
             npm run lint                 clean
```

### The nine contract tests, and what each was probed with

| CT | Guards | Probed by |
|---|---|---|
| **CT-1** | No forbidden field in a `case` object, at any depth | A leak at the top level, and one buried three levels inside `case.patient` |
| **CT-2** | No assessment state in a consultation response — *and the event must carry it* | Returning `matched_topics` |
| CT-3 | The catalogue cannot reveal relevance | Leaking `category` into the menu |
| CT-4 | Detector output reaches a learner only through `reasoning.py` | Forwarding `bias_detail` |
| **CT-5** | No bias vocabulary in any response body | Forwarding `bias_detail` |
| CT-6/7 | Envelope and catalogue agreement | Dropping a code from `CATALOGUE`; deleting a line from `UNIMPLEMENTED` |
| CT-8 | Idempotency replays rather than re-executes | Not storing the outcome |
| CT-9 | A learner's history cannot be read with a bypassing actor | Opening the scope with one |

**CT-1 checks keys at every depth, not substrings of the body.** The first
version swept the raw response for all twelve forbidden terms and failed on
the response §6 asks for — `examination` is a substring of
`examinations_done`. It now walks every key at every depth for exact matches,
and sweeps the raw body only for terms that cannot mean anything else.

---

## 9 · What this changes for you

```bash
git pull
docker compose up -d db && alembic upgrade head      # 33 migrations now
pytest -q --no-cov
cd web && npm run gen:api && npm run check:api
```

- **`POST /v1/sessions` returns `session_id`, not `id`.** Three assertions in
  `tests/db/test_allowance.py` were updated with it.
- **`DELETE /v1/me` answers 202, not 204**, requires
  `{"confirmation": "DELETE"}`, and returns `{status, retained,
  completes_within_hours}`.
- **An unbuilt `/v1` path returns a JSON 501, not an HTML 404.** If you were
  branching on 404 for "not built yet", stop.
- **A wrong verb on a `/v1` path is 404, not 405.** 405 carries an `Allow`
  header listing what the path accepts, and §2.7 declines to confirm the
  existence of things.
- **Adding an error code means three files in one commit** — `errors.py`,
  `API_CONTRACT` §10, `openapi.yaml`. `error()` raises otherwise.
- **Touching `openapi.yaml` means three things in one commit**: the contract,
  the code, and `web/src/api/schema.ts` via `npm run gen:api`. **A
  description-only edit counts** — the generator copies them into comments.

---

## 10 · Known debt left behind

| # | What | Which task |
|---|---|---|
| 1 | **`sessions.py:204`'s `QUESTION_CAP = 40` is dead code, and `CLAUDE.md` calls it "the single home for the 40".** Nothing references it; the live cap is `QUESTIONS_PER_SESSION` in `consultation.py:41`. So the 40 is declared twice, and the rule points at the copy that does nothing | **Unassigned — see below** |
| 2 | **§2.9's sessions-started-per-user limit (20/day) is not enforced anywhere.** The per-session cap and the hourly question limit are; the daily session limit is absent, and the free tier's 3/month is a different rule that does not cover a Pro account | Unassigned |
| 3 | **No `X-RateLimit-*` headers.** §2.9 specifies them for the two per-user scopes. `Retry-After` is sent on the 429 | Unassigned |
| 4 | `POST /me/export` returns 202 and nothing builds the export; `DELETE /me`'s three external steps do not run | **T-038** |
| 5 | `api/routes.py` survives, and with it the only path an anonymous visitor has. **Every `/v1` consultation endpoint is `@require_auth`, while `UX_SPEC` S-09/S-10 say "Auth: Both"** — so the trial cannot use `/v1` at all, and `PRD` FR-2 makes it a launch feature | **Unassigned — needs a task** |
| 6 | `user_progress` has a table, an RLS policy and has never been written to. Trends compute on read, deliberately; `DATA_MODEL` §11.5 is the query if a cache is ever justified | Not debt — recorded so nobody "fixes" it |
| 7 | API-8 is marked "decide before T-036" in §13 and T-036 has shipped, working around it in copy. The row is stale rather than wrong | Unassigned |

**Items 1, 2 and 3 were found while writing this document, not while building
the task**, which is the argument for writing these at the time. None is
urgent; item 1 is actively misleading, because a rule in `CLAUDE.md` names a
constant that does nothing — I have corrected that sentence rather than leave
a false claim in the file every session reads.

**Item 5 is the one to worry about.** It is not a rough edge, it is a launch
feature with no owner and no task.

---

## 11 · How to undo it

Nothing here is destructive, and the only schema change is migration 033:

```bash
alembic downgrade 032        # restores the unconditional append-only trigger
                             # DELETE /me then fails rather than answering 501,
                             # so put the contract.py entry back too
```

The `/v1` surface can be removed wholesale without touching the prototype:
`api/routes.py` reads cases from `domain/content/cases.py` and shares no code
with `api/v1/` except `errors.py` and the repositories. `create_app()`
registers the two blueprints independently.

`web/` is built entirely against `/v1`, so removing it strands the frontend —
which is what sync point S-2 means.

---

## 12 · What it taught

**A specification can assert a behaviour that no code produces, and the
assertion will be in the first place you look.** The 501 handler, the four
drifted error codes and §10.2's unrunnable erasure are the same failure three
times: a document describing the system to itself, with nothing comparing the
two. Every fix was the same shape — make the claim data, and let a test
compare it.

**Shape assertions pass on broken data.** `cases.content()` shipped a patient
with every field `None`, an empty system prompt and no abnormal findings in
any case, through two merged PRs, with a green suite. The assertions all asked
whether keys existed.

**A guard needs probing, not writing.** Every contract test here was seen to
fail before it was trusted, and two of them — `test_openapi.py`'s path
normalisation and `test_no_network.py`'s stale list — had silently stopped
guarding anything.

**Log the contradiction; do not resolve it in a handler.** Five questions came
out of this task. API-6 looked like a judgement call and turned out to have a
documented answer that §6 had misread. API-9 looked like a bug and was a legal
decision. Settling either in passing, inside a route, would have buried it.
