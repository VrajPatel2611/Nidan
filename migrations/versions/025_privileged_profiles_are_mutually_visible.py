"""privileged_profiles_are_mutually_visible

Revision ID: 025
Revises: 024

Let administrators and reviewers see the privileged accounts the review
queue names, so that listing them stops needing the RLS bypass (handoff V-6).

**The bug is one missing `TO` clause, four migrations back.** Migration 016
wrote:

    CREATE POLICY own_profile ON profiles FOR ALL USING (id = auth.uid())

with no `TO`, so it applies to *every* role — `nidan_admin` included. The grant
was never the problem: migration 023 gave `nidan_admin` `SELECT ON ALL TABLES`.
It is this policy that reduces the result to one row, the administrator's own.
So the assign dropdown in T-023 had nothing to put in it, and the only way to
populate it was a `ServiceActor` — a connection with RLS switched off — to read
three columns of a handful of privileged accounts.

That is a disproportionate instrument, and worse, it is a *second* one.
`ADR-0016` accepted exactly one bypassing path and said so as a consequence:
"the bypass is confined to one 100-line module". `CLAUDE.md` repeats it —
`anonymous.py` is "the one path where RLS is OFF". A second use makes a
documented invariant false, and a false invariant is worse than none, because
the next person trusts it.

**The policy is deliberately narrow.** `platform_role IN ('reviewer', 'admin')`
and not "every profile": the task is naming colleagues in a review workflow,
and nothing in it requires reading a learner's row. Soft-deleted accounts are
excluded because a deleted reviewer is not assignable, and a dropdown is the
wrong place to learn that an account existed.

**It covers `nidan_reviewer` as well as `nidan_admin`, which is wider than
assignment alone needs.** Assigning is admin-only, so a reviewer has no use for
the list as a list. But the queue renders *names* — `UX_SPEC` §12.6 shows who
reviewed a version on the Completed tab — and a reviewer must resolve the
`reviewer_id` on a row they are already permitted to see. Granting only
`nidan_admin` would leave exactly two options for that: keep the bypass, or
degrade every reviewer's queue to "a reviewer". Both are worse than letting the
two or three privileged accounts see each other's display names, which the
Completed tab already discloses one row at a time.

Permissive policies are OR-ed, so `own_profile` is untouched and both roles
still see their own row whatever their `platform_role`.

**What this does not do.** It gives `nidan_app` nothing: a learner still sees
only themselves. It grants no write of any kind — `profiles` remains writable
only through `own_profile`. And when the Users screen (A-09, still a shell)
eventually needs to list learners, that is a different question with different
privacy consequences, and should get its own decision rather than an
enlargement of this one.
"""

from __future__ import annotations

from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None

POLICY = "privileged_profiles_are_mutually_visible"
ROLES = "nidan_admin, nidan_reviewer"


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(f"""
        CREATE POLICY {POLICY} ON profiles
          FOR SELECT TO {ROLES}
          USING (platform_role IN ('reviewer', 'admin') AND deleted_at IS NULL)
    """)


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(f"DROP POLICY IF EXISTS {POLICY} ON profiles")
