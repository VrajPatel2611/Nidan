# T-037 · History and progress

| | |
|---|---|
| **Task** | T-037, BUILD_PLAN Phase 3 — the last of Yogesh's run |
| **Status** | 🟡 Built — **not yet seen with a signed-in account's real history** (§6) |
| **Branch** | `feat/t-037-history-progress` |
| **Estimated** | 3 days |
| **Specification** | `UX_SPEC` S-14, S-15, S-16 · `API_CONTRACT` §7 |
| **Behaviour change** | `/history` (S-14), `/history/{id}` (S-15) and `/progress` (S-16). Also **fixes the T-033 dashboard**, which was built from a stale contract and would have listed no sessions against the real API (§4.1). |

---

## 1 · Summary

```
web/src/app/(app)/history/page.tsx          S-14 · 20 a page, by cursor
web/src/app/(app)/history/[id]/page.tsx     S-15 · S-13's layout, read-only
web/src/app/(app)/progress/page.tsx         S-16
web/src/components/app/HistoryList.tsx      the list, its empty state and pager
web/src/components/app/ProgressView.tsx     coverage trend (inline SVG), patterns, outcomes
web/src/lib/progress.ts                     sentences, chart geometry, segments — pure
web/src/components/feedback/FeedbackView.tsx  + readOnly
web/src/lib/dashboard.ts · dashboard page   read data[].session_id/verdict; streak from the API
web/src/lib/api.ts                          listSessions takes a cursor
openapi.yaml · web/src/api/schema.ts        SessionPage and Progress reconciled (§4.1)
```

**218 web tests** (21 new); 1103 backend tests.

---

## 2 · Definition of done

| # | Criterion | Met by | Verified |
|---|---|---|---|
| 1 | Paginated history; detail reuses the feedback layout read-only | `HistoryList` + `?cursor=`; `FeedbackView readOnly` | tested: order, links per status, pager, empty state; S-15 has no rating and no start button |
| 2 | Progress needs ≥ 3 sessions; empty state below that | `has_sufficient_data` from the API | tested at 0, 1, 2 — S-16's copy and no chart drawn |
| 3 | Decline shown neutrally, no alarm styling | one sentence shape and one style for every direction | tested ("up from 1" beside "down from 3"); **broken on purpose** — colouring a decline amber fails the test |

---

## 3 · Decisions

### 3.1 No chart library

The coverage trend is a 40-line inline SVG: the last ten points, a dashed
mean, three gridlines. `ADR-0006` asks for few dependencies, and a library
for one line chart and one stacked bar is the dependency churn it warns about.
Both carry an `aria-label` that states the numbers.

### 3.2 Decline reads like improvement

"Diagnostic focus flagged in 2 of your last 10 cases, down from 3." and
"History completeness flagged in 6 of your last 10 cases, up from 1." — same
shape, same colour (U1). Counts come from the API's rates times the real
window sizes, so with 14 completed the earlier window is 4, not 10. The API's
`direction` (`improving` when a pattern fires *less*) decides only the word
"about the same", never a colour.

### 3.3 S-15's date

S-15 asks for a "Viewed {date}" header. The only date a session carries is
when it took place, so that is the date shown.

### 3.4 The streak comes from the API now

`/progress` computes `current_streak_days` in the learner's timezone. The
dashboard uses it, falling back to its own count only when `/progress` could
not be read — one source for one fact.

---

## 4 · Found along the way

### 4.1 Two more stale schemas — and the dashboard they broke

`openapi.yaml` said `GET /sessions` returns `items[].{id, diagnosis_verdict}`
and a top-level `next_cursor`. The handler and `API_CONTRACT` §7 send
`data[].{session_id, verdict, coverage_pct, ended_at}` and a `pagination`
object. **T-033's dashboard was built from the schema**, so against the real
API it would have shown no recent sessions, no resume banner and no streak.
Its tests passed because they were written from the same schema.

`Progress` was the same: a `trends` map, against §7's streaks,
`has_sufficient_data`, `coverage_series`, `reasoning_trends` and
`verdict_distribution`.

Both reconciled to §7 and the code; types regenerated; the dashboard and its
tests now use the real shape (TypeScript found every call site once the
types were right). This makes **five** drifts across T-034, T-036 and T-037.
Vraj's new `test_request_body_conformance.py` (T-035) checks request bodies;
**response bodies are still unchecked** — passed to Vraj (V-12).

### 4.2 A clipped axis label

The "100%" label sat above its gridline and was cut off at the top edge.
Labels now sit under their line, except 0%.

### 4.3 A redirect that could loop

A 422 on `/history` redirected to `/history` — fine for a bad cursor, an
infinite loop if the first page ever failed that way. It now redirects only
when there is a cursor to drop.

---

## 5 · How to undo

1. `git revert` the T-037 commit. Note that this also reverts the dashboard
   fix in §4.1 — keep that part.
2. No migration

---

## 6 · Before this is called done

A signed-in account with real history. With Y-26's
`scripts/publish_for_demo.py` the local database now has ten published cases
(attributed to "Demo Fixture (not a clinician)", never counted towards the
launch gate), so this is the first task that can be checked end to end on
Yogesh's laptop: sign up, take three cases, and look at all three screens.

---

## 7 · Verification

```bash
cd web && npm run check:api && npm run typecheck && npm run lint && npm test && npm run build
#   218 passed · 0 vulnerabilities · /history, /history/[id], /progress built
pytest -q                          # 1103 passed
```
