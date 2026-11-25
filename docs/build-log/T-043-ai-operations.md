# T-043 · AI usage and cost dashboard

| | |
|---|---|
| **Task** | T-043, BUILD_PLAN Phase 4 |
| **Status** | ✅ Built: tests, a break-on-purpose check and a visual check. **No real month of data yet** (§7) |
| **Branch** | `feat/t-043-t-044-ai-ops-and-content` (with T-044) |
| **Estimated** | 2 days |
| **Specification** | `UX_SPEC` **A-08** (not A-07, see Y-28) · `TECH_SPEC` §5.1, §10.1 · `PRD` §10.3 |
| **Behaviour change** | `/admin/ai` (the old `/admin/ops` redirects). **Failed and fallback model calls now write `llm_calls` rows.** A new `LLM_MONTHLY_BUDGET_USD` setting degrades the gateway at 100 % |

---

## 1 · Summary

```
nidan/web/admin/routes.py · templates/admin/ops.html   A-08: six cards, budget bar, per-model table
nidan/infra/db/repositories/llm.py                     month_spend, usage(since), overview(since)
nidan/infra/db/repositories/leakage.py                 flagged_since: the leakage RATE's numerator
nidan/infra/budget.py                                  BudgetState, 60 s cached month spend, exhausted()
nidan/infra/llm/gateway.py                             set_budget_guard, degrade, failed_call, fallback_call
nidan/infra/llm/pricing.py                             cheapest_model()
nidan/infra/feedback.py · api/v1/consultation.py       record the fallback and failed rows
nidan/config.py · .env.example                         LLM_MONTHLY_BUDGET_USD
nidan/app.py                                           wires the budget check into the gateway
```

**24 new tests** (`tests/test_budget.py`, `tests/db/test_admin_ai_ops.py`). Three
existing tests rewritten to the new behaviour (§3.2). Full suite: 1336 passed.

---

## 2 · Definition of done

| # | Criterion | Met by | Verified |
|---|---|---|---|
| 1 | Spend today/month vs budget; cost per completed session | Window selector (today, 7 d, 30 d, this month); headline card; budget bar | tested against a hand-computed seeded month: **$0.0045** per completed session; 40-day-old spend excluded from every window and from the budget |
| 2 | Tokens, latency p50/p95, error and fallback rates by model | Per purpose and model table; error, fallback and leakage rate cards | tested: 14.3 % / 50.0 % / 25.0 % / p95 4.7 s; **broken on purpose**: letting failed rows into the latency and reply counts fails the test |
| 3 | Budget alert at 80 %; automatic degradation to cheapest model at 100 % | `infra/budget.py` + the gateway guard + amber banners | tested at 79.99 / 80 / 99.99 / 100 / 140 %; over budget, every purpose calls `openai/gpt-oss-20b`; a broken check **fails open**; the page and `exhausted()` agree on a real table |

---

## 3 · Decisions

### 3.1 Everything is computed from `llm_calls` and `leakage_flags`

Neither table has RLS, so `current_admin()` reads all of both with **no new
policy** and no `ServiceActor` in a route. That is the choice Y-31 asked to be
made deliberately. "Cost per completed session" is therefore not computed from
`sessions` (which an admin scope cannot count truthfully). It uses sessions
with a `feedback` row in the window, summing **every** call of each one,
patient turns included. With nothing completed it reads "—", not $0.

The **leakage rate** that T-040 left to this task is flags per answered patient
reply in the window, with confirmed flags shown beside it. `TECH_SPEC` §10.1's
alert lines are drawn on each card ($0.05, 6 s, 5 %, 2 %), and only a figure
over its line turns amber.

### 3.2 Failed and fallback calls are recorded, which reverses a T-031 decision

Asked before building. Vraj's Y-31 called the fallback rate "a decision, not an
implementation". Without this change the error rate and fallback rate would
always read 0 %, which is the same fabricated-number failure T-040 and Y-31
removed from the dashboard.

- **Failed:** after its retries, the gateway attaches an `LLMCall` with
  `status='failed'`, zero tokens and zero cost to the exception
  (`gateway.failed_call(e)`). The patient-turn handler records it in its own
  scope, best-effort. **It is not an event**, so the question is still not
  consumed.
- **Fallback:** rule-based feedback returns a `status='fallback'` call
  (`gateway.fallback_call`). It keeps the failed call's model and latency, or
  uses configuration and zeros when the breaker refused before calling.
  `conclusion.py` already recorded `feedback.call` when it was not None, so it
  did not change.

Migration 015's CHECK has always allowed both values, and nothing wrote them.
Both rows cost $0, so spend is unchanged. Three tests that pinned "no row"
(`test_v1_consultation`, `test_v1_conclusion`, `test_circuit_breaker`) now
pin "a $0 row with the right status, and no event". **This is the one change
in this branch Vraj should look at first** (V-item). Reverting it is three
call sites.

### 3.3 The budget is injected, not imported

`nidan.infra.llm` may not reach the database (import-linter), so `create_app`
calls `gateway.set_budget_guard(budget.exhausted)`. The month's spend is cached
for 60 s per process, so the check costs nothing per request. Like the
circuit breaker, this is process state about the platform, not about a
session, so `ADR-0003` is untouched. With no budget configured, `exhausted()`
returns without a query. Degradation picks `pricing.cheapest_model()` from the
price table, so it can never degrade to an unpriced model whose $0 rows would
make the budget look unspent and switch the degradation off again.

### 3.4 What the page says it cannot see

A footnote, not silence: Playtest records nothing (learner spend, not total
spend); the anonymous-trial prototype records no feedback calls; failed and
fallback rows start with this deploy.

---

## 4 · Found along the way

- **The A-01 dashboard linked to `/admin/ops`.** Repointed, and the old route
  301s to `/admin/ai`, so bookmarks still work.
- **The conversation sampler in A-08 is not in T-043's criteria** and needs a
  `sessions` policy for admins (which Y-28 said should be its own migration and
  conversation). Not built.

---

## 5 · How to undo

1. `git revert` the commit. No migration belongs to T-043. Unset
   `LLM_MONTHLY_BUDGET_USD` to switch the budget off without reverting.
2. To keep the page but drop §3.2 alone: restore `call=None` in
   `infra/feedback.py`'s fallback, remove `_record_failed_call` from
   `consultation.py`, and restore the three tests.

---

## 6 · Configuration

```
LLM_MONTHLY_BUDGET_USD=120     # unset = no budget, nothing alerts or degrades
```

The degraded model is the likelier persona leaker (`TECH_SPEC` §5.2), so set
the budget with headroom, and watch the leakage card when the banner is up.

---

## 7 · Before this is called done

A real month. Locally `llm_calls` has a handful of rows. The figures are
correct against a seeded table, but nobody has yet looked at the page after a
day of learners and asked whether it answers "is the business working?"

---

## 8 · Verification

```bash
pytest -q                                   # 1336 passed
pytest tests/test_budget.py tests/db/test_admin_ai_ops.py
ruff check . && lint-imports                # 3 contracts kept
```
