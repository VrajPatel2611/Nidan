"""content editors

Revision ID: 036
Revises: 035

The grants T-044's two editors need, and nothing wider (`UX_SPEC` A-06,
A-07).

## 1. `nidan_admin` may INSERT and UPDATE the master lists

Migration 023 gave `nidan_admin` SELECT on every table and write access to
`cases`, `case_versions`, `clinical_reviews` and `audit_log` only. So the
clinical-content screen could list the examinations and investigations
but not add or change one.

**No DELETE.** `UX_SPEC` A-06 says delete is not offered and `DATA_MODEL`
§5.3 says why: a key appears inside stored `examination` and
`investigation` events, and a session replayed after its key had gone would
reference something the database no longer knows. Retiring is
`is_active = false`, which is an UPDATE. Leaving DELETE ungranted means
a route that tries to delete is refused by Postgres as well as by the
code.

## 2. `nidan_service` may UPDATE two columns of `topic_phrases`

`match_count` and `last_matched_at` drive the dead-phrase report. Migration
005 says a nightly job fills them, but that job was never built.
`python -m nidan.jobs lexicon` is that job now, and it runs as
`nidan_service`. Migration 020 gave that role write access only to the
learner-owned and operational tables.

**Column-level, so the job can count but cannot rewrite.** The phrases
themselves stay migration-only. The engine scores from
`nidan/domain/assessment/topics.py`, not from this table, and
`tests/db/test_seed.py` asserts the two agree. A job that could UPDATE
`phrase` could break that agreement with nothing in the code changing.

## 3. Nothing for the lexicon itself

The lexicon editor does not write `topic_lexicon` or `topic_phrases` at all.
It generates the migration and the `topics.py` change for a developer to
commit, so scoring, replay (`ADR-0003`) and the golden record move only in a
reviewed commit. See `nidan/web/admin/content/lexicon_export.py`.
"""

from __future__ import annotations

from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None

_MASTER_LISTS = ("examinations", "investigations")


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        f"GRANT INSERT, UPDATE ON {', '.join(_MASTER_LISTS)} TO nidan_admin")
    bind.exec_driver_sql(
        "GRANT UPDATE (match_count, last_matched_at) ON topic_phrases "
        "TO nidan_service")


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        "REVOKE UPDATE (match_count, last_matched_at) ON topic_phrases "
        "FROM nidan_service")
    bind.exec_driver_sql(
        f"REVOKE INSERT, UPDATE ON {', '.join(_MASTER_LISTS)} FROM nidan_admin")
