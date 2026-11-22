# T-034 · Consultation screen

| | |
|---|---|
| **Task** | T-034, BUILD_PLAN Phase 3 |
| **Status** | 🟡 Built — **not yet used with a live case** (§6) |
| **Branch** | `feat/t-034-consultation` |
| **Estimated** | 6 days |
| **Specification** | `UX_SPEC` S-09, S-10, S-11, §4.1 · `PRD` FR-4, FR-6.5, FR-7.3 · API-6 |
| **Behaviour change** | `/case/{id}/preview` (S-09) and `/case/{id}` (S-10, with S-11's diagnosis modal). A learner can take a whole consultation in the web app: question the patient, examine, investigate, and give a diagnosis. |

---

## 1 · Summary

```
web/src/app/case/[id]/preview/page.tsx        S-09 · the case preview
web/src/app/case/[id]/page.tsx                S-10 · loads the session and the two menus
web/src/app/case/[id]/load.ts                 the active session, or the right redirect
web/src/app/case/actions.ts                   ask · order · diagnose — server actions
web/src/components/consultation/Consultation.tsx     S-10, every state
web/src/components/consultation/DiagnosisModal.tsx   S-11
web/src/components/consultation/SmallScreen.tsx      §4.1 · below 768 px
web/src/lib/consultation.ts                   grouping, name-only search, refusal → state
web/src/lib/api.ts                            + getSession, getCatalog, askQuestion, order, submitDiagnosis
web/src/components/ui/Button.tsx              + href — a link that looks like a button
web/src/components/ui/Interactive.tsx         Tabs can be controlled
openapi.yaml · web/src/api/schema.ts          DiagnosisCreate: `diagnosis` → `text` (§4.1)
```

**177 web tests** (29 new); 988 backend tests unchanged.

---

## 2 · Definition of done

| # | Criterion | Met by | Verified |
|---|---|---|---|
| 1 | Three-pane at lg, two-pane at md, blocking below 768 px | `consultation.module.css` | measured in a browser at 1280, 900 and 375 px: three columns; strip + drawer (opens to 520 px of 900); §4.1's message |
| 2 | States: idle, awaiting, error, cap reached, blocked, resuming | `Consultation.tsx` · `askFailure()` | a test per state, plus rate-limited and concluded |
| 3 | Failed reply keeps the typed question and offers retry | the draft is cleared only on success | tested: 503 → banner, text kept, Try again sends the same text |
| 4 | **None present:** question counter, coverage meter, suggestions, timer | nothing to build them from | scanned in the rendered text; **broken on purpose**: a `1/40` and a `1 of 40` counter each turn it red (§4.3) |
| 5 | Investigation search: name only, never ranked | `filterMenu()` | tested: order kept; a group name or a key matches nothing |
| 6 | Diagnosis modal holds no readiness hint | `DiagnosisModal` is given nothing about the consultation | tested: no digits, no "only asked", "haven't", "most students", "are you sure" |
| 7 | Keyboard accessible; conversation is aria-live | `role="log" aria-live="polite"`, chips in `<fieldset>`/`<legend>`, WAI-ARIA tabs, Enter/Shift+Enter, focus back to the input | tested |

`BUILD_PLAN`'s note asks a reviewer to check 4–6 explicitly. They are tests,
so a reviewer can read them: `components/consultation/consultation.test.tsx`.

---

## 3 · Decisions

### 3.1 The client never holds the token

S-10 is interactive, so it is a client component — but every write goes
through a server action (`app/case/actions.ts`) that reads the session cookie
and calls the API. The access token stays where T-032 put it, in an httpOnly
cookie the page's JavaScript cannot read.

### 3.2 The cap is a refusal, not a gauge (API-6, Y-19)

Nothing counts questions on screen. The 429 `question_limit_reached` disables
the input with S-10's note. On load, `capReached()` — a boolean, never the
number — disables it for a resumed session that had already hit 40, which is
Y-19's optional polish.

### 3.3 Signed in only, for now

`/case/*` is public to the proxy because S-10's auth is "both". But every
consultation endpoint in `/v1` is `@require_auth`; the anonymous trial can
start a session (`POST /v1/trial/sessions`) and not continue it. So an
anonymous visitor reaching `/case/{id}` is sent to log in. Handed to Vraj
(V-10).

### 3.4 Copy that is not in the spec

S-09's "You have seen this case before. Treat it as practice." — `PRD`
FR-3.2 says a repeated case must be marked and gives no words. And the empty
Ordered tab says "Results appear here as you examine and investigate."

### 3.5 Not here

- **Browser-back confirmation** ("Leave this consultation?") — no reliable
  way to intercept back in the App Router without a history hack, and
  progress is saved either way. Left for a follow-up.
- **S-12 · Assessment pending** — after a diagnosis the learner goes to
  `/case/{id}/feedback`, which is T-036.

---

## 4 · Found along the way

### 4.1 `openapi.yaml` named the diagnosis field wrongly

`DiagnosisCreate` said `{"diagnosis": …}`; `API_CONTRACT` §6, `conclusion.py`
and all 14 backend tests use `{"text": …}`. A client built from the generated
types was refused with `diagnosis_empty` every time. The file's own header says
it is the bug when the two disagree — corrected, types regenerated. Its
`confidence_post` is declared and never read; left for Vraj (V-10).

### 4.2 A button inside a link — again

The preview's "Begin consultation" was first written as `<Link><Button/></Link>`,
the invalid nesting T-033 removed from the dashboard. `Button` now takes
`href` and renders one element or the other; the dashboard's Resume uses it too.

### 4.3 The U2 tests had a hole, and so did T-033's

The counter check used `\b` around `\d+ of 40`. But `textContent` joins
elements without spaces — the page reads `…Send1/40Give diagnosis` — so word
boundaries fail on both sides and a counter between two buttons passed the
test. Found by breaking it on purpose; both ends fixed, and both forms of
counter now fail it. **T-033's banned-vocabulary scan had the same flaw**
("…2 days agoanchored" slipped past `\banchor`) and is fixed too.

### 4.4 `scrollTo` on an element

jsdom lacks it; `scrollTop = scrollHeight` works everywhere.

---

## 5 · How to undo

1. `git revert` the T-034 commit
2. No migration

---

## 6 · Before this is called done

Needs a published case, which needs a clinician's approval — none yet. Until
then `POST /sessions` answers `no_cases_available` and there is no live
session to open. When there is: one full consultation in the browser,
including a 503 from the model (stop the API mid-question) and a resume after
refresh. Same sign-in gate as T-032/T-033.

---

## 7 · Verification

```bash
cd web && npm run check:api && npm run typecheck && npm run lint && npm test && npm run build
#   177 passed · 0 vulnerabilities · /case/[id] and /case/[id]/preview built
pytest -q                          # 988 passed
```
