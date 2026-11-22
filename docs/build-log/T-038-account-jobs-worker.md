# T-038 · Account jobs worker

| | |
|---|---|
| **Phase** | 3 — API and web app |
| **Owner** | Vraj |
| **Estimate** | 2 d |
| **Depends** | T-030 |
| **Spec** | `DATA_MODEL` §10.2 · `API_CONTRACT` §4 · `ADR-0018` · `UX_SPEC` S-20 |
| **Branch** | `feat/t-038-account-jobs-worker` |
| **Completed** | 2026-11-23 — closes Phase 3 |

---

## 1. What it is for

Both 202s in `/v1` were honest about the database and silent about everything
outside it.

`POST /me/export` wrote an `audit_log` row and returned an ETA; nothing built
the JSON and nothing sent it. `DELETE /me` did all of `DATA_MODEL` §10.2 —
billing cancelled in our own table, the profile anonymised, every
`payload->'text'` redacted, feedback prose replaced — and then left the
Supabase credential alive, the payment provider uncontacted and the
confirmation email `UX_SPEC` S-20 promises unsent.

Two of S-20's printed lines were therefore promises the product could not
keep, which is the sentence `ADR-0018`'s consequences used and the reason this
task existed at all.

**One task, not two.** API-9 and API-10 left the same shape twice: a 202 with
outbound calls behind it, where the work is "read a request out of an
append-only log, make calls we do not own, retry safely". Two workers would
have been two places for the retry logic to drift, and the drift would have
shown up as one of them losing a request.

---

## 2. Two acceptance criteria assumed things that do not exist

Both were found by picking the task up, not by reading it.

### There is no payment provider

Criterion 2 says "the payment provider cancelled". `grep -rln stripe nidan/`
returns `api/v1/contract.py` — its 501 list — and a key name in
`telemetry/redaction.py`. Nothing else. **Stripe is T-041, Phase 4.** The
criterion was written assuming a provider that arrives one phase later.

The resolution is `infra/billing.py`: a `BillingPort` with one implementation,
`NoProvider`, which returns `outcome="no_provider_configured"`. The worker
records that verbatim and marks the step done — because it *is* done. There is
nothing outside our database holding a subscription for this user, and §10.2's
transaction has already cancelled it in the one place a subscription exists.

The alternative was to record `erasure.billing_cancelled` with no detail, and
it is worth being explicit about why that is wrong rather than merely
imprecise. `audit_log` refuses UPDATE and survives the erasure, so it is the
only lasting record that the deletion happened and what it covered. A row
saying a payment provider was cancelled, written by a system with no payment
provider, is a false statement in the one place that must not contain one —
and it would read as true for ever, including to whoever eventually asks
whether an erased user was still being billed.

### There is no email infrastructure

Nothing in `nidan/infra/` sent mail. `grep -i "smtp\|sendgrid\|resend"` found
only unrelated hits in `tokens.py` and `telemetry/redaction.py`.

Decided with Vraj: a port (`infra/email/port.py`) with one adapter
(`infra/email/outbox.py`) that writes each message to
`logs/outbox/<timestamp>-<subject>-<id>/` as `message.json`, `body.txt` and
the attachment. The worker is complete, testable and inspectable; a real
provider needs an account, a verified sending domain and a key, none of which
exist and none of which the worker's correctness depends on.

**`for_name()` raises on an unknown adapter rather than falling back.** A
deployment that asked for a real provider and silently got a directory of
files would believe it had sent mail it had not sent, and the only evidence
would be the absence of complaints.

---

## 3. The queue is a difference between two sets, because the table refuses UPDATE

`audit_log` carries migration 002's unconditional `forbid_mutation` trigger,
and `ADR-0018` deliberately kept it while narrowing the one on
`session_events`: the record of an erasure must not be editable by the thing
performing one.

So **a job cannot be marked done.** There is no `status` column to flip and no
row to claim. A request is outstanding exactly while some step of it has no
completion row, and `AuditRepository.pending()` is that difference.

```
REQUEST_ACTIONS   profile.export_requested · profile.erased
STEPS             export_requested → export.built, export.emailed
                  erased          → erasure.email_sent,
                                    erasure.billing_cancelled,
                                    erasure.credential_deleted
FAILED_ACTION     job.step_failed   (metadata.step; counted as `attempts`)
```

The constraint turned out to be the feature. Criterion 3 ("both read their
work from `audit_log` … so a crash loses nothing") and criterion 4
("idempotent, because an external call that times out is indistinguishable
from one that failed") are both satisfied by the shape rather than by code:

* **A crash loses nothing** — the request row is already committed, and
  re-running re-derives the same work from the same rows.
* **A completed step is never re-attempted**, so a run that sent the email and
  then died does not send a second one.
* **A timeout resolves itself** — `delete_credential` treats Supabase's 404 as
  success, so a call that timed out *after* succeeding completes on the next
  run.

Two details that are not obvious:

**`count(DISTINCT action)`, not `count(*)`.** Nothing prevents two workers
running, because the rows cannot be claimed; with `count(*)` a duplicated
`erasure.email_sent` would make a three-step job look finished after two
steps. `test_a_duplicate_completion_row_does_not_finish_a_job` fails on the
`count(*)` version.

**The filter is in SQL, not in Python.** Filtering after `LIMIT` would be
subtly wrong and would get worse with time: completed requests are never
removed, and the oldest rows are the ones most likely to be finished, so they
would fill the limit and starve the new requests behind them. The bug would
appear as a worker that stops processing anything, months in, with nothing
failing.

---

## 4. Order is forced, not chosen

S-20 requires the confirmation to go "to the old address before it is
removed". That reads as a courtesy and is a constraint: the address lives in
`auth.users`, so after the credential is deleted there is nothing left to
fetch.

So `_email_erasure` runs before `_delete_credential`, and the worker **stops a
job at the first failure** rather than continuing to later steps. Deleting the
credential after a failed confirmation email would leave the user with no
account and no notice.

`test_the_email_is_sent_before_the_credential_is_deleted` asserts the call
order rather than reading the step list, because the step list is exactly what
someone changing this would edit.

**A scope per step, not per run.** One transaction for the whole run would
mean a failure on user B rolling back the completion row for user A's
already-sent email — and then sending it again on the next run. The unit of
work is the step, because the step is what has an irreversible effect outside
the database.

---

## 5. Where the email address comes from, and why it is an HTTP call

`profiles` has no email. The address is in `auth.users`, which Supabase owns.

A probe during this task confirmed `nidan_service` has no access at all:

```
nidan_service CANNOT select auth.users: ProgrammingError
grants on auth.users: nidan | INSERT, SELECT, UPDATE, DELETE, …
```

Only the table owner, and only locally — on Supabase no grant for our roles
exists. There is no SQL path. Both alternatives were worse:

* **Store it when the request is made.** `DELETE /me` would write the address
  into `audit_log.metadata`, and that table refuses UPDATE and survives the
  erasure — so the erasure would preserve, for ever, the one identifier it was
  asked to remove, in the record of having removed it.
* **Grant the service role SELECT on `auth.users`.** A migration doing that
  would work against migration 001's three-column stub and do nothing on
  Supabase. A local-only permission is a code path that is tested and never
  run.

So `identity_admin.fetch_email` asks the admin API, the worker uses the
address, and nothing stores it.

---

## 6. The `service_role` key

`identity_admin.py` is the only module in the codebase that reads
`SUPABASE_SERVICE_ROLE_KEY`. It bypasses RLS entirely, so every guarantee in
`ADR-0016` is void for any process holding it.

Three properties, by construction:

1. **Read from settings, never passed as an argument** — no caller can supply
   a different one.
2. **Never in a message, a log line or an audit row.** An exception string is
   logged, may reach Sentry, and on a `job.step_failed` row is written into
   `audit_log` — which refuses UPDATE and survives the erasure. A key in one
   would outlive the account it was used to delete. Asserted on **every**
   failure path, parametrised rather than sampled, and sent in headers so it
   cannot appear in a URL a proxy would keep.
3. **An absent key refuses.** `NotConfigured`, typed separately from
   `CredentialDeletionFailed` because the worker's responses differ: a failed
   call is retried, an absent key cannot succeed on a retry and must stop
   being tried after it has said so. It is **never** recorded as done —
   recording it would make S-20's "removed within 24 h" permanently and
   silently false.

Until this task the rule existed only as a comment in `web/.env.example`. It
is now `SECURITY_SPEC` §7.9, because "nobody has needed the key yet" was doing
more of the work than the rule was.

---

## 7. The export reads no detector column

`session_results` has `anchoring_detected`, `confirmation_bias_score`,
`bias_detail` and five more. **An export is learner-facing text** — a file
emailed to them — so `PRD` P1's ban applies exactly as it applies to a
response, and `bias_detail`'s own `reason` strings contain the forbidden words
verbatim.

`CLAUDE.md`'s rule is that a detector result reaches a learner through
`api/v1/reasoning.py` and nowhere else. `repositories/export.py` obeys it by
**not reading those columns at all**, which is a stronger property than
reading and filtering them.

The obvious alternative was to import `reasoning_json` here. That is what the
new import-linter contract forbids:

```
name = "the jobs worker must not import the web layer"
source_modules = ["nidan.jobs"]
forbidden_modules = ["nidan.api", "nidan.app"]
```

`import nidan.api.v1.reasoning` executes `api/v1/__init__.py`, which registers
every route on a Flask blueprint as an import side effect. A background job
formatting a number should not boot the API to do it — and with that closed
off, the answer became "do not read the detector columns", which is the better
answer. Verified the contract bites by adding the import: *1 broken*.

**`research_pid` is also absent**, deliberately. It is the key linking an
erased account to retained results; a copy in a file the learner keeps hands
whoever later reads that file the one value that re-identifies the anonymised
dataset.

**Every column is named** — no `SELECT *`, for the same reason `case_view.py`
names its fields. A column added by a later migration would otherwise appear
in an export with no decision and no review, and `session_results` gains
columns regularly.

---

## 8. Verification

| | |
|---|---|
| Tests | **1159 passing** (1103 before, 56 new) |
| New test files | `tests/db/test_jobs_worker.py` (23) · `tests/test_identity_admin.py` (20) · `tests/test_jobs_messages.py` (10) · `tests/test_outbox_is_not_committable.py` (3) |
| `ruff check .` | clean |
| `lint-imports` | 3 contracts kept |
| `mypy nidan/domain --strict` | clean |
| End to end | a real export request, run against the local database: 51 events, 19 KB of JSON, in the outbox |

**Three probes, by breaking the code.** Each was reverted after.

| Broken | Caught by |
|---|---|
| the transcript's `str`/`UUID` key (both halves) | `test_the_export_carries_every_event_the_learner_wrote` |
| the `break` that stops a job at the first failure | `test_a_later_step_does_not_run_after_an_earlier_one_failed` |
| `count(DISTINCT action)` → `count(action)` | `test_a_duplicate_completion_row_does_not_finish_a_job` |

The first probe is worth recording because **the first attempt at it did not
reproduce the bug**: reverting only the lookup left `str` compared with `str`,
because `_jsonable` had already stringified the id. Reverting both halves
reproduced it and the test failed. A probe that passes is not evidence of a
good test until you have checked the probe.

---

## 9. Two bugs in this task's own code

**The transcript was empty and nothing said so.** `_jsonable` turns each
session's `session_id` into a string on the way out, and `by_session` was
keyed by the `UUID` the events carry — so every lookup missed, every
transcript came back as `[]`, and the export serialised cleanly. 436 events
existed in the database; the export contained none of them. An empty list is a
valid transcript, so no assertion about shape would have failed. Found by
counting rather than by checking.

**`grep -c` exits 1 on a zero count**, which under `set -o pipefail` ended
`demo_up.sh` immediately *after* it printed a success line. Same family as the
alembic `|| true` bug in that script: a pipeline's status is the last
command's.

**And one false claim found by checking it.** `config.py`'s docstring said
`EMAIL_OUTBOX_DIR` was "under `logs/`, which `.gitignore` covers".
`.gitignore` had `*.log`, which covers `logs/api.log` and not
`logs/outbox/<id>/nidan-export.json`. A real pilot participant's export — 51
of their own questions and the patient's replies — was sitting in the working
tree, untracked and committable, and nothing failed. `logs/` is now ignored as
a directory, and `tests/test_outbox_is_not_committable.py` asserts it through
`git check-ignore` rather than by reading the file, because the question is
what git does and not what the file says.

---

## 10. Found while building, not fixed here

1. **The error message blamed the wrong thing.** `_admin()` is shared by
   `fetch_email` and `delete_credential`, and its `NotConfigured` message
   described the erasure's half-done state — so someone whose *export* had not
   been emailed was told their credential was still live. True about the wrong
   thing, in the error they would act on. Fixed in this task; recorded because
   the shape recurs whenever two callers share one error path.
2. **`SECURITY_SPEC` contradicted itself about the Supabase region.** Its
   §7.8 table said `⟨DECIDE⟩ — must be chosen deliberately`, while its own S-4
   checklist row had been struck through and closed since 28 Oct 2026
   (`ADR-0017`, Frankfurt). Fixed here.
3. **`SUPABASE_DEPLOYMENT.md` said "21 ordered migrations"** (it is 33) and
   its own Before-you-start table still said the region was undecided. Fixed
   in `609cdca`, which had been stranded — see 5 below.
4. **Nothing validates a *response* against its schema.** Yogesh's V-12
   reports five contract drifts across T-033–T-037; two were request bodies
   (now covered by `test_request_body_conformance.py`) and **three were
   response bodies, which nothing checks.** A missing request field gets a
   422; a renamed response field just reads as `undefined`, so the client is
   silently wrong. He has suggested a response twin — validate each
   implemented route's happy-path JSON against the operation's 2xx schema.
   **Not built here, and it is mine to decide.** It would have caught all
   three on the day.
5. **Two commits were stranded on a merged branch.** PR #50 was merged before
   `a80991c` (`scripts/demo_up.sh`) and `609cdca` were pushed to it, so
   neither reached `main`. Cherry-picked onto this branch. Worth knowing as a
   pattern: pushing to a branch after its PR is merged puts the commits
   nowhere.
6. **No step is claimable, so two concurrent workers would both pick up the
   same job.** One process is the design, and the per-step completion rows
   mean the damage from a double run is a duplicate email rather than a double
   erasure. If it ever needs to be exact, the lock belongs in its own table —
   not in `audit_log`, which cannot be updated.
7. **The persona pass on `gpt-oss-120b` is still outstanding.** Unrelated to
   this task; recorded because T-040 criterion 4 is the adversarial suite that
   would catch a persona leaking on the new model, and until then leakage is
   unmeasured rather than known-good.
