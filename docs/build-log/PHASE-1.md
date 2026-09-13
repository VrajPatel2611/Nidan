# Phase 1 — Persistence and accounts

| | |
|---|---|
| **Tasks** | T-010 … T-018 (nine; there is no T-019) |
| **Status** | ✅ Complete — 11–13 September 2026 |
| **Effort** | 17 days estimated |
| **Tests** | 293 → **555** |
| **Goal** | *"Nothing is lost, everyone is who they say they are."* |

---

## 1 · What Phase 1 was for

Phase 0 made the prototype trustworthy to work on: a package, a test harness, CI,
a validation gate, containers, typed configuration, telemetry.

Phase 1 gave it a memory and an identity. At the start, a consultation lived in a
dictionary in one process and vanished on restart; there were no accounts, no
database, and no way to tell one learner from another. At the end there is a
21-migration schema, an enforced tenant boundary, an append-only event log, JWT
authentication, a free tier, a replayable assessment engine, and the pilot
inside the system rather than beside it.

| Task | | Tests after |
|---|---|---|
| T-010 | Schema and migrations | 330 |
| T-011 ⭐ | Seed content and `openapi.yaml` (sync point S-1) | 356 |
| T-012 | Repository layer and tenant scoping | 396 |
| T-013 ⭐ | Event-sourced session state | 433 |
| T-014 | Supabase Auth integration | 468 |
| T-015 | Anonymous trial sessions | 487 |
| T-016 ⭐ | Assessment from events | 502 |
| T-017 | Free-tier allowance and case selection | 540 |
| T-018 | Pilot data backfill | 555 |

---

## 2 · The defects Phase 1 found

Every one was found by a test or by CI, not by review.

| What | Found in | Why it mattered |
|---|---|---|
| **Four tables had RLS enabled with zero policies** — which in PostgreSQL denies everything, not allows everything | T-013 | `feedback_texts`, `subscriptions`, `user_progress` and `user_case_history` were completely unreachable by the application. It would have surfaced as T-014's mystery, one table at a time, with no error explaining any of them. Migration 021, plus a schema-wide guard |
| **`FLASK_SECRET_KEY` unset breaks sessions across workers** | T-013, by CI | Raising the worker count turned "sessions don't survive a restart" into "sessions don't work". Each gunicorn worker signed cookies with its own random key. Production now refuses to start without one |
| **`TRUNCATE … CASCADE` propagates outward** | T-011 | It took the five seeded cases with it via `cases.created_by`. A fixture that says "these tables hold only test data" is a claim about the current schema, and it stops being true without telling you |
| **`user_case_history` had no writer** | T-017 | Created in T-010, populated by nothing, and no task assigned to it — making "a case the user has not completed" unanswerable |
| **The threshold drift guard was grepping source** | T-016 | It asserted `bias.py` still contained the string `"concentration > 0.60"`. Now a value comparison |
| **A validation-gate test had stopped degrading anything** | T-016 | It broke rule A1 by replacing a string that no longer existed, and had no assertion that the target was present. It would have passed on an unmutated copy — a green build proving nothing |
| **Sequence collisions starved a thread** | T-013 | The retry was lockstep: every loser recomputed and retried immediately. Fixed with randomised backoff |

---

## 3 · What the phase taught

**Probe every guard by breaking what it guards.** Adopted in T-012 and used in
every task since. It has now caught three tests that could not fail, and — twice
— a *probe* that could not prove anything: T-017's mutation silently did nothing
because a quoted string did not match, and T-018's mutation worked while the
measurement (`grep -c "^FAILED"`) missed 14 errors. The probe needs checking as
carefully as the thing it probes.

**CI catches what one machine hides.** Three times now — `setuptools` in T-004,
`pip` in T-011, `FLASK_SECRET_KEY` in T-013 — always the same shape: *the
developer's environment supplies something the specification never required.*
Since T-013 every task is run in a Linux container with a fresh dependency
resolution and no `.env` before pushing.

**Two safety mechanisms can each be correct and still cancel each other.**
T-014's JWKS cache had to refetch immediately on an unknown key (or a rotation
is a ten-minute outage) *and* throttle refetches (or junk keys are a
denial-of-service). The first throttle defeated the rotation handling it was
written to coexist with. Only a test exercising both together said so.

**A stored number is meaningless without the version that produced it.** T-016
made thresholds data; T-018 proved why. The pilot's anchoring score of 0.71 and
today's 0.00 for the same consultation are both in the database and both correct,
because each carries its engine version.

---

## 4 · The one that is worth defending in a viva

T-016 replayed the 16 pilot sessions through the shipped engine. **Fifteen
reproduce exactly.** One does not, and the reason is traceable to a commit:

Case 2 is the pulmonary embolism case. A learner asked *"did you catch a travel
bug on the flight?"* — and the pilot-era anchor keyword list contained
`"travel bug"`, so the question that pointed **at** the correct diagnosis was
counted as evidence of anchoring. The keyword overlapped a contradictory clue,
which invariant C-4 forbids, and it was removed.

So the single divergence is the fix working: it is the one case in the published
pilot where a learner was marked down partly for asking the best question
available to them. Both numbers are now stored, each under its own engine
version, and a test fails if a sixteenth divergence appears **or if this one
silently heals** — because a match would most likely mean the fix had been
reverted.

---

## 5 · What Phase 1 deliberately did not do

- **No JSON consultation API.** `POST /v1/sessions` exists; asking questions and
  ordering investigations over JSON is T-030. A trial is started over `/v1` and
  continued in the prototype.
- **No admin console**, no case editor, no clinical review — all Phase 2.
- **The server-rendered prototype still exists**, unlimited and unauthenticated,
  as a development surface. It is deleted at T-030, and the free-tier and
  one-trial limits are enforced only on `/v1` until then. That is a
  surface-based exemption, not a role-based one, and it expires when the surface
  does.
- **The pilot import is not run in production.** Whether real participants' data
  belongs there is a privacy decision, taken separately.

---

## 6 · The state entering Phase 2

**The gate is T-023.** Four tasks in a row have hit the same wall:

The five seeded cases are **drafts**, on purpose — `DATA_MODEL` §9.2 says
publishing them without review would make the publication gate a formality. The
gate refuses to publish without an approving clinical review. Case selection
filters on `status = 'published'`. So selection correctly finds nothing, and
`no_cases_available` is the honest answer until a clinician can approve a case.

`BUILD_PLAN` §2.1 said this before any of it was built:

> **T-023 unblocks your two clinician reviewers.** Until it exists, only a
> programmer can look at a case, and content authoring — which is on its own
> critical path — cannot start in earnest.

Phase 2's goal is one sentence: *clinicians can review cases without reading
code.* It is 11 days, and `BUILD_PLAN` calls it the milestone that matters most.

**One decision remains open**: the Supabase region (`SECURITY_SPEC` S-4). It
blocks launch, not the next task — I said three times that it blocked T-014 and
T-015, and it did not.

---

*There is no Phase 0 summary. Phase 0's seven build logs were written as it
happened; a retrospective now would be reconstructed rather than observed, and
this document is only worth having because it was written the day the phase
closed.*
