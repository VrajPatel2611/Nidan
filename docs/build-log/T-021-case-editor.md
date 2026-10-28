# T-021 · Case editor

| | |
|---|---|
| **Task** | T-021, BUILD_PLAN Phase 2 |
| **Status** | ✅ Complete — 30 September 2026 |
| **Branch** | `feat/t-021-case-editor` |
| **Estimated** | 5 days |
| **Specification** | `UX_SPEC` §12 A-03 · `DATA_MODEL` §8.1 · `API_CONTRACT` §9 |
| **Behaviour change** | Form-based case editor at `/admin/cases/{id}/versions/{v}` for clinicians with live C-1...C-7 validation, save blocking on C-4 keyword overlaps, immutable published version handling, and concurrent edit protection. |

---

## 1 · Summary

Task **T-021: Case editor** provides the non-programmer interface for authoring and editing clinical case versions.

```
nidan/web/admin/cases/__init__.py             case editor package exports
nidan/web/admin/cases/routes.py               editor routes: view, save, validate, create
nidan/web/templates/admin/cases/editor.html   master editor container
nidan/web/templates/admin/cases/_section_*.html 8 section partials (patient, truth, trap, etc.)
nidan/web/templates/admin/cases/_validation.html live invariant validation sidebar
nidan/web/static/admin/case_editor.js         token counter & tag input interaction
tests/test_admin_case_editor.py                5 unit tests covering C-4, draft creation, OCC, audit log
```

---

## 2 · Definition of done

| # | Acceptance criterion | Met by |
|---|---|---|
| 1 | Sectioned form: patient, truth, trap, history, clues, exams, investigations, persona | `editor.html` & `_section_*.html` |
| 2 | Editing a published version creates a new draft; published content immutable | `save()` route handler in `cases/routes.py` & `create_draft()` |
| 3 | Live validation of C-1...C-7 invariants; **SAVE IS BLOCKED on C-4** with overlapping terms named | `_validate_invariants()` & `_validation.html` |
| 4 | Token counter on persona prompt (≈ `len(text) // 4`) | `_section_persona.html` & `case_editor.js` |
| 5 | Every save writes to `audit_log` with actor ID | `db.audit.record(...)` in save route |

---

## 3 · Key Features Built

### 3.1 C-4 Invariant Enforcement & One-Click Fixes
`c4_collisions(content)` checks if any `anchor_keywords` overlap `contradictory_clues` terms (including substring matches). When a collision exists:
- The **Save Draft** button is **disabled**.
- The validation sidebar highlights the exact colliding terms (e.g. `anchor "heart" <-> clue[0] "heartburn"`).
- Backend `save` route returns `400 Bad Request` if a C-4 violation payload is posted.

### 3.2 Immutable Published Versions
When an admin edits a version whose status is `published`, clicking Save creates a new draft version (vN+1) via `db.cases.create_draft(...)` and records a `case_version.draft_created` audit event.

### 3.3 Concurrent Edit Protection (OCC)
Form submits include `expected_updated_at`. `db.cases.update_draft(...)` compares `updated_at` in the WHERE clause, preventing stale edits from overwriting concurrent changes with a `409 Concurrent Edit` response.

---

## 4 · How to undo

1. Revert commit: `git revert HEAD`
2. Remove `nidan/web/admin/cases/` and `tests/test_admin_case_editor.py`

---

## 5 · Verification

All quality and safety gates pass:
```bash
ruff check .                          # All checks passed!
pytest -m "not slow" -q               # 583 passed
python validate_detectors.py         # PASS: detector accuracy 94.4% >= 94%
pytest tests/test_case_invariants.py # 40 passed
```
