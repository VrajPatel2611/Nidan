# T-020 · Admin shell and auth

| | |
|---|---|
| **Task** | T-020, BUILD_PLAN Phase 2 |
| **Status** | ✅ Complete — 21 September 2026 |
| **Branch** | `feat/admin-shell` |
| **Estimated** | 1 day |
| **Specification** | `UX_SPEC` §12 · `ADR-0006` · `API_CONTRACT` §2.7 |
| **Behaviour change** | Desktop-only Jinja + HTMX admin console shell created at `/admin/*` with strict 404 access control and append-only audit logging. |

---

## 1 · Summary

Phase 2 begins with **T-020: Admin shell and auth**, establishing the desktop-only Jinja + HTMX administrative interface and enforcing strict 404 security rules.

```
migrations/versions/022_platform_role.py   platform_role enum & profiles table column
nidan/infra/db/repositories/audit.py       AuditRepository for append-only audit_log
nidan/infra/db/repositories/profiles.py    ProfileRepository selects platform_role
nidan/api/auth.py                           @require_admin and @require_reviewer decorators
nidan/web/admin/routes.py                  Flask Blueprint for /admin shell
nidan/web/templates/admin/                  Jinja + HTMX administrative layout templates
tests/test_admin_auth.py                    Comprehensive 404 access control & audit tests
```

**12 new unit tests.** 567 pass across the full test suite.

---

## 2 · Definition of done

| # | Acceptance criterion | Met by |
|---|---|---|
| 1 | Jinja + HTMX shell, admin-only, desktop-only | `nidan/web/admin/routes.py` & `nidan/web/templates/admin/` |
| 2 | Every admin action writes to `audit_log` | `AuditRepository` in `nidan/infra/db/repositories/audit.py` & `/admin/audit-action` route |
| 3 | Access rule: `/admin/*` yields 404 for unauthenticated visitors and non-admins | `@require_admin` in `nidan/api/auth.py` & `tests/test_admin_auth.py` |
| 4 | Pending counts shown as plain numbers in brackets, no red badges | `base.html` sidebar template (`Review (3)`) |

---

## 3 · What was built

### 3.1 The 404 Access Rule

In accordance with `API_CONTRACT` §2.7 and `UX_SPEC` §12.1:
```
/admin/*  →  session valid?  ──no──►  404
          →  role = 'admin'? ──no──►  404
          →  serve
```
A non-admin or unauthenticated visitor MUST receive **404 (Not Found)**, never 403 or 401. A 403 or 401 response confirms the existence of the administrative console; a 404 provides zero information.

### 3.2 Platform Role Schema & Authorization Decorators

Migration 022 (`022_platform_role.py`) creates the `platform_role` enum (`'user'`, `'reviewer'`, `'admin'`) and adds the `platform_role` column to the `profiles` table.

The auth decorators `@require_admin` and `@require_reviewer` evaluate the user's platform role directly from their profile row inside a repository scope.

### 3.3 Audit Repository

`AuditRepository` in `nidan/infra/db/repositories/audit.py` records administrative actions into the append-only `audit_log` table. The actor ID is retrieved directly from the repository scope.

### 3.4 Jinja + HTMX Desktop Shell

`nidan/web/templates/admin/base.html` provides the responsive desktop layout featuring:
- Top Navigation: Nidan Admin branding, top section tabs, user account status
- Contextual Sidebar: Context-specific sub-navigation with plain number counters in brackets, avoiding red badge fatigue
- Dark-themed modern styling aligned with Nidan design system guidelines

---

## 4 · How to undo

1. Revert commit `git revert HEAD`
2. Alembic downgrade: `alembic downgrade 021`

---

## 5 · Verification

All 6 quality and safety gates pass cleanly:
```bash
pytest                               # 567 passed
ruff check . --fix                   # 0 issues remaining
mypy nidan/domain --strict          # Success: no issues found in 15 source files
lint-imports                         # Contracts: 2 kept, 0 broken
python validate_detectors.py         # PASS: detector accuracy 94.4% >= 94%
```
