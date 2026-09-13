# T-015 · Anonymous trial sessions

| | |
|---|---|
| **Task** | T-015, BUILD_PLAN Phase 1 |
| **Status** | ✅ Complete — 13 September 2026 |
| **Branch** | `feat/anonymous-trials` |
| **Estimated** | 1.5 days |
| **Specification** | `PRD` FR-2 · `DATA_MODEL` §6.1 |
| **Behaviour change** | `POST /v1/trial/sessions` exists; signing up claims the trial you took first |

---

## 1 · Summary

The join between the two halves. Since T-013 every consultation writes an
`anonymous_id`; since T-014 real accounts exist. T-015 is the moment a
stranger's work becomes theirs.

```
POST /v1/trial/sessions      → anonymous session + httpOnly cookie, one per browser
  … a complete case, including feedback …
POST /v1/me { anonymous_id } → creates the profile AND claims the session
```

```
api/trial.py                     the endpoint and the cookie
infra/db/repositories/trial.py   claiming — one UPDATE, for two good reasons
api/v1.py                        POST /me now claims
api/routes.py                    the prototype shares the same cookie
```

**21 new tests.** 487 pass.

---

## 2 · Definition of done

| # | Acceptance criterion | Met by |
|---|---|---|
| 1 | `POST /trial/sessions` creates a session with `anonymous_id`, sets httpOnly cookie | `test_starting_a_trial_creates_a_session_and_sets_an_httponly_cookie` |
| 2 | One trial per browser; second attempt → 409 `trial_already_used` | `test_a_second_trial_from_the_same_browser_is_refused` |
| 3 | `POST /me` with `anonymous_id` claims it within 30 days; 422 after | `test_a_trial_older_than_the_window_is_refused_with_its_own_code` |
| 4 | `owner_is_exclusive` never violated | `test_owner_is_exclusive_is_never_violated` |

---

## 3 · What was built

### 3.1 The claim is one UPDATE, and both reasons matter

Two constraints from `DATA_MODEL` §6.1 do the real work, and **neither applies
to a trial session until the moment it is claimed** — which is what makes them
easy to miss.

`owner_is_exclusive` requires exactly one owner, so `user_id` must be set and
`anonymous_id` cleared **in the same statement**. Written as two updates the
row is briefly invalid and the CHECK fires. Criterion 4 exists because two
updates is the natural way to write it.

`user_sequence_unique` is a **partial** index — `WHERE user_id IS NOT NULL` —
so it does not constrain a trial session at all. It begins applying at the
instant of claiming. Every trial is created with `sequence_index = 1`, so
claiming one into an account that already has a session numbered 1 violates it.
The claim renumbers in the same statement, and **per row**: one identifier can
carry several sessions, and giving them all `highest + 1` violates the index
just as surely as leaving them at 1.

```sql
WITH highest AS (SELECT COALESCE(max(sequence_index), 0) AS n
                 FROM sessions WHERE user_id = :uid),
     claimable AS (SELECT id, row_number() OVER (ORDER BY started_at) AS offset_in_batch
                   FROM sessions
                   WHERE anonymous_id = :aid AND user_id IS NULL
                     AND started_at > now() - make_interval(days => :days))
UPDATE sessions s
   SET user_id = :uid, anonymous_id = NULL,
       sequence_index = highest.n + claimable.offset_in_batch
  FROM claimable, highest WHERE s.id = claimable.id
RETURNING s.id
```

`WHERE user_id IS NULL` makes a double claim a no-op: two concurrent signups
with the same cookie is a race the second should lose quietly, not a 500.

### 3.2 Why claiming needs a `ServiceActor`

Neither existing scope can do it. The row is anonymous, so `own_sessions`
(`user_id = auth.uid()`) cannot see it as the *new* owner; and the trial scope
has no business writing a `user_id`. So claiming bypasses RLS — through the
mechanism T-012 built for exactly this, which demands a written reason and
makes every such bypass greppable.

`TrialRepository` refuses to be constructed with anything else.

### 3.3 Order of operations in `POST /me`

1. **Validate the trial** — before anything is written.
2. Create the profile.
3. Claim.

The order is not incidental. `sessions.user_id` references `profiles(id)`, so
claiming first violates the foreign key. But validating *after* creating the
profile would leave a user half-signed-up holding a 422 they cannot act on — so
the window check happens first, and a refused claim changes nothing. There is a
test asserting no profile row exists after a `trial_expired`.

### 3.4 Three outcomes, not two

`sessions_for` deliberately returns sessions **outside** the window rather than
filtering them out, because "there is nothing here" and "there is something,
but it is too old" are different facts about the user's own work:

| Situation | Answer |
|---|---|
| Unknown or already-claimed identifier | Carry on. A stale cookie must not block a signup |
| Sessions exist, all older than 30 days | `422 trial_expired` |
| Sessions exist, within the window | Claim them, return their ids |

`trial_expired` was already in the frozen error enum, unused. It means a client
can say *"that trial has expired"* rather than *"something was wrong with your
request"*.

The claimed ids come back in the response so the client can do what `UX_SPEC`
§6.1.5 requires: send the new user to that session's feedback page and **show
them what they saved**.

### 3.5 The cookie is a bearer credential

There is no `auth.uid()` on this path, so whoever holds the `anonymous_id` can
read that consultation. Its protection is that it is unguessable (uuid4, 122
bits) and unreadable by JavaScript — hence `httpOnly`, and `Secure` everywhere
but local http, where the browser would drop it silently and the trial would
appear broken for reasons no error explains.

It is **cleared** once claimed. Leaving it would tell the browser it is still
mid-trial, and the next `POST /trial/sessions` would answer 409 to somebody who
has already signed up.

---

## 4 · Where we diverged from the specification

**The one-trial limit is enforced on `/v1/trial/sessions` only, not on the
server-rendered prototype.** A decision taken deliberately with Vraj.

The rule protects revenue, not data: it is cookie-based, so clearing cookies
defeats it, which `PRD` FR-2.5 accepts by saying "per browser" rather than "per
person". The prototype is a development surface with a deletion date (T-030),
and enforcing it there would mean clearing cookies between every case while
authoring the five remaining ones — which `BUILD_PLAN` §11.1 calls the real
critical path — in exchange for protecting revenue that does not yet exist.

The limit lives in one method, `TrialRepository.has_used_trial`, so there is a
single definition of "has this browser used its trial" even though one surface
asks. `test_the_prototype_is_not_limited` records the decision as a test, so it
reads as a choice rather than an oversight.

**`POST /me` reads the cookie as well as the body.** The contract shows
`anonymous_id` in the body. Accepting the cookie too means the common case —
a browser that just took a trial — needs no client cooperation at all.

**The Supabase region still did not block this**, for the third task running.
Tokens come from the throwaway RSA authority built in T-014. The region blocks
launch, and it remains the one open decision in `SECURITY_SPEC` S-4.

---

## 5 · A guard that could not fail

All 19 tests passed on the first run, which is unusual enough to be worth
distrusting. So each was probed by breaking what it guards:

| Break | Tests that caught it |
|---|---|
| Same `sequence_index` for every claimed row | 1 |
| Forget to clear `anonymous_id` | 8 |
| **Remove the claim-window filter from the UPDATE** | **0** |

The third is the interesting one. Every window assertion went through
`POST /me`, which validates the window *before* calling the repository — so the
repository's own filter was dead as far as the tests were concerned. Deleting
it from the SQL broke nothing.

That filter is not redundant: it is the last line if a future caller reaches the
repository directly, which is exactly what `TrialRepository` exists to allow.
But an untested guard is indistinguishable from a missing one, and this is the
second time in three tasks that probing has found a test suite agreeing with
itself rather than with the code.

`test_the_repository_refuses_an_expired_trial_on_its_own` now covers it, and
re-running the same probe fails.

---

## 6 · What the existing tests caught

**The restart test was carrying half the browser.** Moving the visitor id out
of the Flask session cookie into `anonymous_id` broke
`test_a_consultation_survives_losing_the_process`, which copied only the
`session` cookie to the reborn client. Correctly: a browser that kept one and
lost the other would be a browser that had lost its trial. It now carries both.

**T-014's "claiming is not available yet" test failed**, as it should have —
that behaviour is what this task implements. Rewritten to assert the new
property: an unknown `anonymous_id` must not block a signup.

---

## 7 · Verification

```
pytest                          487 passed        (was 468)
pytest tests/db -q --no-cov     140 passed        (was 121)
ruff check .                    All checks passed
mypy nidan/domain --strict      Success: no issues found in 12 source files
lint-imports                    2 contracts kept, 0 broken
```

`tests/db/test_trial.py` — 19 tests covering all four criteria, the two
constraints directly, the double-claim race, and the guess-another-visitor's-id
case.

---

## 8 · What this changes for you

**A visitor can now finish a whole case and keep it.** That is `PRD` FR-2, the
largest avoidable drop-off in the funnel, closed.

**The prototype is unchanged to use** — still five cases, as often as you like.
It now shares the trial cookie, so a consultation taken there is claimable too.

**Phase 1's identity work is complete.** A learner can arrive, try a case, sign
up, and find their result in their history.

---

## 9 · Known debt left behind

**Case selection is still the transitional path.** `POST /trial/sessions`
resolves an unpublished case through `prototype_version_id`, exactly as
`routes.py` does, because the seeded cases are drafts pending clinical review
(T-023). T-017 owns real selection.

**The trial returns an empty transcript.** The full consultation API — posting
questions, ordering investigations over JSON — is T-030. Today a trial is
started over `/v1` and continued in the prototype.

**One trial per browser is per identifier.** Clearing cookies earns another.
Accepted by `PRD` FR-2.5; the alternative is fingerprinting, which is a worse
trade than the free case it saves.

**The claim window is enforced in two places** — the API before creating the
profile, and the UPDATE itself. Deliberate defence in depth, now tested on both
sides.

---

## 10 · How to undo it

```bash
git revert <commit>
```

No migration and no schema change. Sessions already claimed stay claimed; they
are ordinary owned sessions.

---

## 11 · Next

**T-016 · Assessment from events** ⭐ (2 days) — `assess(events, case, engine)`
as a pure function, thresholds read from `engine_versions` rather than
constants, and the golden-file test replaying all 16 pilot sessions to assert
stored results match recomputed ones.

That test is the one that matters most in the repository: it is the pilot's
data-integrity check, which matched all 16 sessions exactly, turned into
something CI runs on every push.
