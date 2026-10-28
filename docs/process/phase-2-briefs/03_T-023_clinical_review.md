# T-023 · Clinical review workflow

**2 days · depends on T-022 · Owner Y**

> ```bash
> git checkout main && git pull origin main && git checkout -b feat/t-023-clinical-review
> ```

---

# Why this is the most important two days in the project

Nidan has two clinician reviewers waiting. They cannot do anything.

Right now the only way to look at a case is to open a Python file. So: no case
can be reviewed, no case can be published, case selection has nothing to select
from, and the **five remaining cases cannot be written** — because writing a
case nobody can review is writing into a drawer.

`BUILD_PLAN` §11.1 says content authoring, not engineering, is the real critical
path to launch. **This task is the gate in front of it.** When you merge this,
two doctors start working, and the longest remaining piece of the project starts
moving.

Two days of work. Do it carefully.

---

# Reading

1. `docs/spec/UX_SPEC.md` §12.6 — the review queue and the rubric form
2. `docs/spec/DATA_MODEL.md` §8.4 — the `scores` JSON shape
3. `docs/spec/PRD.md` FR-12.4 and FR-12.5
4. `docs/spec/BUILD_PLAN.md` — the T-023 block

Short. Maybe 600 words.

---

# The acceptance criteria

1. Assign a version to a reviewer; reviewer opens it in Playtest
2. Rubric 1–5 on plausibility, consistency, trap validity, solvability
3. `approve` / `changes_requested` / `rejected`, with comments
4. **Any dimension < 4 cannot be recorded as approved**
5. **Publish is blocked without an approving review** (409, and the DB trigger holds)

---

# The two screens

## Review queue — `/admin/reviews`

You already have a stub at this route from T-020. Three tabs:

```
Assigned to me (2)   ·   All pending (3)   ·   Completed
```

Each row: case title, version, how long ago it was assigned, the diagnosis, the
trap, and an **[ Open in Playtest ]** button.

That button is the whole reason T-022 came first. A reviewer does not read a
case — they **play** it, and judge it from the inside.

Note the route guard: `@require_reviewer`, not `@require_admin`. Reviewers are
a separate `platform_role` and reach the console only for this screen and
Playtest. The case editor and the operational screens stay closed to them.

## The review form — *alongside* Playtest, not instead of it

```
Clinical plausibility        ○1 ○2 ○3 ○4 ●5
Internal consistency         ○1 ○2 ○3 ●4 ○5
Trap validity                ○1 ○2 ○3 ○4 ●5
Solvability from the info    ○1 ○2 ○3 ●4 ○5

Comments
┌──────────────────────────────────────────┐
└──────────────────────────────────────────┘

[ Request changes ]  [ Reject ]  [ Approve ]
```

**Alongside** is not a layout detail. A reviewer who has to leave the case to
score it will score it from memory. Keep both visible.

Why a structured rubric rather than a free-text box: two reviewers scoring the
same four dimensions produce comparable judgements, and the scores are data you
can report. A comment box produces two opinions in different vocabularies.

---

# The data

`clinical_reviews` already exists (migration `006_cases.py`). You do not create
it.

```sql
clinical_reviews (
  id               UUID PK,
  case_version_id  UUID NOT NULL REFERENCES case_versions(id),
  reviewer_id      UUID NOT NULL REFERENCES profiles(id),
  decision         TEXT CHECK (decision IN ('approved','changes_requested','rejected')),
  scores           JSONB NOT NULL,
  comments         TEXT,
  reviewed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
)
```

`scores` has a fixed shape (`DATA_MODEL` §8.4):

```json
{
  "clinical_plausibility": 5,
  "internal_consistency":  4,
  "trap_validity":         5,
  "solvability":           4,
  "rubric_version": "v1"
}
```

Always write `"rubric_version": "v1"`. It is there so the rubric can change one
day without making every past review unreadable.

**The `nidan_admin` role has INSERT on `clinical_reviews` and nothing else** —
no UPDATE, no DELETE. A recorded judgement is evidence, and a review that can be
edited afterwards cannot support the publication gate that rests on it. If you
need a repository method to read or write this table, ask — do not add it to
`infra/` yourself.

---

# The three rules that are actually rules

## Any dimension below 4 cannot be approved

Enforced in the **application** — the database does not check it. If any of the
four scores is 1, 2 or 3, the **Approve** button is disabled and an inline note
names which dimension is short.

*Request changes* and *Reject* stay available. That is the correct outcome for a
case with a 3 — not a blocked reviewer, a different decision.

## Request changes and Reject both require a comment

An empty rejection tells the author nothing. Block the submit and say so.

## Reviewer ≠ author — warned, not blocked

If the reviewer is also the person who wrote the case, show a warning. Do not
block it. Two-person teams sometimes have no choice, and a rule that cannot be
followed gets worked around instead of obeyed.

---

# Publish — criterion 5, and the interesting one

A case version cannot be published without an approving review. This is enforced
**twice**, deliberately.

**In the database.** Migration `007_case_publish_gate.py` installs a trigger
`enforce_clinical_approval` on `case_versions`. Setting `status = 'published'`
with no approving row in `clinical_reviews` raises:

```
Case version <id> has no approving clinical review
```

That is not hypothetical — a test written during the T-021 backend work tried to
publish a row directly and was refused by this trigger. It works.

**In your code.** Check for an approving review before you attempt the update,
and return **409 Conflict** with a message a human can read.

Why both: the trigger is the guarantee — it holds even if someone writes to the
database with a script, and it cannot be forgotten. Your check is the *user
experience* — a clinician should see "this case has no approving review yet",
not a raw Postgres exception.

**Write the test for the trigger too.** Attempt the publish directly in SQL,
bypassing your code, and assert it raises. That test is what tells a future
reader the guarantee is real and not just a form validation someone can route
around.

The database also has a unique index `one_published_version_per_case` — only one
published version per case at a time. Handle that error gracefully if it fires.

---

# Files

### You write

```
nidan/web/admin/reviews/__init__.py
nidan/web/admin/reviews/routes.py
nidan/web/templates/admin/reviews/queue.html
nidan/web/templates/admin/reviews/_form.html
tests/test_admin_reviews.py
docs/build-log/T-023-clinical-review.md
```

Plus your existing `nidan/web/templates/admin/reviews.html` from T-020, which
this replaces or absorbs.

### You must not touch

```
migrations/**          ← clinical_reviews and the publish trigger already exist
nidan/domain/**
nidan/infra/**
nidan/api/**
```

---

# Suggested order

**Day 1 · Queue and assignment.** The three tabs, the rows, the [ Open in
Playtest ] link, and assigning a version to a reviewer. Every assignment writes
to `audit_log`.

**Day 2 · The form and the publish gate.** Rubric, the < 4 rule, the comment
requirements, recording the decision, the 409, and the tests.

---

# Tests to write

In `tests/test_admin_reviews.py`:

1. The routes 404 for anonymous, non-admin/non-reviewer and expired tokens, with
   **identical** bodies. A **reviewer** can reach `/admin/reviews`; a plain user
   cannot
2. **A review with any dimension < 4 cannot be recorded as approved** — the
   request is refused and no row appears with `decision = 'approved'`
3. `changes_requested` and `rejected` without a comment are refused
4. **Publishing without an approving review returns 409**
5. **Publishing without an approving review raises at the database level too** —
   attempt it in raw SQL and assert the trigger fires
6. Publishing *with* an approving review succeeds
7. Assigning a reviewer writes to `audit_log`

Tests 2 and 5 are the ones that matter. Break each on purpose and watch it fail
before you call them done.

---

# Definition of done

- [ ] All five acceptance criteria satisfied
- [ ] Both the application check and the database trigger tested
- [ ] The five checks in `00_START_HERE.md` Part 5 pass locally
- [ ] `docs/build-log/T-023-clinical-review.md` written
- [ ] `BUILD_PLAN` T-023 marked done, `python scripts/build_status.py` run
- [ ] Pull request open, base `main`, eight checks green

---

# When this merges

Say so immediately. Two clinicians can start, and five cases can be written.
Phase 2 is the milestone `BUILD_PLAN` calls the one that matters most, and this
is the task that closes it.
