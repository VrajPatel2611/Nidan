# T-031 · LLM gateway hardening

| | |
|---|---|
| **Task** | T-031, BUILD_PLAN Phase 3 |
| **Status** | ✅ Complete — 4 November 2026 |
| **Branch** | `feat/t-031-gateway-accounting` |
| **Estimated** | 2 days |
| **Specification** | `TECH_SPEC` §5.1–5.2 · `ADR-0011` |
| **Behaviour change** | Every model call now writes an `llm_calls` row with tokens, cost, latency and attempt; a failing provider is retried with jittered backoff and then left alone for 30 s while the fallback is served; the provider is resolved from configuration rather than imported. No user-visible change — which is the point of all four. |

---

## 1 · Summary

```
nidan/infra/llm/pricing.py                 per-model token prices, dated
nidan/infra/llm/provider.py                the Provider protocol + for_name()
nidan/infra/llm/breaker.py                 the circuit breaker; process state
nidan/infra/llm/gateway.py                 returns LLMResult(text, call); retry + breaker
nidan/infra/db/repositories/llm.py         LlmCallRepository + the PURPOSES catalogue
nidan/infra/db/repositories/base.py        registered as db.llm_calls
nidan/infra/db/repositories/anonymous.py   the trial path records too (§3.4)
nidan/infra/feedback.py                    FeedbackResult.call; structured log
nidan/api/v1/consultation.py               records the patient turn
nidan/api/v1/conclusion.py                 records the feedback call
nidan/api/routes.py                        the prototype records too
nidan/web/admin/playtest/routes.py         records NOTHING, and says why (§3.3)
nidan/app.py                               /readyz reports open circuits
nidan/config.py                            + LLM_PROVIDER
tests/test_llm_accounting.py               24 tests — pricing, seam, routing, metrics
tests/test_circuit_breaker.py              20 tests — the state machine, through the gateway
tests/db/test_llm_calls.py                 13 tests — the row, the CHECK, the roles
tests/fakes/llm.py                         FakeLLM returns LLMResult; as_result()
tests/conftest.py                          the guard moved to the seam; breaker reset
```

**63 new tests.** 976 pass across the full suite, none skipped (913 before).

---

## 2 · Definition of done

| # | Acceptance criterion | Met by |
|---|---|---|
| 1 | Per-purpose model routing | `_model_for()` — `GROQ_MODEL_<PURPOSE>`, else the default. Untested until this task; `TestPerPurposeRouting` now proves the routed model reaches the provider **and** the row, not just the lookup |
| 2 | Exponential backoff with jitter; circuit breaker after N failures | `_backoff_seconds()` — 2/4/8 s ±25% · `breaker.py` — 3 consecutive failed calls, 30 s, one probe |
| 3 | Every call writes an `llm_calls` row | `LlmCallRepository`, called by four sites. Playtest is the deliberate exception (§3.3) |
| 4 | Provider swap is a config change | `Provider` protocol · `for_name(settings.LLM_PROVIDER)` · an unknown name raises |
| 5 | Failure on `/questions` returns 503 without consuming the question | Already true since T-030 slice 3; re-checked for the breaker's path, which bypasses the provider entirely |

| Check | Result |
|---|---|
| Breaker watched failing | ✅ `before_call` disabled → 2 red in `test_circuit_breaker.py` |
| Route-level criterion 5 watched failing | ✅ **passed for the wrong reason first** — see §4 |
| `ruff` · `mypy --strict` · `lint-imports` | clean · clean · 2 kept |
| `pytest` (Docker running, nothing skipped) | 976 passed |
| `validate_detectors.py` | PASS: 94.4 % |

---

## 3 · Decisions

### 3.1 The gateway cannot write its own row, and that is enforced

Criterion 3 reads "every call writes an `llm_calls` row", which sounds like
work for the gateway. It cannot: `pyproject.toml`'s import-linter contract
forbids `nidan.infra.llm` from importing `nidan.infra.db.engine` and **counts
indirect imports**, so every repository is out of reach too — all of them
reach `base`, which reaches `engine`. `lint-imports` fails the build on it.

So `call_llm` returns `LLMResult(text, call)` and the **caller** writes the row
inside a scope it already holds. `infra/feedback.py` is under the same
restriction and passes the metrics further up through `FeedbackResult.call`,
which is `None` on the rule-based fallback because nothing was billed.

The alternative was loosening the contract. It was not close: the contract is
what keeps a provider SDK out from behind every repository import, and the
cost of honouring it is one field on a dataclass.

### 3.2 Three consecutive failed *calls*, not attempts

A call that reaches the breaker has already slept through 2 s and 4 s of
backoff, so three failed calls is nine attempts and about eighteen seconds of
evidence. Counting attempts instead would open the breaker on the first call's
third try — a single blip, fully retryable, treated as an outage.

The breaker is keyed by `provider:model`, not by purpose. `TECH_SPEC` §5.2
routes feedback to a stronger model than the patient turn, so a global breaker
would silence working feedback because the patient model was rate-limited.

**It is process-local, and that is a decision.** A shared breaker needs a
store: Postgres puts a write on the path that is failing, and Redis is
infrastructure the product does not otherwise have. The cost is that each of
the 2 gunicorn workers trips its own, so the threshold is reached up to twice
before the provider is left alone. A provider outage outlasts that.

**It does not break `ADR-0003`.** "Session state is never held in the process"
is about a learner's consultation — replaying the event log must give the same
answer on any worker. This holds no session, no learner and no event, only how
a dependency is behaving right now. The lock is not decorative: the Dockerfile
runs `--workers 2 --threads 4`.

`CircuitOpen` is a plain `RuntimeError`, so **no caller changed**. `POST
/questions` already answers 503 `patient_unavailable` on `Exception` without
consuming the question, and `infra/feedback.py` already falls back to
rule-based prose — which is what `TECH_SPEC` §5.1 means by "serve the
fallback".

### 3.3 Playtest records nothing, and the old comment promised the opposite

T-022 left a comment saying `purpose="playtest"` would keep those calls out of
cost-per-session reporting "once T-031 starts logging by purpose". T-031
cannot, for two independent reasons that are both deliberate:

- Migration 015's CHECK allows five purposes. `playtest` is not one.
- Migration 024 withheld `llm_calls` from `nidan_reviewer` **on purpose** —
  "no reason for them to be able to read `audit_log`, `llm_calls` or anyone's
  billing".

Recording the row would mean widening a CHECK *and* granting the narrowest
role in the product INSERT on the billing table, to account for an author's
own turns against a draft. The call is still logged with its tokens, cost and
latency; only the row is absent. `repositories/llm.py` mirrors the five as
`PURPOSES` and raises `UnaccountablePurpose` rather than letting a
CheckViolation abort a transaction opened for work that mattered more.

### 3.4 The trial path records too, and a test made that a decision

`test_the_trial_scope_reaches_nothing_but_its_own_consultation` is an
allow-list of what an anonymous visitor can touch, and it failed — which is
what it is for. The unauthenticated, free, rate-limited path is the one whose
cost someone would watch, so leaving it out would make the dashboard
under-report precisely that traffic. Insert-only; the row holds tokens, cost
and latency and the visitor cannot read it back.

### 3.5 `pricing.py` is dated, not configured

`llm_calls.cost_usd` is `NOT NULL`, so a price is needed for every call. Prices
move, so a figure here carries `PRICES_CHECKED` — the date it was true. An
unknown model costs zero and the row is **still written**: the tokens and
latency are true, and a zero beside a real token count is visibly wrong in a
way a missing row is not. `logger.warning("llm.model_not_priced")` names it.

### 3.6 An unknown provider raises

A silent fallback to the default would run the whole product against a
provider nobody chose, and the only evidence would be the `provider` column in
`llm_calls`. One protocol, one implementation, and no second adapter — building
one now would be designing against an imagined API. What this delivers is the
seam: adding a provider is a new file and a dict entry.

### 3.7 `/readyz` reports open circuits and stays ready

`TECH_SPEC` §11 lists "circuit breaker open" among the five things that page,
so something has to say so. Reported, never required: failing readiness during
a provider outage would pull the worker out of the load balancer and take down
the nine-tenths of the product that needs no model at all.

### 3.8 `status` is `retried` when an earlier attempt failed

Migration 015 offers the value and nothing was using it. A column that only
ever reads `ok` hides the pattern worth watching — calls that succeed, but
only second time, every time.

### 3.9 Not in this task

- **No second provider.** The seam is real; the adapter is not needed.
- **No budget alerts or degradation to a cheaper model.** That is T-043, which
  depends on this task for its data.
- **No prompt versioning.** `TECH_SPEC` §5.1 lists it under the gateway's
  responsibilities; it belongs with the case editor's persona field and no
  acceptance criterion here asks for it.

---

## 4 · A test that passed for the wrong reason

`test_an_open_circuit_still_does_not_consume_the_question` asserted 503,
`patient_unavailable`, no question event and no `llm_calls` row. All four were
true **with the breaker disabled**, because the autouse no-network guard
produces the same 503 by a different route. The test proved the endpoint
degrades, not that the breaker caused it.

It now patches in a provider that *would* succeed and counts its calls, and
asserts the count is zero. Disabling `before_call` turns it red.

The same class of mistake cost this project a slice in T-030 (shape assertions
passing over an all-`None` patient), and it is the reason the build-log
convention asks for the test to be watched failing. Watching it fail is what
found this.

### Also changed

- `tests/test_no_network.py` asserted on `gateway._get_client`, which the
  provider seam removed. It failed loudly on the rename — exactly what that
  file exists for — and now names the seam. A second test drives the whole
  path through `call_llm` itself.
- `FakeLLM` returns the real `LLMResult`, with non-zero tokens. A zero-token
  call is the shape a broken accounting path produces, so a test asserting the
  row was written would pass against one.
- `tests/db/test_anonymous_scope.py` — see §3.4.
- `tests/conftest.py` resets the breaker around every test. It is process
  state and the suite is one process; three tests each provoking one failure
  would trip it and fail the fourth while it asserted something unrelated.

---

## 5 · How to undo

1. `git revert` the two T-031 commits
2. No migration was added — `llm_calls` has existed since migration 015 and
   was simply never written to. Nothing in the database to undo; existing rows
   are valid readings of calls that happened.

---

## 6 · Verification

```bash
ruff check . && mypy nidan/domain --strict && lint-imports
pytest -q                                   # 976 passed, Docker running
pytest tests/test_circuit_breaker.py -q     # 20 passed
pytest tests/test_llm_accounting.py -q      # 24 passed
pytest tests/db/test_llm_calls.py -q        # 13 passed
python validate_detectors.py                # PASS: 94.4% >= 94%
```

---

## 7 · Found while verifying, and not fixed here

`python test_api.py` fails: the configured default model
`llama-3.3-70b-versatile` returns **404 model_not_found** from the live Groq
API, and `client.models.list()` shows the key can reach eleven models, none of
them a Llama chat model. The patient cannot reply against this key today.

Nothing in the suite noticed, and nothing should have: criterion 1 of T-002 is
that no test makes a network call, so the suite never asks a real provider
whether the model exists. **The model choice is `TECH_SPEC` §5.2's decision —
"leakage rate first, then cost, then latency" — so it is Vraj's, not a
default this task should pick.** It also needs a `pricing.py` entry, or every
row records a zero cost. Raised separately; `LLM_PROVIDER` and
`GROQ_MODEL_<PURPOSE>` mean the fix is configuration, not code.
