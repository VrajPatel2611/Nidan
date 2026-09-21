"""platform_role

Revision ID: 022
Revises: 021

Who may reach the admin console (BUILD_PLAN T-020, `UX_SPEC` §12.1).

§12.1 specifies that admin access uses **the same authentication as the
product** — "there is no separate admin credential store, a second credential
system is a second thing to compromise" — gated on `role = 'admin'` on the
profile.

**That field did not exist.** `profiles` carried `professional_role` (what the
learner does clinically) and `subscription_tier` (what they pay), and nothing
about platform privilege. This adds it.

**Why an enum rather than `is_admin BOOLEAN`.** There are already two distinct
privileged kinds in the specification, not one:

* **admin** — the console, content, operations (`UX_SPEC` §12)
* **reviewer** — a clinician who assesses a case version and records a verdict.
  `clinical_reviews.reviewer_id` references `profiles(id)` (migration 006), and
  T-023 has reviewers opening a case in Playtest, so they need the console too.

A boolean cannot express the second, and discovering that at T-023 would mean a
second migration plus a rewrite of every access check written against it.

**Why `platform_role` rather than `role`.** `professional_role` is already a
column on this table and means something entirely different — a physician is
not an admin. One of these names had to be unambiguous, and the new one is the
one that can still be chosen.

Default `'user'`, NOT NULL: privilege is never absent-or-unknown, and a NULL
here would make every access check answer three ways instead of two.
"""

from __future__ import annotations

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None

# DATA_MODEL §4.1. Ordered least to most privileged, which is only a reading
# convenience — Postgres enum order is not used for comparison anywhere, and
# code that relied on it would break the day a value was inserted.
PLATFORM_ROLES = ("user", "reviewer", "admin")


def upgrade() -> None:
    bind = op.get_bind()
    labels = ", ".join(f"'{v}'" for v in PLATFORM_ROLES)
    bind.exec_driver_sql(f"CREATE TYPE platform_role AS ENUM ({labels})")

    bind.exec_driver_sql("""
        ALTER TABLE profiles
        ADD COLUMN platform_role platform_role NOT NULL DEFAULT 'user'
    """)

    # Partial: the overwhelming majority of rows are 'user', and an index over
    # them would be a scan of the whole table wearing an index's clothes. The
    # only question anyone asks of this column is "who is privileged".
    bind.exec_driver_sql("""
        CREATE INDEX profiles_privileged
            ON profiles (platform_role)
            WHERE platform_role <> 'user'
    """)


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("DROP INDEX IF EXISTS profiles_privileged")
    bind.exec_driver_sql("ALTER TABLE profiles DROP COLUMN IF EXISTS platform_role")
    bind.exec_driver_sql("DROP TYPE IF EXISTS platform_role")
