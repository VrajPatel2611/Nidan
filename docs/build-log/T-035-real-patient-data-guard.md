# T-035 · Real-patient-data guard

| | |
|---|---|
| **Phase** | 3 — API and web app |
| **Owner** | Vraj |
| **Estimate** | 1 d |
| **Depends** | T-034 |
| **Spec** | `PRD` FR-4 · `PRD` P4 · `UX_SPEC` S-10 |
| **Branch** | `feat/t-035-patient-data-guard` |
| **Completed** | 2026-11-22 |

---

## 1. What it is for

`PRD` P4, in its own words: *"All patients are synthetic. The product never
advises on a real case, and actively blocks attempts to enter real patient
data… it is what keeps us outside medical-device regulation, and it is the
honest description of what we do."*

That makes this the one input that changes what the product legally **is**. A
trainee pasting a ward patient into a synthetic simulator turns an educational
tool into something handling clinical data about a real person, and the guard
is the thing standing between those two readings.

It is also the last backend task in Phase 3.

---

## 2. What was already there, and what was not

Three of the four pieces existed before this task and none of them were
connected to anything.

| Piece | State before |
|---|---|
| `patient_data_detected` at 422 | catalogued in `api/errors.py`, in `API_CONTRACT` §10, in `openapi.yaml`'s enum — **never raised by any code** |
| `input_blocked` event type | one of the eight in `domain/events.py`, with a validator refusing the event if the payload carries `text`, `content`, `message` or `input` — **never appended by any code** |
| The 422 on `POST /questions` | already declared in `openapi.yaml`: *"Too long, or real patient data detected"* |
| The modal, the copy, the `{state: "blocked"}` mapping | **already built by Yogesh in T-034** |

So the contract, the error code, the event type and the entire frontend were
waiting for a detector that did not exist. **No `openapi.yaml` change was
needed for the guard itself**, and Yogesh's client was the fixed contract: the
server had to return exactly `patient_data_detected` at 422 or his modal would
never fire.

---

## 3. The detector

`nidan/domain/guard.py` — pure, no I/O, no clock, no randomness, so it sits in
`domain/` and is tested without a database or a model call (`lint-imports`
confirms it reaches neither `infra/` nor `api/`).

`classify(text)` returns a `Detection` carrying **a reason code and nothing
else**, or `None`.

### 3.1 Deliberately conservative, and why that is not timidity

The two failure modes are not symmetrical:

- **A false block** discards the learner's typed question — `UX_SPEC` S-10's
  modal sends it nowhere — and teaches them the tool is broken. They lose real
  work for writing ordinary English.
- **A miss** leaves one real detail in a synthetic-patient exercise, which the
  P4 disclaimers also speak to.

So the guard errs towards letting text through, and three rules follow:

| Rule | Why |
|---|---|
| **A bare name does not block** | "Did Dr Mehta mention it?" is a learner talking about teaching, not pasting data. A name blocks only beside a structured identifier |
| **A bare date does not block** | "Did the pain start before Diwali?" is history taking. A date blocks only in date-of-birth shape, or labelled as one |
| **An age never blocks** | "A 54-year-old man" is how every case in the bank is written, ours included |

What does block is structure with no innocent reading in a question to a
synthetic patient: a **checksummed** NHS number, an explicitly labelled
hospital or record number, a full date of birth, an email address, a phone
number, a postcode.

Reasons are coarse on purpose — `identifier`, `date_of_birth`,
`contact_details`, `named_individual`. A reason precise enough to reconstruct
the input would defeat the point of not storing it.

### 3.2 The checksum is what makes the 10-digit rule safe

An NHS number is ten digits with a mod-11 check digit. Without the
arithmetic, a ten-digit run also matches an Indian mobile number and a phone
typed without spaces; the checksum rejects about ten in eleven of them.

**A test I wrote backwards.** I asserted `9999999999` would not block, on the
assumption it was obviously not a real number. It blocks, and correctly: the
weights sum to 486, 486 % 11 = 2, 11 − 2 = 9, which is the tenth digit. The
implementation was right and the test was wrong. It is now two tests — one
using `9434765918` (a real number's check digit changed, so it fails the sum)
and one pinning the all-nines case with the arithmetic written out, because it
looks like a false positive and is not.

### 3.3 A bug the false-positive list caught

The phone pattern made the country code optional in front of a mandatory
`0`-or-bracket group, so `+44 7700 900123` — the most ordinary form there is —
did not match. Rewritten as three alternatives (country code, parentheses,
trunk zero), each a positive signal on its own, which is also what keeps doses
("500 mg"), vitals ("132/84") and counts ("14 units") out.

### 3.4 Validated against the product's own language

40 strings that must pass, drawn from how the ten cases are written and the
kind of question the 16 pilot sessions contain, and 24 that must block. All 64
behave correctly. The pass list includes every shape that trips naive
patterns: `"Was the BP 132/84?"`, `"Did they give you 2.5 mg of
bisoprolol?"`, `"Did the ECG show ST elevation in II, III and aVF?"`,
`"Is there a history of HLA-B27 positivity?"`, `"ward 7"`, `"Last Tuesday"`.

---

## 4. The route

### 4.1 Where the check sits, and why there

Inside the repository scope, **after** the session is fetched and the
ownership check has run, and **before** the cap, the rate limit and the
gateway.

- **After ownership**: a 422 on a stranger's session would confirm that
  session exists. `API_CONTRACT` §2.7 calls that the same leak in a quieter
  form, so a stranger posting patient data still gets an identical 404.
- **Before the cap and the rate limit**: both of those are "not now", this one
  is "not ever". Neither consumes the question, so the order only decides
  which reason the learner sees, and P4 is the one that matters.
- **Before the gateway**: a blocked question must not cost a model call. The
  test for this patches in a *counting* stub and asserts zero calls rather
  than relying on the autouse `_no_real_llm` fixture — which would make the
  test pass with the guard removed. That exact mistake was made once in T-031.

### 4.2 The question is not consumed

No `question` event is appended. This is criterion 2, and it has teeth beyond
the 40-question cap: **`question_count` feeds the premature-closure detector**
(`P1: q < q_min`), so a blocked question logged as a question would inflate
the count and **suppress a flag the learner should have seen**. Same shape of
reasoning as `patient_unavailable` not consuming the question, for a different
reason.

`input_blocked` is a different event type, so it cannot affect either count.

### 4.3 The guard runs on the prototype too

`api/routes.py` got the same check, and that is not belt-and-braces.

`PRD` P4 does not exempt anonymous visitors, and **the prototype is the only
path they have**: every consultation there is a trial one, and all of `/v1`'s
consultation endpoints are `@require_auth`, so a trial cookie alone gets 401
(Yogesh raised this as HANDOFF V-10.3). Guarding only the signed-in path would
have left the most public surface — the one anyone can reach without an
account — as the only unguarded one.

---

## 5. The text is never stored, and that is tested by reading the database

`DATA_MODEL` §8.2: `input_blocked` records *"never the offending text"*.
Storing what was just refused would put real patient data into the table we
keep for ever, under the name of protecting it — the block would be worse than
no block at all.

Three layers now hold that:

1. `Detection` carries one field, and a reason outside the catalogue raises.
2. `domain/events.py` refuses the append if the payload holds `text`,
   `content`, `message` or `input` (this predates T-035).
3. `test_the_blocked_text_reaches_nothing` posts a record containing a name, a
   hospital number, a DOB and a phone number, then reads **every payload in
   the session back out of Postgres** and searches for each fragment. It does
   not inspect the one event it expects to find, so a future change that
   records the text somewhere else in the log — a context key, an audit note —
   fails this too.

The 422 response is checked the same way: it names the category, never the
characters that matched. An error that quotes the input back puts it in logs,
in browser history and in any client that renders `message`.

---

## 6. The schema-conformance test, and the four drifts it found

Folded in at Vraj's decision after Yogesh asked for it twice (HANDOFF V-10.1,
V-11). His case was that three contract drifts had happened in three
consecutive tasks, each passing CI here and failing only when a client was
generated from the types:

- **T-034** · `DiagnosisCreate` declared `required: [diagnosis]`; the handler
  reads `text`. A generated client got `diagnosis_empty` every time.
- **T-036** · the rating body declared `helpful`; the handler reads
  `was_helpful`.
- **T-036** · the `Feedback` response schema had drifted from both §6 and
  `conclusion.py`.

He was right about the cause. The CT tests guard what must be **absent** from
a response — that is their purpose, and `questions_remaining` and
`matched_topics` are what they catch. **Nothing checked that the shape we
declare is the shape we read**, so the contract could say anything at all
about a request body and the suite stayed green.

`tests/test_request_body_conformance.py` walks the AST of the `/v1` route
modules for the keys each handler reads off the JSON body and compares them
with the schema the contract attaches to that operation. Static on purpose: no
database, no app context, no network, so it runs in 0.2 s and cannot be
skipped when Docker is down — which is when a contract change is most likely
to be made in a hurry. It follows the idiom of
`test_the_case_adapter_supplies_every_key_the_domain_reads`, which walks the
AST for the same reason.

**It found four more drifts on its first run, three of them real:**

| Finding | Verdict |
|---|---|
| `POST /sessions/{id}/diagnosis` declares `confidence_post`, never read | **Real** — this is V-10.2, which Yogesh raised and left. Removed from the contract |
| `PATCH /me` reads `consent_version`, not declared | **Real, and consequential** — `consent_research: true` is refused without it, so a client generated from the contract **could never give research consent at all**. Declared |
| `POST /me` accepts seven fields the contract never mentioned | **Real** — `identity.py` validates both `POST` and `PATCH` against one `_WRITABLE` set, so a client could not set a display name at sign-up without a second PATCH. Declared |
| `PATCH /me` "declares six fields no handler reads" | **False positive, mine.** Fixed before committing — see below |

### 6.1 Two bugs in the test itself, found by distrusting its output

A test with false positives gets switched off, so both were fixed rather than
explained away.

1. **It silently skipped the busiest endpoint in the API.** Flask spells the
   parameter `<uuid:session_id>` and `openapi.yaml` spells the same one
   `{id}`, so matching on the name found nothing for
   `POST /sessions/{id}/questions`. Both sides are now reduced to a shape with
   the parameter names stripped, which is what they actually agree about. A
   guard test — `test_the_ast_walk_finds_the_routes` — now fails if the walk
   stops matching, because otherwise every assertion passes over an empty set
   and the file becomes decoration.
2. **It did not understand the whitelist idiom.** `identity.py` filters with
   `{k: v for k, v in body.items() if k in _WRITABLE}` and no literal
   `body.get("display_name")` appears anywhere, so the walk saw a handler
   reading nothing and reported six false positives on `PATCH /me` alone. It
   now resolves module-level string collections. That errs towards counting a
   field as read, which makes the "declared but unread" direction more lenient
   and never wrong in the direction that cries wolf.

### 6.2 On `confidence_post`

Removed rather than implemented. Storing it is not a one-line change — it
needs a column or an event-payload field, a migration, and a decision about
whether it belongs in the research export. A field a client can send and the
server silently discards is worse than no field, because it looks like it
works.

Confidence **calibration** — comparing `confidence_pre` on `SessionCreate`
against a post-diagnosis figure — is a real and well-evidenced teaching
signal, and `PRD` FR-3 already captures the "pre" half. If it is wanted it
deserves a task, not a silent key. That is the answer to V-10.2.

---

## 7. Verification

| Check | Result |
|---|---|
| `pytest` | see §7.1 |
| `ruff check .` | clean |
| `mypy nidan/domain --strict` | clean, 16 files |
| `lint-imports` | 2 kept, 0 broken — `domain/guard.py` reaches neither `infra/` nor `api/` |
| `npm run gen:api` + `check:api` | regenerated; `schema.ts` matches |
| `npm run typecheck`, `npm run lint` | clean |

`schema.ts` moved by 16 insertions and 1 deletion. Every insertion is an
**optional** field and the single deletion is `confidence_post`, which
Yogesh's client never sent — so T-034 and T-036 are unaffected.

### 7.1 A note on the environment, not the code

Test runs on this laptop were taking 3–9 minutes and one aborted with
`TimeoutError: [Errno 60] Operation timed out` **while importing a `.so`**.
That is not a test failure and not a code problem:

- the project sits on the Desktop, and **Desktop & Documents iCloud sync is
  on** (`~/Library/Mobile Documents/com~apple~CloudDocs/Desktop` exists);
- the disk is **96 % full — 21 GiB free of 460 GiB**, which is where macOS
  starts evicting synced file contents to the cloud;
- so reads of the 457 MB `web/node_modules` and of the venv have to be fetched
  back, intermittently blocking. Importing `tests/conftest.py` by hand took
  144 s cold and 0.5 s warm; `importlib.metadata.entry_points()` took 25 s
  cold and 0.00 s warm.

Nothing in the repository causes it and nothing in the repository can fix it.
Recorded here because the same symptoms will otherwise be read as a broken
test suite. See §8.

---

## 8. Found while verifying, and not fixed here

1. **The laptop's disk is 96 % full and the repo is inside iCloud Desktop
   sync.** Until that changes, the test suite will intermittently appear
   broken in ways that have nothing to do with the code. Moving the project
   off the Desktop would settle it; freeing space would reduce it. Not a code
   change, and not mine to make on someone's machine.
2. **The anonymous trial still cannot use `/v1`** (V-10.3). Every `/v1`
   consultation endpoint is `@require_auth` while `UX_SPEC` S-09/S-10 say
   "Auth: Both", so the web app is signed-in only and the prototype is what
   serves trials. T-035 guards both paths, so P4 holds either way — but this
   gap is not in `BUILD_PLAN` and needs an owner and a task.
3. **`API_CONTRACT` §4 still describes `GET /me` as returning an `allowance`
   object and `active_session_id`**, neither of which the implementation or
   `openapi.yaml` ever had (V-9). Not touched here; §4 should be corrected to
   match.
4. **The response side has no conformance check.** §6's test covers request
   bodies. The `Feedback` drift was a *response* schema, and the right place
   for that check is the route tests, where a real response already exists —
   not in the static walk.
5. **T-030 still has no build log**, so `STATUS.md` cannot count it honestly.
