# ADR-0018 · Erasure by one permitted mutation on the event log

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-22 |
| **Deciders** | Vraj Patel, Yogesh Bagotia |
| **Supersedes** | — |

## Context

`API_CONTRACT` API-9 has been open since 3 November 2026, raised by T-030 slice 5 and marked as having a legal dimension. `DELETE /v1/me` returned 501.

**The specification contained an instruction the schema forbids.** `DATA_MODEL` §10.2 erases an account in one transaction, and one of its statements is:

```sql
UPDATE session_events
   SET payload = jsonb_set(payload, '{text}', '"[redacted]"')
 WHERE session_id IN (SELECT id FROM sessions WHERE user_id = :uid)
   AND type IN ('question','diagnosis');
```

Migration 010 applies `forbid_mutation()` to `session_events` as `BEFORE UPDATE OR DELETE`, with no condition and no `TO` clause — verified against the running database to refuse even the table owner. `session_events.session_id` is `ON DELETE CASCADE`, so deleting the session does not help: the cascade reaches the same trigger and aborts the transaction. There was no path, as privileged as you like, to removing the words a learner typed.

So three documents disagreed with each other and with the database. `UX_SPEC` S-20 prints "The questions you typed are permanently redacted" on the screen, above a box the user types `DELETE` into. `SECURITY_SPEC` L7 says erasure "redacts free text". `DATA_MODEL` §10.3 gives that text a 24-month retention and then "Redacted, structure kept". None of it could happen, and `ADR-0003` — the event log is the source of truth — is the reason why.

### Four facts found while settling it, which shaped the decision more than the choice of mechanism

**§10.2 redacted two event types and there are four.** `_SHAPES` in `domain/events.py` gives a learner-written `text` to `question`, `diagnosis` **and `early_diagnosis`**; `patient_reply` carries a model-written one generated from the learner's question, which can echo it back. §10.2 named the first and the second.

**§10.2 did not mention `feedback_texts` at all.** `PRD` P3 and `ADR-0004` require feedback to cite the learner's own questions — that is the product's second non-negotiable property. So their words sit verbatim in `feedback_texts.lines`, in a table with no append-only trigger, which the erasure never looked at. The hardest half of the problem was guarded by a database trigger; the easy half was simply missing.

**Nothing that needs reproducibility reads the free text.** This is the fact that collapsed the case for retention. §10.2 keeps `session_results` and `research_pid` "because published analyses must remain reproducible", and §11.7's research export is the query those analyses run — it selects `research_pid`, `coverage_pct`, verdicts and counts, and **no text column at all**. `scripts/build_golden.py` reads `sessions/*.json`, not the database. Redacting the prose costs the research nothing, so "keep it, for the research" was an argument for retaining data that the research does not use.

**§4 and S-20 already disagreed about time.** §4 specified `204`, which asserts the erasure finished inside the request. S-20 told the user "within 24 h" and promised a confirmation email. Three of the steps are outbound calls we do not own: the credential deletion (`ADR-0002` — Supabase owns `auth.users`), the payment provider, and that email.

## Decision

**Migration 033 replaces the unconditional trigger on `session_events` with one that permits exactly one state transition and refuses every other mutation, DELETE included.**

```
payload->'text'  →  '"[redacted]"'        and nothing else changes
```

A `BEFORE UPDATE` trigger sees `OLD` and `NEW`, so the predicate is checkable in the database: `id`, `session_id`, `seq`, `type` and `created_at` must be identical, `OLD.payload` must already have a `text` key, and `NEW.payload` must equal `jsonb_set(OLD.payload, '{text}', '"[redacted]"')` **exactly** — so no other key may be added, removed or altered in the same statement.

This is a specified exception, not a relaxation, and three properties follow from its shape:

- **It is enforced in the database, for every role including the owner.** The guarantee stays where `ADR-0003` put it rather than moving into application code a future caller can forget.
- **It is idempotent.** Redacting an already-redacted row satisfies the predicate and changes nothing, so a worker retry is safe.
- **It is self-announcing.** `"[redacted]"` is a value, not an absence. Replay still returns something defined, and anything reading the log can see that text was removed rather than silently behaving differently — which is what option (a) could not offer.

`audit_log` keeps `forbid_mutation()` unchanged. It records that an erasure happened, and granting it the same exception would let the record of an erasure be edited by the thing performing one.

Three consequential decisions ride with it:

**The erasure covers all four text-bearing event types and `feedback_texts`.** The repository's predicate is `payload ? 'text'`, not a list of type names, so an event type added later is covered the day it is added rather than the day someone remembers the file. `patient_reply` is included deliberately: a reply is generated from the learner's question and can quote it, so it is the one place a detail that slipped past `domain/guard.py` — which is conservative on purpose — could be reflected into storage.

**`DELETE /v1/me` returns 202, not 204.** The database half completes before the response: billing cancelled, profile anonymised and stamped `deleted_at`, every `text` redacted, feedback prose replaced, all in one transaction with the `audit_log` row that attests to it. The three external calls remain, so 202 means "your data is erased, the external cleanup follows" and the body carries `completes_within_hours`. S-20 was right about the time and §4 was the document out of step.

**A soft-deleted profile is invisible to every learner route.** `ADR-0002` means the user's token stays valid until the worker deletes the credential, so for up to 24 hours an erased account can still make authenticated requests. `ProfileRepository.get()` filters `deleted_at IS NULL` — one filter, every route, and the 404 they get is the same 404 as a profile that was never created, which `API_CONTRACT` §2.7 prefers to a status that distinguishes the two. `update()` and `touch_last_active()` are scoped the same way, and `ensure()` raises `AccountErased` → 409 `account_deleted` rather than resurrecting the row, because an erasure that a retried sign-up could undo is not an erasure.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **(a) Redact at read** | Leaves the text at rest indefinitely and calls it erasure. Article 17 is about the data, not the view of it, and a filter in a repository is one forgotten query away from being bypassed. It also puts the log's meaning in the application: two readers of the same event would legitimately disagree, which is the one thing `ADR-0003` buys by making the log the source of truth. |
| **(c) An offline job that disables the trigger** | Needs an owner-level credential in a worker — `nidan_service` is `NOLOGIN` and `BYPASSRLS` but does not own the table, so it cannot `DISABLE TRIGGER`. And `ALTER TABLE` takes an `ACCESS EXCLUSIVE` lock on the hottest table in the schema, stalling every live consultation, while the append-only guarantee is off for **every row and every role** for the duration. Switching the invariant off globally to erase one person is a worse trade than specifying one exception to it. |
| **(d) Retain the text and say so** | The cheapest option: no migration, no trigger change. Rejected on three counts. It withdraws a promise already printed on S-20, in the one place `UX_SPEC` calls "the ethical core of this screen". It retains free text indefinitely in exactly the place a real patient detail could have landed — `domain/guard.py` is deliberately conservative, so misses are expected, and `SECURITY_SPEC` §7 rests the whole regulatory position on "we hold no patient data". And its central argument turned out to be false: the research does not read the text (see Context). |
| **Move free text to a side table, referenced from the payload** | The textbook event-sourcing answer, and architecturally the cleanest: erasure becomes an ordinary `DELETE` from a mutable table and the log is never touched. Rejected on proportion, not principle. It changes the payload shape of four event types, `replay()`, `_SHAPES`, every test that reads `text`, and requires migrating the 16 backfilled pilot sessions — for an outcome this achieves with one trigger. Worth revisiting if the payload is ever restructured for another reason. |
| **Crypto-shredding — encrypt per user, destroy the key** | Renders the text unrecoverable without mutating a byte of the log, which is elegant. Rejected because it adds a key-management dependency to the critical path of every consultation, makes `session_events` unreadable for support and leakage review while the account is live, and rests on key destruction counting as erasure — defensible, and less settled than overwriting the data. |
| **Leave it as a 501** | The status quo, and honest while undecided. Rejected now because it is only honest as a temporary state: `PRD` FR-11 and S-20 make deletion a launch feature, `SECURITY_SPEC` §7 assumes GDPR applies, and an account a user cannot delete is a launch blocker that was being carried as an open question. |

## Consequences

+ API-9 is closed. `DELETE /v1/me` works, and `nidan/api/v1/contract.py`'s 501 list is down to Phase 4's three Stripe routes
+ `DATA_MODEL` §10.2 is corrected: four event types, not two, plus `feedback_texts`
+ `session_events` is append-only with one specified exception, and `tests/db/test_erasure.py::TestWhatTheTriggerStillRefuses` enumerates eight mutations it still refuses — the safety of this decision rests on that class, not on the erasure working
+ The erasure's own `audit_log` row is written in the same transaction, so it cannot exist unless the erasure committed
− **A redacted session can no longer be reassessed from its event log.** Topic extraction reads the text, so coverage is not recomputable for an erased learner. `session_results` holds the computed answer and §11.7 reads only that, so no analysis is affected — but the pilot's data-integrity check, which recomputed results from stored questions, could not be repeated for such a session
− **The erasure is not complete when the endpoint returns.** Three external steps need a worker, and until it exists the credential is not deleted, billing is cancelled only in our own table, and no confirmation email is sent. T-038 covers it, with API-10's export worker, and this is the one promise in S-20 the product cannot yet keep
− `research_pid` survives while `consent_research` becomes false, and §11.7 filters on consent — so re-running the export after an erasure will not reproduce a previously published dataset. "Reproducible" can only mean "the published snapshot stays interpretable", which argues for archiving each export rather than regenerating it. Recorded here; no task yet

## Not legal advice

This records a reading of Article 17 and a design that follows from it, taken by two engineering students. `SECURITY_SPEC` S-7 — privacy policy, terms, cookie notice — is open and needs someone qualified. The mechanism above is what makes the promise on S-20 **possible** to keep; whether the wording of that promise is sufficient is a question for that review.
