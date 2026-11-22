"""
033 — the one mutation `session_events` permits (API-9).

`DATA_MODEL` §10.2's erasure redacts the free text a learner typed. It could
not run: migration 010 put `forbid_mutation()` on `session_events` as
`BEFORE UPDATE OR DELETE`, unconditionally, and it refuses even the table
owner. So `DELETE /v1/me` answered 501 and the account could not be erased.

**This does not weaken the append-only guarantee; it specifies a single
exception to it and refuses everything else.** `forbid_mutation_except_redaction`
permits exactly one state transition:

    payload->'text'  →  '"[redacted]"'      (and nothing else changes)

`id`, `session_id`, `seq`, `type` and `created_at` must be identical, and
`NEW.payload` must equal `jsonb_set(OLD.payload, '{text}', '"[redacted]"')`
exactly — so no other key may be added, removed or altered in the same
statement. DELETE stays refused with no exception at all.

Three properties follow, and each is why this was chosen over the
alternatives in API-9:

- **It is enforced in the database, for every role including the owner.** The
  guarantee stays where `ADR-0003` put it rather than moving into application
  code that a future caller can forget.
- **It is idempotent.** Redacting an already-redacted row satisfies the
  predicate and changes nothing, so a retried erasure job is safe.
- **It is self-announcing.** A redacted event reads `"[redacted]"`. Replay
  still returns a defined value, and anything reading the log can see that
  text was removed rather than silently getting different behaviour — which
  is what "redact at read" (option (a)) could not offer.

**`audit_log` keeps `forbid_mutation()` unchanged.** It records what was done
to an account, erasures included, and nothing in it is the learner's own
prose. Granting it the same exception would let the record of an erasure be
edited by the thing performing the erasure.

`forbid_mutation()` itself is left in place and is still the function
`audit_log` uses. This migration adds a second function rather than amending
the first, for the same reason migration 025 added a second policy: the
original is correct for the table it still guards.

Revision ID: 033
Revises: 032
"""

from __future__ import annotations

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None

# The literal the redaction writes. Kept here and mirrored in
# `nidan.infra.db.repositories.erasure.REDACTED`, with a test asserting the
# two agree: the trigger compares against it, so a disagreement would make
# every erasure raise "append-only" and look like the bug API-9 described.
REDACTED = "[redacted]"


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(f"""
        CREATE OR REPLACE FUNCTION forbid_mutation_except_redaction()
        RETURNS trigger AS $$
        BEGIN
          -- DELETE has no permitted form. A row may be emptied of its text,
          -- never removed: the sequence is what makes the log replayable, and
          -- a gap in it is indistinguishable from a bug.
          IF TG_OP = 'UPDATE'
             AND NEW.id         = OLD.id
             AND NEW.session_id = OLD.session_id
             AND NEW.seq        = OLD.seq
             AND NEW.type       = OLD.type
             AND NEW.created_at = OLD.created_at
             AND OLD.payload ? 'text'
             AND NEW.payload = jsonb_set(OLD.payload, '{{text}}',
                                         '"{REDACTED}"'::jsonb)
          THEN
            RETURN NEW;
          END IF;

          RAISE EXCEPTION
            'Table %% is append-only; the only permitted mutation is '
            'redacting payload->text (DATA_MODEL 10.2)', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
    """)

    # Replaced rather than added: two BEFORE triggers would both run, and the
    # unconditional one would refuse the redaction whichever order they fired
    # in. `forbid_mutation()` survives for `audit_log`.
    bind.exec_driver_sql(
        "DROP TRIGGER IF EXISTS session_events_append_only ON session_events")
    bind.exec_driver_sql("""
        CREATE TRIGGER session_events_append_only
          BEFORE UPDATE OR DELETE ON session_events
          FOR EACH ROW EXECUTE FUNCTION forbid_mutation_except_redaction()
    """)


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        "DROP TRIGGER IF EXISTS session_events_append_only ON session_events")
    bind.exec_driver_sql("""
        CREATE TRIGGER session_events_append_only
          BEFORE UPDATE OR DELETE ON session_events
          FOR EACH ROW EXECUTE FUNCTION forbid_mutation()
    """)
    bind.exec_driver_sql(
        "DROP FUNCTION IF EXISTS forbid_mutation_except_redaction()")
