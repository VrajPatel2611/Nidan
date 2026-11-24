# T-040 · Leakage monitor

| | |
|---|---|
| **Phase** | 4 — Commercial readiness |
| **Owner** | Vraj |
| **Estimate** | 3 d |
| **Depends** | T-030 |
| **Spec** | `TECH_SPEC` §5.3 · `DATA_MODEL` §7.2, §11.7 |
| **Branch** | `feat/t-040-leakage-monitor` |
| **Completed** | 2026-11-24 |

---

## 1. What it is for

`TECH_SPEC` §5.3 called this "the most under-addressed risk in the project",
and the reason is Property 1 read backwards.

The patient's *"only reveal when directly asked"* rule is **prompt
engineering, which is soft**. If the model answers a question the learner
never asked, history-coverage measures the model's helpfulness instead of the
learner's thoroughness. Every number computed from that session is then a
number about something else — and nothing downstream says so. The pilot's
45.3 % → 79.7 % coverage result is the thing at stake: it is only a finding
about learners if the patient held its tongue.

§5.3 names three defences. Before this task, none of them existed.

**It had become more urgent than the plan knew.** Groq retired
`llama-3.3-70b-versatile` on 2026-08-16; the patient now runs on
`openai/gpt-oss-120b`. A model change invalidates the leakage tuning of every
persona, and nothing had re-measured them. **Leakage was unmeasured, not
known-good.** One of this task's jobs was retro-validating a switch that had
already happened.

---

## 2. What was already there, and what was not

| | |
|---|---|
| `leakage_flags` | **existed** — migration 015, matching §7.2 exactly. Zero rows, no repository, nothing wrote to it |
| A working heuristic | `nidan/web/admin/playtest/instrumentation.py` had one, labelled as a heuristic. Playtest-only, in memory, wrote nothing |
| §11.7's exclusion filter | in the spec's query. The query was **not implemented anywhere** |
| The dashboard's figures | `unreviewed_leakage=2` hardcoded in the route; `0.9%` "leakage rate" hardcoded in the template. Both invented |

So the shape of the work was not "build a detector". It was: promote the
heuristic into the runtime, give it a queue a person can act on, build the
export it protects, and point adversarial prompts at ten personas.

---

## 3. The detector

`nidan/domain/leakage.py`. Pure, deterministic, no I/O — so a flag can be
recomputed from the event log years later and come out the same (`ADR-0003`,
`ADR-0005`).

```python
def detect(*, reply, question, required_topics, asked_before=()) -> Leak | None
```

**Only required topics count.** A reply that volunteers something outside
`required_topics` costs nothing, because coverage is scored over the required
list and an unrequired topic cannot inflate it. Narrowing to the required set
is the definition of the measurement being affected, not a convenience.

**The rule is per-turn.** Revealed, and not asked for *here* — which is what
§7.2 says. Earlier questions decide the severity and nothing else: a patient
that keeps volunteering an answer is still volunteering it.

**It is deliberately sensitive, which is the exact opposite of
`domain/guard.py`.** That one is conservative because a false block discards
the learner's question and teaches them the tool is broken. Here a false flag
costs an administrator one click, while a miss costs the validity of every
measurement taken through that persona and nothing would ever reveal it. So
the rule is broad, the confirm/dismiss step is human, and **only
`confirmed = true` excludes a session**.

`topics_asked(events)` reads the questions themselves rather than
`patient_reply`'s stored `matched_topics`, so a lexicon change moves the
detector and the coverage score together instead of leaving flags frozen
against a lexicon nobody uses. It skips a question whose `text` is missing,
because migration 033's erasure rewrites that key to `"[redacted]"` and a
replay of an erased session must still run.

**Playtest now imports it rather than owning a copy.** A panel that disagrees
with the recorded flag is worse than no panel — an author would dismiss a
queue item the instrumentation never showed them. The keyword annotation stays
on top, because the domain detector returns topics and an author needs to see
what matched.

### The severity split, which §7.2 left undefined

Migration 015's CHECK allowed `low` and `high` from the start and nothing said
which was which.

| | |
|---|---|
| **`high`** | the learner never asked about the topic anywhere in the session. Coverage credits them for something they did not do, so the session's numbers are wrong |
| **`low`** | they had asked earlier, so coverage had credited it regardless and the patient merely repeated itself. The score is unaffected |

A mixed leak takes the worse severity rather than an average: one corrupted
topic corrupts the session's coverage figure.

Severity is **triage, not a verdict.** The queue sorts on it; §11.7 does not
read it at all.

---

## 4. Both question paths, for `PRD` P4's reason

Wired into `api/v1/consultation.py` **and** `api/routes.py`, exactly as
T-035's guard was. Every `/v1` consultation endpoint is `@require_auth`, so
the prototype is an anonymous visitor's only path — and §5.3 exempts nobody. A
persona that volunteers an answer invalidates a trial session's numbers just as
surely, and the adversarial suite cannot see a leak that only ever happens in
conversation.

**The record cannot cost the learner their reply.** `record()` holds its own
`begin_nested()` savepoint and returns `False` rather than raising. Without
one, a failing INSERT poisons the transaction in Postgres — so the question
and the reply appended moments earlier would roll back and the learner would
lose a reply they had already read. The failure is logged at warning level
rather than swallowed: a queue that is quietly short of items looks like a
persona that has stopped leaking, which is the one wrong conclusion this task
exists to prevent. The log line carries no session id, because logs outlive an
erasure.

**The response says nothing.** CT-2. A learner who could see a leak flag would
learn that the patient had just told them something they had not asked for —
a coverage hint by another name, and `PRD` U2 is why there are no hints.

---

## 5. Four things the criteria assumed and the codebase did not have

### 5.1 Criterion 3 had nothing to exclude from

"Confirmed leaks excluded from the research export" — and `DATA_MODEL` §11.7
was a query in a document. No code ran it. `scripts/backfill_pilot.py` writes
`research_pid`; nothing read it in that shape.

So confirming a flag would have had no observable effect, which makes a
criterion that reads as met and is not. `repositories/research.py` holds
§11.7's SQL **verbatim** as one constant, and `scripts/research_export.py`
writes it as CSV or JSON. Verified against the real database: the 16 pilot
sessions export, and `excluded_session_count()` reports zero.

Three details are deliberate. The columns are listed one by one rather than
`SELECT *`, so a future migration cannot widen the export by adding one.
`ServiceActor` only — not because RLS would leak, but because a **partial**
export is the dangerous one: it looks like the dataset and is one learner's
slice of it, and nothing about the file would say so. And `duration_seconds`
is absent, because the 16 backfilled sessions carry synthetic timestamps
(§9.3) and exporting nothing that invites a think-time calculation is simpler
than exporting it with a warning attached.

The script reports how many sessions a confirmed flag removed, because §5.3's
third defence is *disclosure* and that is the figure disclosure needs.

### 5.2 Criterion 4 contradicts T-002 criterion 1

"A case whose persona leaks a key fact fails the build" — but T-002 criterion
1 is that **no test makes a network call**, and extracting from a persona
requires calling the model.

So it is `validate_personas.py` at the repository root, with its own CI job,
following the pattern `validate_detectors.py` and `test_api.py` already set.
Eight fixed probes against each of the ten personas: two that ask nothing
(`greeting`, `open_floor`), one that asks for the diagnosis outright, two
jailbreaks, one asking it to echo its brief, one asking for everything, one
asking which test would prove it.

**What counts as a key fact needed deciding, and two obvious answers are
wrong.**

* `accepted_diagnoses` **is** the list — those are the strings
  `domain/assessment/clinical.py` marks a learner correct for, so a patient
  uttering one has handed over the answer.
* `partial_diagnoses` is **not**. It holds lay words like "heartburn" and
  "indigestion", and `contradictory_clues` *requires* the patient to say
  "burning" and "heartburn" when asked about pain character. Treating those as
  leaks would fail every well-written case.
* **The anchor is not a leak either.** "I think it's my heart" is
  `anchor_topic` doing its job; `PRD` P1's whole design is that the patient
  voices a plausible wrong worry. A suite that punished it would push authors
  to delete the trap.

Three checks, two of them fatal: naming the condition, quoting its own brief,
and volunteering a required topic (fatal only on the probes that ask nothing,
where there is nothing it could be answering).

**Exit 3 when a probe never reached the provider**, separate from exit 1. An
outage must not read as a clean bill of health.

The probes are a frozen tuple and `tests/test_validate_personas.py` asserts
it, because a suite whose inputs move cannot tell you whether a persona got
worse or the probes did. The CI job also runs **weekly**: this is the one
check whose result can change with no commit at all.

### 5.3 `nidan_admin` could list the queue and not act on it

Migration 023 grants it `SELECT ON ALL TABLES` plus INSERT/UPDATE on `cases`
and `case_versions` and INSERT on `clinical_reviews` and `audit_log`.
Resolving a flag is an UPDATE on `leakage_flags`, which was in none of those
lists.

Migration 034 adds it — **UPDATE only, never INSERT**. An administrator must
not be able to create a flag by hand: `confirmed = true` excludes a session
from the research export, so a hand-written flag is a way to drop a session
from the dataset without a detector ever having objected to it, which is the
one thing the queue exists to make visible. Flags are written by the
consultation path and reviewed by the console, and that asymmetry is the
control. DELETE is not granted either: a confirmed flag is the evidence for a
session's absence from the dataset, and deleting one would make that absence
unexplainable.

`nidan_reviewer` gets nothing. Which sessions count as research data is not a
clinical judgement.

### 5.4 RLS binds `nidan_admin` too, and the symptom was an empty screen

This one was found by a test, and it is the most instructive failure in the
task.

`own_sessions` is `FOR ALL USING (user_id = auth.uid())` **with no `TO`
clause**. `DATA_MODEL` §10.1 flags this explicitly — migration 025 exists to
work around the same thing on `profiles` — and it binds every role,
`nidan_admin` included. So the queue's join through `sessions` returned
nothing for an administrator, and `session_events`, where the flagged reply
lives, returned nothing either.

**It looked like an empty queue rather than a permission error**, which is
precisely the failure mode §10.1 is otherwise so careful about. An
administrator would have concluded there was no leakage.

Migration 034 adds two policies, and both are keyed on **the flag** rather
than on the role's seniority:

```sql
CREATE POLICY flagged_sessions_are_visible_to_admins ON sessions
  FOR SELECT TO nidan_admin
  USING (EXISTS (SELECT 1 FROM leakage_flags lf
                 WHERE lf.session_id = sessions.id));

CREATE POLICY flagged_replies_are_visible_to_admins ON session_events
  FOR SELECT TO nidan_admin
  USING (EXISTS (SELECT 1 FROM leakage_flags lf
                 WHERE lf.session_id = session_events.session_id
                   AND lf.event_seq = session_events.seq));
```

An administrator may read a session *because it carries a flag*, and may read
exactly the event the flag points at — matched on `session_id` **and** `seq`.
Not the learner's questions, not their diagnosis, not the rest of the
consultation. `TestHowNarrowMigration034Is` asserts all of that, including
that the learner's question remains invisible.

This is deliberately narrower than "administrators may read sessions". A-09
(users and support) will want more one day; it should ask for it then, in its
own migration, with its own reason.

**And the route had to change too.** The queue was written with
`repo_scope(current_actor())`, copied from the dashboard — and
`current_actor()` returns an ordinary `AuthenticatedUser` even for an
administrator, by design (`api/auth.py` says so). Both the queue and the
review now use `current_admin()`. The test that caught it is the one that
asserts the patient's words appear on the screen.

---

## 6. The queue screen

`/admin/leakage`, under AI Ops — `UX_SPEC` §12 has no leakage screen, and
A-08 is where the sidebar already promised "LLM Metrics & Leakage". T-043
builds the metrics half.

The screen states, in plain words, that **confirming excludes the whole
consultation from the research export** and that dismissing leaves it in. An
administrator should not have to learn that from a build log. It uses no bias
vocabulary (CT-5): the console is internal, but the habit is what keeps those
words out of learner-facing copy.

High severity sorts first, and **oldest first within a severity** — the point
of a queue is that a persona which started leaking gets noticed, and
newest-first buries the first occurrence under its own repetitions.

The patient's words are read live from `session_events` at `event_seq`,
**never copied onto the flag**. A copy would survive migration 033's erasure
— a learner's consultation preserved in a table the erasure never looks at,
which is the mistake `feedback_texts.lines` already cost us once. When the
account has been erased the screen says the reply is no longer available.

Reviewing is **audited** as `leakage_flag.reviewed`, with the verdict in
`reason` so it reads in the audit screen without expanding JSON. It removes a
session from the dataset a published result rests on, and the question anyone
will ask later is who decided it and when.

A second verdict gets **409**, not a silent overwrite: `review()`'s
`AND reviewed = false` is what makes two administrators opening the same queue
ordinary rather than a race.

### The dashboard's two invented numbers

`unreviewed_leakage=2` was a literal in the route and `0.9%` a literal in the
template. A hardcoded "needs attention" figure is worse than an empty panel:
it reads as a real backlog nobody can find, and as silence on the day there is
one. The count is now real, the attention line is **absent** when the queue is
empty rather than showing "0 unreviewed", and the stat card shows queue depth
— a leakage *rate* needs flags per reply over a window, which is T-043's
metrics page.

---

## 7. The trial scope widened by one INSERT, as a decision

`tests/db/test_anonymous_scope.py` holds an allow-list of what a visitor's
scope may reach, and it failed — which is exactly what it is for. The
docstring now records `leakage` alongside the `results` (T-016) and
`llm_calls` (T-031) entries, with the reason, so it arrived as a decision
rather than with a refactor.

`AnonymousLeakageRepository` carries the same `_OWNERSHIP` predicate as
events, feedback and results, so a session id that is not this visitor's
writes no row. The read methods it inherits carry no visitor filter because
the console is their only caller, and `review()` refuses anything but an
`AdminUser`, which a visitor is not. `TestTheTrialPath` checks all three
rather than asserting them in prose.

---

## 8. Verification

VERIFICATION_PLACEHOLDER

---

## 9. Found while building, not fixed here

1. **`BUILD_PLAN`'s screen references for Phase 4 were off by one.** T-043
   cited `UX_SPEC` A-07 for the cost dashboard, but A-07 is the topic lexicon
   and AI operations is A-08; T-044 cited A-05 and A-06 for the master-list
   and lexicon editors, but A-05 is the review queue and they are A-06 and
   A-07. Both are Yogesh's tasks and both would have been built against the
   wrong specification. The references are corrected in `BUILD_PLAN` with a
   note, and it is in his handoff inbox.

2. **The leakage *rate* does not exist yet.** The dashboard shows queue depth.
   A rate needs flags per reply over a window, which is T-043's metrics page
   (`TECH_SPEC` §10.1). §5.3's third defence — disclosure — currently has the
   excluded-session count from the export script and nothing finer.

3. **`leakage_flags` has no RLS, and that is consistent with §10.1** rather
   than an oversight: the ops tables (`llm_calls`, `leakage_flags`,
   `audit_log`) are deliberately outside the §10.1 ALTER list, and no learner
   route reads any of them. Noted because the table now holds per-session
   data, so the next person to look will wonder.

4. **The three Stripe 501s are the only ones left** in
   `api/v1/contract.py`. T-040 retired none of them and was never going to;
   recording it because the file is now one task away from being deletable.

5. **A machine-level I/O stall ran through the whole session.** macOS
   background indexing and on-device intelligence processes
   (`spotlightknowledged.updater`, `siriinferenced`, `aned`,
   `IntelligencePlatformComputeService`) saturated the disk: `mypy` died with
   `mmap(…) failed with errno=60`, a 39 MB local read ran at 12 MB/s, and two
   `test_validation_gate.py` tests timed out in a full run while passing in
   6.4 s alone. Nothing in the code was implicated, but it is worth knowing
   that the symptom is a hang with no output — the same shape as the
   `node_modules` bug T-035 recorded, and the second time this project has
   had to diagnose one.
