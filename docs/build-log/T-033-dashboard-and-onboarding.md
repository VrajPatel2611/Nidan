# T-033 · Dashboard and onboarding

| | |
|---|---|
| **Task** | T-033, BUILD_PLAN Phase 3 |
| **Status** | 🟡 Built — **not yet seen by a signed-in account** (§6) |
| **Branch** | `feat/t-033-dashboard-onboarding` |
| **Estimated** | 3 days |
| **Specification** | `UX_SPEC` S-07, S-08 · `PRD` FR-2.6, FR-2.7, FR-10.2 |
| **Behaviour change** | `/welcome` is S-07's two-question onboarding and `/dashboard` is S-08 in all its states. `PATCH /me` gains `onboarded` and `GET /me` gains `allowance_resets_at` — the two API additions this needed. |

---

## 1 · Summary

```
web/src/lib/dashboard.ts                     S-08 as a pure function: state, greeting, streak, labels
web/src/app/(app)/dashboard/page.tsx         three reads in parallel → buildDashboard → view
web/src/app/(app)/dashboard/loading.tsx      S-08 "Loading": skeletons
web/src/app/(app)/actions.ts                 finish onboarding · start a case · abandon
web/src/components/app/                      AppHeader, DashboardView
web/src/components/onboarding/               S-07
web/src/app/welcome/page.tsx                 S-07, plus the POST /me retry S-22 needs
web/src/lib/api.ts                           + updateProfile, listSessions, getProgress, startSession, abandonSession
nidan/api/v1/identity.py                     + `onboarded` on PATCH /me, + `allowance_resets_at` on GET /me
nidan/infra/db/repositories/profiles.py      stamps onboarded_at once
openapi.yaml · web/src/api/schema.ts         both fields, regenerated in the same commit
tests/db/test_v1_reads.py                    6 tests for the two fields
web/src/lib/dashboard.test.ts                19 tests — every S-08 state and copy rule
web/src/components/app/screens.test.tsx      11 tests — S-07 and S-08 as rendered
```

**148 web tests** (36 new), **988 backend tests** (6 new). Also: the T-032
build log's `.docx`, which Y-20 noted had never been generated.

---

## 2 · Definition of done

| # | Criterion | Met by | Verified |
|---|---|---|---|
| 1 | All four dashboard states: empty, normal, limit reached, unfinished session | `buildDashboard` + `DashboardView` | one model test and one rendered test per state; all four looked at in a browser with sample data |
| 2 | Onboarding two steps, skippable | `Onboarding.tsx` · `finishOnboarding` | year asked only of student/intern/resident; Skip from either step; both end onboarding (`onboarded_at` stamped) |
| 3 | Allowance on the dashboard only, never in a consultation | `AppHeader` shows it only when passed `allowance` | tests for both; the component's docstring tells T-034 not to pass it |

---

## 3 · Decisions

### 3.1 Two API additions, agreed before they were written

The brief puts `nidan/api/` on Vraj's side; Yogesh chose to add them and hand
them over for review (handoff V-9).

- **`PATCH /me` `{"onboarded": true}`.** Nothing ever set `onboarded_at` — not
  `POST /me`, not `PATCH /me`, no trigger — so T-032's landing rule (§6.1.5:
  not onboarded → `/welcome`) would have sent every sign-in back to onboarding
  for ever. The server stamps it, `COALESCE(onboarded_at, now())`, the way it
  stamps `consent_at`: a caller who could choose the time could rewrite when
  someone joined. `false` is refused.
- **`GET /me` `allowance_resets_at`.** S-08's "Your next free case unlocks on
  {date}" needs it, and the server already computes it
  (`selection.next_month_start`, in the learner's timezone). A second copy of
  that arithmetic in TypeScript is how a reset comes to be a day out once a
  month — the exact bug `month_start`'s docstring warns about.

`API_CONTRACT` §4 describes a different shape again (`allowance.resets_at`,
`active_session_id`) that the implementation never had. The resume banner
does not need `active_session_id`: the active session is in `GET /sessions`.

### 3.2 S-08 is a pure function

`buildDashboard` takes the three API answers and a clock and returns
everything the screen shows. Every state in S-08's table is therefore a unit
test, not a click-through. The view renders what it is given.

### 3.3 The verdict labels are S-13's, and `anchored` never reaches the screen

`correct` "Correct diagnosis", `partial` "On the right track", `anchored`
"Worth reconsidering" in amber, `other` "Not quite". A rendered test scans the
dashboard's text for `UX_SPEC` §9's banned words.

### 3.4 Streak and greeting use the learner's timezone

The greeting is by local hour (S-08 copy rule) and the streak counts local
calendar days — a session at 01:30 IST is the 15th, not UTC's 14th. A day in
progress does not break a streak. Stated factually, never with urgency (U1).

### 3.5 Starting a case

"Start a case" posts `POST /sessions` — the server chooses the case
(`PRD` FR-3) — and goes to `/case/{id}/preview`, S-09, which is **T-034**.
The refusals the dashboard can explain become sentences: limit reached, a
consultation already open, and `no_cases_available`, which is what **every**
start returns today, because no case is published until a clinician approves
it. "Start my first case" on S-07 saves and then does the same.

### 3.6 What is not here

- **"Go unlimited — $X/month"** is rendered disabled: billing is T-041 and the
  price is not set. It is there so the limit state is complete.
- **Coverage per session** in the recent list (S-08's "75%"): `GET /sessions`
  does not carry it. S-14 (history) will need it too.

---

## 4 · Found along the way

- **The Skip button first cleared React state and then submitted** — but the
  browser builds the form data before React re-renders, so the old answer
  would have been saved. Skip now says what it skips (`skip-all`,
  `skip-year`) and the server drops it.
- **A button inside a link** for Resume: invalid HTML and confusing to screen
  readers. It navigates with the router instead.
- **`mean_coverage_last10` is already a percentage** (an average of
  `coverage_pct`). A first draft guessed at a 0–1 ratio and would have shown a
  learner at 0.8 % as 80 %.

---

## 5 · How to undo

1. `git revert` the T-033 commit
2. No migration: `onboarded_at` already existed and was simply never written

---

## 6 · Before this is called done

Same gate as T-032: a real account, signed in against the live project. Then:
complete onboarding once and skip it once (a second account), and see that
both land on the dashboard and stay there on the next sign-in. Starting a case
will answer "There are no cases available right now" until one is published.

---

## 7 · Verification

```bash
cd web && npm run check:api && npm run typecheck && npm run lint && npm test && npm run build
#   148 passed · 0 vulnerabilities · /dashboard and /welcome built
pytest -q                          # 988 passed
python validate_detectors.py       # 94.4%
```
