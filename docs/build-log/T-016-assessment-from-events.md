# T-016 · Assessment from events

| | |
|---|---|
| **Task** | T-016, BUILD_PLAN Phase 1 ⭐ |
| **Status** | ✅ Complete — 13 September 2026 |
| **Branch** | `feat/assessment-engine` |
| **Estimated** | 2 days |
| **Specification** | `TECH_SPEC` §4.4 · `DATA_MODEL` §6.3–6.4, §8.5 |
| **Behaviour change** | Concluding a consultation now writes a `session_results` row |

---

## 1 · Summary

```python
assess(events, case, engine) -> AssessmentResult
```

A pure function. Thresholds arrive as data from `engine_versions`; the id
travels with every stored result. The 16 pilot sessions are pinned in a
committed golden record, so any change that moves a result has to be seen.

```
domain/assessment/engine.py       assess() — pure, replayable
domain/assessment/thresholds.py   the constants, as data
infra/db/repositories/results.py  session_results + engine_versions
tests/golden/pilot_assessments.json   the pinned record
scripts/build_golden.py           how to regenerate it, and when not to
```

**21 new tests.** 502 pass, detector accuracy unchanged at 94.4 %.

---

## 2 · Definition of done

| # | Acceptance criterion | Met by |
|---|---|---|
| 1 | `assess(events, case, engine)` is a pure function | `domain/assessment/engine.py` — no clock, no randomness, no I/O |
| 2 | Thresholds read from `engine_versions`, not constants | `thresholds.py` + `test_the_engine_reads_its_thresholds_from_the_version_it_is_given` |
| 3 | `session_results` written with `engine_version_id` | `test_a_result_is_stored_with_the_engine_that_produced_it` |
| 4 | `bias_detail` includes counters | `DATA_MODEL` §8.5 shape, asserted in the property tests |
| 5 | Replaying the same events yields byte-identical results | `test_assessing_the_same_events_twice_is_byte_identical` |

---

## 3 · What was built

### 3.1 The pilot comparison, run before anything was written

The task's headline test is *"stored == recomputed over the 16 pilot
sessions"*, so that comparison was run first, against the existing detectors,
before a line of T-016 was written.

**Fifteen of sixteen reproduce exactly** — every score, every flag, including
every confirmation-bias result.

One does not:

```
P07_case_2   anchoring   published: detected, 0.71   →   today: not detected, 0.00
```

Case 2 is the **pulmonary embolism** case. The learner asked:

> *"You mentioned Dubai — did you catch a travel bug on the flight?"*

The pilot-era anchor keyword list contained `"travel bug"` — confirmed by
reading `cases.py` at commit `11a5256`. So that question counted as evidence of
anchoring: 5 of 7 questions "focused on chest infection", which is 0.71 and just
over the 0.60 threshold. Today the keyword is gone, the count is 4 of 7 = 0.571,
and anchoring is not flagged.

Case 2's contradictory clues include
`['flight', 'flew', 'long haul', 'long journey', 'immobile', …]` — the travel
history that points **at** pulmonary embolism. The anchor keyword overlapped a
contradictory clue, which is exactly what invariant **C-4** forbids and the same
class of defect that cost 14 % sensitivity in the confirmation detector.

**So the divergence is the fix working.** This is the one session in the
published pilot where a learner was marked down partly for asking the single
most diagnostically useful question available to them.

### 3.2 Two tests, because they check different things

A naive "stored == recomputed over all 16" would either fail forever or be
weakened until it proved nothing. So:

**`test_the_golden_record_still_matches`** — today's engine against a committed
record of its own output. Any change to a detector, a threshold or the lexicon
that moves a result fails here, and the failure names the session and prints
golden-versus-now. Regenerate deliberately with `python scripts/build_golden.py`
and commit the diff alongside the change that caused it.

**`test_the_engine_still_reproduces_the_published_pilot_results`** — today's
engine against the results *in the paper*. The one divergence is pinned by name,
with the reason in the docstring. If a sixteenth appears, it fails. If the known
one silently *heals*, it also fails — because a match would most likely mean the
C-4 keyword fix had been reverted.

A third test checks the *cause* rather than the symptom: `"travel bug"` must not
be an anchor keyword, and the travel history must still be a contradictory clue.
If either changes, the exception stops being justified and has to be re-argued.

### 3.3 Thresholds became data

Every constant left `bias.py`:

```python
if concentration > 0.60:                              # before
if concentration > thresholds.anchoring_concentration: # after
```

The refactor was verified as behaviour-preserving at each step: detector
accuracy stayed at 94.4 %, and the pilot comparison produced the same single
known divergence and no new ones.

`Thresholds.PILOT` remains as the fallback for callers with no database — the
detector unit tests, `validate_detectors.py`, the prototype. Anything that
*writes* a result passes a version loaded from the table, because
`ResultRepository.save` refuses a result whose `engine_version.id` is None.
That refusal is the enforcement of criterion 2; the fallback exists so that 69
existing call sites and the validation harness do not each need a database.

### 3.4 Counters, and why they are worth a column

`DATA_MODEL` §8.5 says it better than I can:

> **`counters` is the addition that makes replay verifiable.** Storing the
> intermediate values means a recomputation mismatch can be localised to a
> specific counter rather than merely observed as a different score.

Had they existed in the pilot, §3.1 would have been one line — `a: 5 → 4` —
instead of an afternoon reading git history.

### 3.5 Storing a result does not contradict T-013

T-013 deliberately stored **no** scores and recomputed the feedback screen from
the log, on the argument that a stored score is a cache of a conclusion and a
cache can disagree with its own log. There was a test asserting
`session_results` was empty.

Both positions hold, because they answer different questions:

| | |
|---|---|
| **Feedback screen** | Recomputed, always. What a learner reads is derived live |
| **`session_results`** | The durable analytical record — progress trends, research export, calibration — stamped with the engine that made it |

The cache-drift risk is handled rather than accepted: the golden test fails if a
recomputation stops matching, so a divergence is a finding. T-013's assertion was
rewritten, not deleted — it now reads *"nothing is stored without an engine
version"*, with the history in its docstring.

---

## 4 · Where we diverged from the specification

**`Thresholds.PILOT` is still a constant in code.** Criterion 2 says thresholds
come from `engine_versions`, and the write path enforces exactly that. The
fallback covers paths that produce no stored result, and `tests/db/test_seed.py`
compares the two **by value**, so it cannot drift from the row it stands in for.

**Rounding is centralised.** Scores are rounded once, in the engine, to the
three decimals `NUMERIC(4,3)` stores — so the number written to the database and
the number rendered on the page cannot disagree. Two code paths rounding
separately is the ordinary way "byte-identical" quietly stops being true.

**`session_results` is upserted, not inserted.** It is keyed on `session_id` and
it is *derived* data, unlike `session_events`, which is append-only precisely
because it is not. A recomputation under a new engine version must replace the
row rather than fail.

---

## 5 · Three tests that had stopped testing anything

All three were caught by this task's changes rather than by review.

**The threshold drift guard was grepping source.** `tests/db/test_seed.py`
asserted that `bias.py` still contained the literal string
`"concentration > 0.60"`. Its own docstring admitted the limitation: *"Until
T-016 makes the engine read these values, this test is the only thing holding
the two together."* It now compares `Thresholds.from_row(stored)` against
`PILOT` **by value** — which fails on any changed number, including one the
source formats differently.

**Both validation-gate tests had stopped degrading anything.** They copy the
repository, break anchoring rule A1, and assert the build fails. They broke it
by replacing `"if concentration > 0.60:"` in `bias.py` — a string that no longer
exists there. One of them asserted the fragment was present first and failed
loudly; **the other did not, and would have passed on an unmutated copy** — a
green build proving nothing. Both now mutate the threshold where it lives, which
is a better mutation point: it breaks the detector the way a bad calibration
would rather than the way a bad edit would.

---

## 6 · A false alarm worth recording

While probing the golden test — modifying a value, running the suite, restoring
the file — the suite kept failing after the restore. `thresholds.py` on disk read
`0.60`; the running code read `0.55`.

A stale `__pycache__` entry. Restoring a file by `cp` left bytecode that Python
did not invalidate, so a "failure" I spent time investigating was an artefact of
my own probe procedure rather than anything in the code. `find . -name
__pycache__ -exec rm -rf {} +` cleared it.

It does not affect CI, which checks out fresh. It is recorded because the
symptom — source and behaviour disagreeing — is alarming enough to send someone
looking in the wrong place for an hour.

---

## 7 · Verification

```
pytest                          502 passed        (was 487)
pytest tests/db -q --no-cov     149 passed        (was 140)
ruff check .                    All checks passed
mypy nidan/domain --strict      Success: no issues found in 14 source files
lint-imports                    2 contracts kept, 0 broken
python validate_detectors.py    PASS: 94.4%  (unchanged by the refactor)
```

| File | Tests | Defends |
|---|---|---|
| `tests/test_golden_assessment.py` | 6 | the pilot record, determinism, thresholds-as-data — **no database** |
| `tests/db/test_engine.py` | 8 | results stored with their engine, and as private as the session |

Both golden tests were probed by breaking what they guard: nudging the anchoring
threshold 0.60 → 0.55 fails the golden record with a per-session diff, and
restoring `"travel bug"` as an anchor keyword fails all three pilot tests.

---

## 8 · What this changes for you

**Concluding a consultation now writes a `session_results` row.** That is the
table every future progress screen, research export and calibration run reads.

**Changing a detector now has a visible cost.** If a change moves any of the 16
pilot results, CI fails and shows which. That is the point — but it means
"improving" a detector is now a conversation with the diff, which is exactly how
it should be for a published claim.

**Calibration is now a data operation.** Insert a new `engine_versions` row,
replay, compare. No code change, and no invalidation of history.

---

## 9 · Known debt left behind

**The pilot logs are synthesised.** The pilot predates the event log, so
`tests/pilot.py` translates each JSON summary into events. Topics come from the
stored `topics_covered` rather than re-extraction, deliberately: re-running
`extract_topics` would substitute today's lexicon and turn a detector test into
a lexicon test.

**Per-question topic attribution is not recoverable.** The summary format kept
only the aggregate, so every topic is attached to the first reply. The detectors
read the aggregate, so nothing is lost for them — but a future per-question
analysis cannot use these sixteen.

**`session_results` is written but not yet read.** T-017 onwards consumes it.

**`Thresholds.PILOT` duplicates the seeded row**, held honest by a test rather
than by construction. Removing it would mean a database for every detector unit
test.

---

## 10 · How to undo it

```bash
git revert <commit>
```

No migration. Stored `session_results` rows become orphaned data — harmless, and
still interpretable, because each one records the engine version that made it.
That is the entire argument for the column.

---

## 11 · Next

**T-017 · Free-tier allowance and case selection** (1.5 days) — a random
published case the learner has not completed, falling back to least-recent, and
an allowance that counts every session started this month including abandoned
ones. It depends on T-014 and is the first task to read `user_case_history`.

Phase 1 has three tasks left after it.
