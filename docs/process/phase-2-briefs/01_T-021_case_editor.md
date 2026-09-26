# T-021 · Case editor

**5 days · depends on T-020 and T-011 (both done) · Owner Y**

> Read `00_START_HERE.md` first. Start with:
> ```bash
> git checkout main && git pull origin main && git checkout -b feat/t-021-case-editor
> ```

---

# The backend is already there

The database would not let a case editor save anything until recently:
migration 020 lists the tables the application may write, and `cases` and
`case_versions` were deliberately not on it. That is now fixed on `main`, so
**you are not blocked and you do not need to ask anyone for anything.** Pull
`main` and it is all present.

```python
from nidan.api.auth import current_admin, require_admin
from nidan.infra.db.repositories import repo_scope

with repo_scope(current_admin()) as db:
    case_id    = db.cases.create_case(slug="chest-pain-trap", specialty="cardiology")
    version_id = db.cases.create_draft(case_id, content)
    row        = db.cases.for_editing(version_id)      # drafts included
    stamp      = db.cases.update_draft(version_id, content,
                                       expected_updated_at=row["updated_at"])
```

| Method | What it does |
|---|---|
| `db.cases.bank()` | every case with its latest version, **drafts included** — the case bank (A-02) |
| `db.cases.versions(case_id)` | one case's version history, newest first |
| `db.cases.for_editing(version_id)` | one version with full content, **whatever its status** |
| `db.cases.create_case(slug=..., specialty=...)` | a new case with no versions yet |
| `db.cases.create_draft(case_id, content)` | a new draft, numbered one past the highest |
| `db.cases.update_draft(version_id, content, expected_updated_at=...)` | overwrite a draft, returns the new `updated_at` |

## Three things about this that change how you write the screen

**Use `current_admin()`, not `current_actor()`, for anything that writes.**
They are different on purpose. `current_actor()` gives an ordinary user who
runs as the `nidan_app` database role, and the database denies that role every
content write. `current_admin()` gives an `AdminUser` running as `nidan_admin`,
the only role permitted to author. Read-only admin screens can keep using
`current_actor()`. Both require `@require_admin` on the route.

If you forget, you get a clear Python error naming the requirement, not a
mystery — that was deliberate.

**Editing a published version is just `create_draft` again.** There is no
separate "fork" call. Load the published version with `for_editing`, let the
user edit, and call `create_draft(case_id, edited_content)`. It numbers itself
and the published row is never touched. That is what makes the banner in
`UX_SPEC` §12.4 true — *"Published content is read-only. Saving creates draft
v3."*

**Concurrency is handled by a token you must pass back.** `for_editing`
returns `updated_at`. Keep it in a hidden field, send it back with the save,
and pass it as `expected_updated_at`. If someone else saved in the meantime you
get a `ConcurrentEdit` exception, and **that** is when you show the *"This
version was changed by {name} 2 minutes ago `[ Reload ]`"* banner.

```python
from nidan.infra.db.repositories.cases import ConcurrentEdit, ContentInvariantViolation
```

Catch both. `ContentInvariantViolation` is C-4 (below) or a missing content
field; its message names the problem and is safe to show.

---

# What this screen is

`/admin/cases/{id}/versions/{v}` — the screen that lets a clinician own the
clinical content without reading Python.

A case is not a row. It is a JSON document in `case_versions.content`, about
forty fields including two big dictionaries (27 examinations, 86
investigations). Your job is to turn that document into a form a doctor can
use, and to stop them saving it in a state that would quietly ruin the research.

---

# Reading, in order

1. `docs/spec/UX_SPEC.md` §12.4 — the screen, with an ASCII drawing of it
2. `docs/spec/DATA_MODEL.md` §8.1 — the exact JSON shape and invariants C-1…C-7
3. `docs/spec/BUILD_PLAN.md` — the T-021 block, five acceptance criteria
4. `docs/spec/UX_SPEC.md` §12.3 — the case bank, the list this screen opens from

Roughly 1 500 words. Read them properly; this is the most detailed screen in
the console.

---

# The acceptance criteria, in full

From `BUILD_PLAN`:

1. Sectioned form: patient, truth, trap, history, clues, exams, investigations, persona
2. Editing a published version creates a new draft; published content immutable
3. Live validation of C-1…C-7; **save is blocked on C-4** with the overlapping terms named
4. Unsaved-changes guard on navigate away
5. Token counter on the persona prompt

Criterion 3 is the one this whole task exists for.

---

# The sections

Eight, in a left-hand nav, content on the right. Everything maps to
`case_versions.content` (`DATA_MODEL` §8.1).

| Section | Fields |
|---|---|
| **Patient** | name, age, sex, presenting complaint, intro, opening line |
| **Truth** | correct diagnosis, `accepted_diagnoses[]`, `partial_diagnoses[]` |
| **The trap** | `anchor_topic`, `anchor_keywords[]`, `alternative_topics[]` |
| **History** | `required_topics[]` (multi-select from `topic_lexicon`), `minimum_questions` |
| **Clues** | `contradictory_clues[][]` — a list of tag-lists |
| **Examination** | all 27 from the `examinations` table — mark key, write the finding (blank = normal) |
| **Tests** | all 86 from the `investigations` table — category and result |
| **Persona** | `system_prompt`, with a live token counter |

The keyword and clue fields are **tag inputs**, not comma-separated text boxes.
Each term is a chip with an ✕. That matters for validation — you need to be
able to point at one term and say *this one is the problem*.

The three master lists come from the database, not a hard-coded list:
`examinations`, `investigations`, `topic_lexicon` (migration
`005_content_master.py`).

---

# The validation, which is the actual point of this task

The left sidebar shows all seven invariants live as the user types.

## C-4 — the one that blocks saving

> `anchor_keywords` ∩ (any `contradictory_clues` entry) = ∅

In plain terms: **a keyword that means "the learner is chasing the trap" must
never also mean "the learner is exploring the evidence against the trap."**

This is not theoretical. In the pilot, case 1 had `"heart"` as an anchor keyword
while `"heartburn"` appeared in a contradictory clue. Every learner who asked
about heartburn was scored as if they were anchoring on cardiac disease. It cost
**14 % sensitivity** in the confirmation-bias detector, and it was found by
accident, months later.

**Your screen is the structural fix for that entire class of bug.**

When C-4 is violated:

- Save is **disabled** — not a warning, not a confirm dialog. Disabled.
- A conflict panel names the exact term and where it collides:

```
⚠ Conflict with contradictory clues
"heart" also appears in clue set 4. A learner asking about the trap
would be counted as exploring the evidence against it.
[ Remove from anchor ]   [ Remove from clue set 4 ]
```

- Both buttons work with one click.

Note that `"heart"` vs `"heartburn"` is a **substring** collision, not an exact
match. A set intersection would let it through, which is exactly how the
original bug survived.

### Reuse the backend's check so the two cannot disagree

```python
from nidan.infra.db.repositories.cases import c4_collisions

collisions = c4_collisions(content)   # list of strings, empty when clean
```

That function shares `clue_keywords` with the detector itself, so the form, the
repository and the scoring engine all agree on what a clue's keywords are.

**The repository also refuses a C-4 violation outright** — a save that slips
past your form is rejected by the backend with the colliding terms named.
**That does not make your validation optional.** The backend refusal is a flat
error after the fact; `UX_SPEC` §12.4 wants Save disabled with the conflict
panel and the one-click fixes, live as the user types. Yours is the experience,
the backend's is the guarantee. Build both.

## The other six

| Invariant | Rule | Behaviour |
|---|---|---|
| C-1 | every `examination` key exists in `examinations.key` | warn |
| C-2 | every `investigations` key exists in `investigations.key` | warn |
| C-3 | every `required_topics` entry exists in `topic_lexicon.topic_key` | warn |
| **C-4** | anchor ∩ clues = ∅ | **blocks save** |
| C-5 | `accepted_diagnoses` length ≥ 2 | blocks **publish**, not save |
| C-6 | `contradictory_clues` length ≥ 4 | blocks **publish**, not save |
| C-7 | ≥ 1 investigation with `category: "key"` | blocks **publish**, not save |

The split is deliberate: **a draft is allowed to be incomplete.** Someone
halfway through writing a case has one accepted diagnosis and two clue sets, and
blocking their save would make the editor unusable. C-4 is different because a
C-4 violation is not incompleteness — it is a case that will produce wrong
numbers.

---

# Draft and published

| Situation | Behaviour |
|---|---|
| Draft, valid | Save enabled |
| Draft, C-4 violated | Save disabled, conflict panel shown |
| Opening a **published** version | Banner: *"Published content is read-only. Saving creates draft v3."* |
| Unsaved changes, user navigates away | Confirmation guard |
| Someone else saved while you were editing | *"This version was changed by {name} 2 minutes ago. `[ Reload ]`"* |

`update_draft` refuses a published version with a `ValueError` whose message
says "immutable", and refuses a stale `expected_updated_at` with
`ConcurrentEdit`. Both are yours to catch and turn into the banners above.

The database also has a unique index `one_published_version_per_case` — only one
version of a case can be published at a time. You do not enforce that; just do
not be surprised by the error if it fires.

---

# Files

### You write

```
nidan/web/admin/cases/__init__.py
nidan/web/admin/cases/routes.py
nidan/web/templates/admin/cases/editor.html
nidan/web/templates/admin/cases/_section_*.html      (one per section)
nidan/web/templates/admin/cases/_validation.html     (the sidebar panel)
nidan/web/static/admin/case_editor.js                (tag inputs, token counter)
tests/test_admin_case_editor.py
docs/build-log/T-021-case-editor.md
```

You will also extend `nidan/web/admin/routes.py` and
`nidan/web/templates/admin/cases.html`, both already yours from T-020.

### You must not touch

```
migrations/**                        ← the grant you need is already there
nidan/infra/db/repositories/cases.py ← call its methods, do not add to it
nidan/domain/**
nidan/api/**                         ← current_admin() is already there too
```

---

# How to build it — a suggested order

**Day 1 · Routes and shell.** `/admin/cases/{id}/versions/{v}` loads a case
through `db.cases.for_editing(version_id)` and renders the eight-section
skeleton with the left nav working. Nothing editable yet. Extend the case bank
list from T-020 so each row links here — use `db.cases.bank()`, which includes
drafts.

**Day 2 · The simple sections.** Patient, Truth, The trap, History, Persona.
Plain inputs and tag inputs. Token counter on the persona prompt — a rough
`len(text) / 4` is fine and honest; label it "≈".

**Day 3 · The two big ones.** Examination (27 rows) and Tests (86 rows), both
loaded from the master tables. These are long lists — make them scannable,
group them, give them a filter box. A doctor will scroll this every day.

**Day 4 · Validation.** All seven invariants, live. C-4 with the conflict panel
and the two one-click fixes. This is the day that matters; give it the whole
day.

**Day 5 · Save, guards, tests.** Wire the save path, the draft-from-published
behaviour, the unsaved-changes guard, the concurrent-edit banner. Write the
tests. Write the build log.

---

# Tests to write

In `tests/test_admin_case_editor.py`:

1. The editor route 404s for anonymous, non-admin, and expired tokens — and all
   three bodies are **identical** (same rule as T-020)
2. A case with a C-4 violation cannot be saved — the response says so and the
   database row is unchanged
3. The C-4 error names the offending term and the clue set it collides with
4. Saving an edit to a **published** version creates a new draft and leaves the
   published row untouched
5. A save carrying a stale `updated_at` is refused rather than silently
   overwriting
6. Saving writes a row to `audit_log`

Number 2 is the one that matters. Write it so that **if someone deletes the C-4
check, this test fails.** Then actually try it: comment the check out, run the
test, watch it go red, put the check back. A test you have not seen fail is a
test you do not know works.

---

# Definition of done

- [ ] All five `BUILD_PLAN` acceptance criteria satisfied
- [ ] The five checks in `00_START_HERE.md` Part 5 all pass locally
- [ ] Tests written, and you have watched the C-4 test fail on purpose
- [ ] `docs/build-log/T-021-case-editor.md` written — what you built, what you
      found, anything you left out
- [ ] `docs/spec/BUILD_PLAN.md` T-021 marked done, `python scripts/build_status.py` run
- [ ] Pull request open, base `main`, all eight checks green
