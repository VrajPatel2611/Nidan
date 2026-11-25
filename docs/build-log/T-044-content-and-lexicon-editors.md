# T-044 · Master list and lexicon editors

| | |
|---|---|
| **Task** | T-044, BUILD_PLAN Phase 4 |
| **Status** | ✅ Built: tests, a break-on-purpose check and a visual check. **Not yet used by a clinician** (§7) |
| **Branch** | `feat/t-043-t-044-ai-ops-and-content` (with T-043) |
| **Estimated** | 3 days |
| **Specification** | `UX_SPEC` **A-06, A-07** (not A-05/A-06, see Y-28) · `PRD` FR-12.7 · `DATA_MODEL` §5.3, §5.4 |
| **Behaviour change** | `/admin/content/{examinations,investigations}` add, edit and retire menu items. `/admin/content/lexicon` proposes lexicon changes and exports them. `python -m nidan.jobs lexicon` fills the dead-phrase counters |

---

## 1 · Summary

```
migrations/versions/036_content_editors.py     nidan_admin INSERT/UPDATE on master lists (no DELETE);
                                               nidan_service UPDATE on two topic_phrases columns
nidan/infra/db/repositories/catalog.py         admin_list (with "used by"), add/update/set_active
nidan/infra/db/repositories/lexicon.py         topics, phrases, dead counts, schema head, job reads/writes
nidan/jobs/lexicon.py · jobs/__main__.py       `python -m nidan.jobs lexicon` — the counts, never the text
nidan/web/admin/content/routes.py              A-06 and A-07
nidan/web/admin/content/lexicon_tools.py       matcher, proposal, checks, migration + topics.py export (pure)
nidan/web/templates/admin/content/*            list, form, lexicon, _tester, export
```

**40 new tests** across `tests/db/test_admin_content.py`, `tests/test_lexicon_tools.py` and
`tests/db/test_lexicon_export.py`. Full suite: 1336 passed.

---

## 2 · Definition of done

| # | Criterion | Met by | Verified |
|---|---|---|---|
| 1 | Examination and investigation CRUD; delete not offered, `is_active` only | A-06 list, add, edit, retire and restore; migration 036 grants no DELETE | tested: menu gains the item at the end; the key cannot be renamed; retiring drops it from the learner's menu and from ordering; **`DELETE` as `nidan_admin` is refused by Postgres**; retiring a used item without confirmation gets a 409 |
| 2 | Adding an investigation warns that no existing case returns an abnormal result | The amber notice on the add form, with the live case count | tested; seen in the browser |
| 3 | Lexicon editor with live match tester | Proposal-based editor (§3.1); the HTMX tester shows the matched phrases, COVERED or NOT COVERED, what the proposal changes, and other topics hit | tested; **the tester agrees with `extract_topics` on every pilot question**; **broken on purpose**: whole-word matching fails that test on the first pilot question |
| 4 | Dead-phrase report (no match in 90 days) | `python -m nidan.jobs lexicon` + per-topic marks + summary | tested: before the job runs, the page says it has no counts (rather than calling 677 phrases dead); after it, the matched phrase has its count and timestamp and the others are marked; the job stores no question text; **the job cannot UPDATE `phrase`** |

---

## 3 · Decisions

### 3.1 The lexicon editor exports. It does not save

Asked and decided with Yogesh before building. The engine scores from
`TOPIC_KEYWORDS` in `topics.py`, and `topic_lexicon`/`topic_phrases` are a
copy that `tests/db/test_seed.py` keeps in step. A phrase saved to the table
would not change scoring at all, and it would break the agreement the test
enforces. Making the engine read the database instead would change the core
assessment code, need `lexicon_version` to become real, and let a browser
re-score every replayed session (`ADR-0003`) with no review.

So the editor works on a **proposal** carried in hidden form fields. Nothing
is stored between requests, and the page says leaving discards it. Export
produces a complete Alembic revision (parent read from `alembic_version`)
**and** the whole new `TOPIC_KEYWORDS` entries, to commit together, with
`build_golden.py` named in both the page and the migration's docstring.
"Every new case needs two hand-written migrations" becomes one generated
file plus one paste.

`tests/db/test_lexicon_export.py` applies a generated migration to a real
database, checks the tables equal `apply(TOPIC_KEYWORDS, proposal)` (the
assertion `test_seed.py` will make once the paste lands), then downgrades and
checks the seed is back.

### 3.2 The master lists do save

`/v1` reads `examinations`/`investigations` at request time
(`CatalogRepository._menu`, `master_entry`), so A-06's "this appears on every
case immediately" is literally true, and an export step would add nothing.
The consequence is that a live database can now hold items `cases.py` does
not. That is expected: `cases.py` is the seed for a fresh database, and
`test_seed.py` checks the seed on a freshly migrated one. The prototype
(`api/routes.py`) reads `cases.py` and will not see new items, which is fine
because it is due to be retired.

### 3.3 Refusals that are sentences

A phrase under 3 characters is refused ("ear" is inside "heart"), a phrase
already in another topic is a warning, and a proposal that empties a topic
blocks the export, because a topic nobody can cover marks every learner as
having missed it. Reused master-list keys, including retired ones, are refused
with a sentence via a savepoint, so the form re-renders with the author's
input intact rather than a 500.

### 3.4 The counting job recomputes from scratch

Its own command, not a step of `run`, so a lexicon problem never makes an
export or erasure report failure. It is idempotent and crash-safe with no
bookkeeping, and an erased question stops counting on the next run.
Backfilled pilot events count towards `match_count` but not towards
`last_matched_at` (synthetic timestamps, `DATA_MODEL` §9.3). Its audit row
is written with `actor_id` NULL stated in the query, as the account jobs do.

---

## 4 · Found along the way

### 4.1 A flaky test in T-040's queue

`test_high_severity_sorts_first_then_oldest_first` failed once in the first
full run on this laptop and passed on rerun. All three flags in it are written
in one transaction, so they share `created_at` (`now()` is fixed per
transaction), and `LeakageRepository.queue()` had no tiebreak. Added
`f.event_seq`. Passed to Vraj (V-item).

### 4.2 What the tester shows on day one

"evening" alone matches `timing_pattern` and `symptom_timing_pattern`, so the
question *"does a rich evening dinner set it off?"* is credited for timing.
That is the engine's real behaviour, not a bug in the screen. It is the kind
of thing A-07 exists to make visible, and a candidate for the first
clinician-led lexicon edit.

---

## 5 · How to undo

1. `alembic downgrade 035` (revokes 036's grants)
2. `git revert` the commit. No data is touched: the lexicon editor never
   wrote any, and master-list rows added through A-06 stay (retire them first
   if wanted)

---

## 6 · What this does not do

- **No lexicon "edit live" path**, by design (§3.1).
- **No topic deletion or rename.** Cases reference topics in
  `required_topics`, so removal needs a case-editor change in the same commit,
  and that is a developer's job.
- **Embeddings** (`ADR-0013`): the tester will need a similarity column when
  they ship.

---

## 7 · Before this is called done

A clinician or author uses the lexicon editor on a real gap, for example the
"evening" finding in §4.2, and a developer commits the export. That is the
first time the round trip runs end to end outside a test.

---

## 8 · Verification

```bash
pytest -q                                  # 1336 passed
pytest tests/db/test_admin_content.py tests/test_lexicon_tools.py tests/db/test_lexicon_export.py
ruff check . && lint-imports && mypy nidan/domain --strict
python validate_detectors.py              # 94.4 %
python -m nidan.jobs lexicon              # "N question(s) read · M of 677 phrase(s) matched"
```
