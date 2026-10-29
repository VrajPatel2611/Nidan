# T-023 · Clinical review workflow

| | |
|---|---|
| **Task** | T-023, BUILD_PLAN Phase 2 |
| **Status** | ✅ Complete — 29 October 2026 |
| **Branch** | `feat/t-023-clinical-review` |
| **Estimated** | 2 days |
| **Specification** | `UX_SPEC` §12.6 · `PRD` FR-12.4–12.5 · `DATA_MODEL` §5.2, §8.4 |
| **Behaviour change** | Clinical reviewers can now reach the console: a real review queue at `/admin/reviews`, Playtest with a structured review form beside it, and — for admins — assigning reviewers and publishing approved versions. **The last task of Phase 2.** |

---

## 1 · Summary

```
nidan/web/admin/reviews/__init__.py            package export
nidan/web/admin/reviews/routes.py              queue · assign · unassign · record · publish · sidebar count
nidan/web/templates/admin/reviews/queue.html   three tabs, and the assign form for admins
nidan/web/templates/admin/reviews/_form.html   rubric, decision, comments, publish, review history
nidan/web/static/admin/review_form.js          Approve disabled below 4, naming the dimension
nidan/web/admin/playtest/routes.py             @require_reviewer; ?review=1 adds the form
nidan/web/templates/admin/playtest/index.html  form beside the panel
nidan/web/admin/routes.py                      T-020 stub route and hard-coded counts removed
nidan/web/templates/admin/base.html            sidebar shows the real count
nidan/web/templates/admin/reviews.html         deleted — the T-020 stub with sample rows
nidan/infra/db/repositories/cases.py           + for_review()      ┐ infra additions, agreed with
nidan/infra/db/repositories/reviews.py         + reviewers()       ┘ Yogesh; Vraj to review (V-6)
tests/test_admin_reviews.py                    21 tests, real database
```

**21 new tests**, plus updates to two older ones (§4). 708 pass across the full
suite, none skipped.

The backend — `nidan_reviewer`, `review_assignments`, `ReviewRepository`,
`CaseRepository.publish()` — was built by Vraj in PR #26 (migration 024). This
task is the console on top of it.

---

## 2 · Definition of done

| # | Acceptance criterion | Met by |
|---|---|---|
| 1 | Assign a version to a reviewer; reviewer opens it in Playtest | `/admin/reviews/assign` (admin, audited) · queue rows link to `…/playtest?review=1` |
| 2 | Rubric 1–5 on the four dimensions | `_form.html` — one radio row per `RUBRIC` dimension; `rubric_version: v1` written by the repository |
| 3 | approve / changes_requested / rejected, with comments | three buttons; both "no" decisions require a comment, in the form and on the server |
| 4 | **Any dimension < 4 cannot be recorded as approved** | Approve disabled with the short dimension named · `check_rubric()` → 400 · `ReviewRepository` → `RubricViolation` |
| 5 | **Publish blocked without an approving review** (409, trigger holds) | `has_approval()` → 409 · `PublicationBlocked` / `AlreadyPublished` → 409 · migration 007's trigger |

| Check | Result |
|---|---|
| Test 2 (rubric floor) watched failing | ✅ the `approved` floor disabled in route and repository → 5 tests red; restored |
| Test 5 (trigger) watched failing | ✅ `enforce_clinical_approval` disabled → "DID NOT RAISE"; restored |
| `ruff` · `mypy --strict` · `lint-imports` | clean · clean · 2 kept |
| `pytest` (Docker running, nothing skipped) | 708 passed |
| `validate_detectors.py` · case invariants | 94.4 % · 46 passed |

---

## 3 · Decisions

### 3.1 Two additions to `infra/`, agreed before they were written

The brief says to ask before touching `infra/`. Asked; Yogesh chose to add them
and hand them to Vraj for review (handoff V-6).

- **`CaseRepository.for_review()`.** Migration 024 lets `nidan_reviewer` read
  drafts, but no repository method did: `for_editing()` is admin-only by design
  and `content()` filters to published. Without it a reviewer could not open a
  draft in Playtest — criterion 1. Same SELECT as `for_editing()`, accepting a
  `ReviewerUser` or `AdminUser`. A test proves the reviewer role still cannot
  write the row, through the repository or around it.
- **`ReviewRepository.reviewers()`.** The assign form needs to list reviewers,
  and `profiles` has a single RLS policy, `own_profile`, which applies to
  `nidan_admin` too: an admin cannot see anyone else's profile. The options were
  a new policy (a migration) or one narrow `ServiceActor` read returning id,
  display name and role of privileged accounts. This is the second; the reason
  string at the call site says so. A policy letting `nidan_admin` read
  privileged profiles would replace it.

### 3.2 Playtest is now `@require_reviewer`

A reviewer judges a case by playing it, so Playtest had to admit them.
Administrators reach it through the same `current_reviewer()` scope — playtesting
only reads, and never needs the right to author. The case editor stays
admin-only; a reviewer gets the same 404 there as anyone else.

### 3.3 The form sits beside Playtest, and posts as JSON

`?review=1` puts the form above the instrumentation panel, so both stay in view.
It posts with `fetch` rather than a form submit: Playtest's event log lives in
the page (T-022 §3.1), and a full page load would throw the consultation away
in the middle of a review.

### 3.4 Each rule is checked where a person meets it and where it is enforced

| Rule | Form | Route | Repository / database |
|---|---|---|---|
| < 4 cannot be approved | Approve disabled, dimension named | `check_rubric` → 400 | `RubricViolation` |
| "No" needs a comment | blocked before posting | `check_rubric` → 400 | `RubricViolation` |
| Publish needs approval | button disabled | `has_approval` → 409 | trigger 007 |

`test_the_repository_still_refuses_when_the_route_check_is_bypassed` removes the
route's check and confirms the repository still refuses.

### 3.5 Reviewer ≠ author: warned

`is_author()` drives an amber notice on the form. Recording still works — tested.

### 3.6 Only privileged accounts can be assigned

`review_assignments.reviewer_id` references `profiles`, so the database accepts
any account. The route refuses one that is not a reviewer or admin.

### 3.7 The sidebar count is real

`Review (3)` was hard-coded on every admin page since T-020. It is now this
person's outstanding assignments, from an app context processor, at most one
query per request and none outside `/admin`.

### 3.8 Not in this task

- **No audit row for recording a review.** `nidan_reviewer` has no INSERT on
  `audit_log`, and the `clinical_reviews` row is itself the append-only record of
  who judged what. Assigning, unassigning and publishing are audited.
- **No retire / republish.** Publishing v2 while v1 is live returns 409 with a
  sentence saying so; retiring is a later decision.

---

## 4 · Tests changed, and why

- `tests/test_admin_playtest.py` — reviewers now get 200 on Playtest rather than
  404. That is criterion 1, not a regression.
- `tests/test_admin_auth.py` — asserted the hard-coded `(3)`. It now mocks two
  assignments and asserts `(2)`, and patches the reviews module's scope so the
  test never reaches a database (it had been, silently, through `.env`).

---

## 5 · How to undo

1. `git revert` the T-023 commit
2. No migration was added; nothing in the database to undo

---

## 6 · Verification

```bash
ruff check . && mypy nidan/domain --strict && lint-imports
pytest -q                                   # 708 passed, Docker running
pytest tests/test_admin_reviews.py -q       # 21 passed
python validate_detectors.py                # PASS: 94.4% >= 94%
pytest tests/test_case_invariants.py -q     # 46 passed
```
