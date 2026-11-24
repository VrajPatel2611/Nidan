"""leakage review

Revision ID: 034
Revises: 033

An administrator can see and resolve a leakage flag (BUILD_PLAN T-040,
criterion 2).

Migration 015 created `leakage_flags` and migration 020 gave `nidan_app` and
`nidan_service` INSERT on it, which is what a consultation needs. Nothing let
anybody act on one, and two separate things were missing.

## 1. The grant

Migration 023 gives `nidan_admin` `SELECT ON ALL TABLES` plus INSERT/UPDATE on
`cases` and `case_versions` and INSERT on `clinical_reviews` and `audit_log`.
Confirming or dismissing a flag is an UPDATE on `leakage_flags`, which was in
none of those lists — so the console could list the queue and not act on it.

**UPDATE only, never INSERT.** An administrator must not be able to create a
flag by hand. `confirmed = true` excludes a session from the research export
(`DATA_MODEL` §11.7), so a hand-written flag is a way to drop a session from
the dataset without a detector ever having objected to it — the one thing the
queue exists to make visible. Flags are written by the consultation path,
reviewed here, and that asymmetry is the control.

## 2. Two policies, because RLS binds `nidan_admin` too

`own_sessions` is `FOR ALL USING (user_id = auth.uid())` **with no `TO`
clause**, which `DATA_MODEL` §10.1 flags explicitly: it binds every role,
`nidan_admin` included, and migration 025 exists to work around the same thing
on `profiles`. So the queue's join through `sessions` returned nothing for an
administrator, and `session_events` — where the flagged reply lives — returned
nothing either. Both looked like an empty queue rather than a permission
error, which is the failure mode §10.1 is otherwise so careful about.

**Both policies are keyed on the flag, not on the role's seniority.** An
administrator may read a session *because it carries a leakage flag*, and may
read exactly the event the flag points at — matched on `session_id` AND `seq`.
Not the learner's questions, not their diagnosis, not the rest of the
consultation. The queue needs the patient's words to be judged, and that is
the whole of what this opens.

This is deliberately narrower than "administrators may read sessions". A-09
(users and support) will want more one day; it should ask for it then, in its
own migration, with its own reason. `nidan_reviewer` gets nothing here: which
sessions count as research data is not a clinical judgement, and widening the
narrowest role to cover it would undo the reason it is narrow.
"""

from __future__ import annotations

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    bind.exec_driver_sql("GRANT UPDATE ON leakage_flags TO nidan_admin")

    bind.exec_driver_sql("""
        CREATE POLICY flagged_sessions_are_visible_to_admins ON sessions
          FOR SELECT TO nidan_admin
          USING (EXISTS (SELECT 1 FROM leakage_flags lf
                         WHERE lf.session_id = sessions.id));
    """)

    # Matched on seq as well as session, so this is the flagged reply and not
    # the consultation around it.
    bind.exec_driver_sql("""
        CREATE POLICY flagged_replies_are_visible_to_admins ON session_events
          FOR SELECT TO nidan_admin
          USING (EXISTS (SELECT 1 FROM leakage_flags lf
                         WHERE lf.session_id = session_events.session_id
                           AND lf.event_seq = session_events.seq));
    """)


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        "DROP POLICY IF EXISTS flagged_replies_are_visible_to_admins "
        "ON session_events")
    bind.exec_driver_sql(
        "DROP POLICY IF EXISTS flagged_sessions_are_visible_to_admins "
        "ON sessions")
    bind.exec_driver_sql("REVOKE UPDATE ON leakage_flags FROM nidan_admin")
