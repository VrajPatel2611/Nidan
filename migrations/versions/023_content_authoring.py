"""content_authoring

Revision ID: 023
Revises: 022

The role the admin console writes clinical content as (BUILD_PLAN T-021).

**The hole this fills.** Migration 020 lists the tables the application may
write and deliberately leaves `cases` and `case_versions` out of it, with a
comment saying content is changed "by the case editor through a service
connection (T-021)". T-021 has now arrived, and that plan does not survive
contact with the other half of the requirement: `UX_SPEC` §12 says **every**
admin action writes an `audit_log` row, and `AuditRepository.record()` takes the
actor from the scope. A `ServiceActor` has no `user_id`, so the audit row it
would write has no actor -- and an audit log that cannot say who acted is not an
audit log, it is a list of things that happened.

So the case editor cannot run as `nidan_service`, and it cannot run as
`nidan_app` either, which has SELECT and nothing more on both tables. It needs a
role that is privileged for content and still carries `auth.uid()`.

| Role | RLS | `auth.uid()` | Used for |
|---|---|---|---|
| `nidan_app`     | applies  | set   | every authenticated learner request |
| `nidan_service` | bypassed | none  | the anonymous-trial path, migrations, jobs |
| **`nidan_admin`** | **applies** | **set** | **the admin console** |

**NOBYPASSRLS, like `nidan_app` and unlike `nidan_service`.** Granting the
console a bypassing role would have been one line shorter and would have
switched the safety net off for every statement an admin's request makes --
including the ones that touch `profiles` and `sessions`, which have nothing to
do with authoring. The policy below opens exactly one table, and leaves the
other eight protecting the admin's request the same way they protect a
learner's.

**What it may write, and what it may not.**

- `cases`, `case_versions` -- INSERT and UPDATE. No DELETE: a case is retired by
  setting `retired_at`, which is an UPDATE, so DELETE has no legitimate caller
  and would only ever destroy clinical history.
- `clinical_reviews` -- INSERT only. A recorded judgement is evidence; a review
  that can be edited afterwards cannot support the publication gate that rests
  on it (migration 007).
- `audit_log` -- INSERT only. The `forbid_mutation` trigger from migration 015
  would refuse an UPDATE anyway; not granting it says so at the permission layer
  rather than at the trigger.
- everything else -- SELECT.

The console does **not** get the learner-writable tables. An administrator using
Nidan as a learner is served by `AuthenticatedUser` on the ordinary routes, and
runs as `nidan_app` there like anyone else.

**The RLS policy.** `case_versions` has RLS enabled and exactly one policy:
`read_published_cases`, `FOR SELECT USING (status = 'published')` (migration
016). For a role RLS applies to, that means drafts are invisible and no write of
any kind is permitted -- which is most of what a case editor does. Policies are
permissive and OR-ed, so `admin_manages_case_versions` adds the admin's access
without touching what anyone else can see.

`cases` and `clinical_reviews` have RLS disabled, so the GRANT is sufficient
there and no policy is needed. Enabling RLS on them is a separate decision with
its own read-path consequences, and is not smuggled in here.
"""

from __future__ import annotations

from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None

ROLE = "nidan_admin"

# INSERT and UPDATE, no DELETE -- see the module docstring.
_AMENDABLE = ("cases", "case_versions")

# INSERT only. Both tables are records of something that happened.
_APPEND_ONLY = ("clinical_reviews", "audit_log")


def upgrade() -> None:
    bind = op.get_bind()

    # CREATE ROLE has no IF NOT EXISTS, and a failed CREATE aborts the whole
    # transaction -- the same guard, and the same reason, as migration 020.
    bind.exec_driver_sql(f"""
        DO $do$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
            CREATE ROLE {ROLE} NOLOGIN NOBYPASSRLS;
          END IF;
        END
        $do$;
    """)
    # Explicit rather than implied by CREATE: the role may already exist from an
    # earlier partial run, and the whole argument above rests on this attribute.
    bind.exec_driver_sql(f"ALTER ROLE {ROLE} NOBYPASSRLS")

    bind.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    # Needed to call auth.uid() from inside a policy, exactly as in 020.
    bind.exec_driver_sql(f"GRANT USAGE ON SCHEMA auth TO {ROLE}")
    bind.exec_driver_sql(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ROLE}")
    bind.exec_driver_sql(
        f"GRANT INSERT, UPDATE ON {', '.join(_AMENDABLE)} TO {ROLE}")
    bind.exec_driver_sql(
        f"GRANT INSERT ON {', '.join(_APPEND_ONLY)} TO {ROLE}")
    # audit_log is BIGSERIAL; an INSERT without sequence USAGE fails at runtime
    # rather than here.
    bind.exec_driver_sql(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE}")
    # So the connecting user can SET ROLE to it. In production the app's login
    # user is granted membership; locally they are the same user, which is what
    # makes an unconfigured `docker compose` stack work.
    bind.exec_driver_sql(f"GRANT {ROLE} TO CURRENT_USER")

    # Permissive and OR-ed with read_published_cases, so nothing any other role
    # can see changes. WITH CHECK as well as USING: USING alone governs which
    # rows are visible to read, update and delete, and would let an INSERT of a
    # row this role could not then see.
    bind.exec_driver_sql(f"""
        CREATE POLICY admin_manages_case_versions ON case_versions
          FOR ALL TO {ROLE}
          USING (true) WITH CHECK (true)
    """)


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        "DROP POLICY IF EXISTS admin_manages_case_versions ON case_versions")
    # DROP ROLE refuses while any privilege anywhere still references it, and
    # names the database rather than the grant. DROP OWNED removes them; the
    # role owns no objects, only permissions.
    bind.exec_driver_sql(f"""
        DO $do$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
            EXECUTE 'REVOKE ALL ON SCHEMA public FROM {ROLE}';
            EXECUTE 'DROP OWNED BY {ROLE}';
            EXECUTE 'DROP ROLE {ROLE}';
          END IF;
        END
        $do$;
    """)
