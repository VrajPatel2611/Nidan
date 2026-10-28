"""clinical_review

Revision ID: 024
Revises: 023

What a clinical reviewer may do, and where an assignment is recorded
(BUILD_PLAN T-023).

**Three gaps, found by the person who needed them.** `@require_reviewer` has
existed since T-020 and lets a reviewer into the console, but their requests run
as `nidan_app`: migration 016's only policy on `case_versions` is
`read_published_cases`, so a draft is invisible to them, and nothing grants
INSERT on `clinical_reviews`. A reviewer could reach the queue and then do
none of the two things a review consists of. Separately, T-023 criterion 1 is
"assign a version to a reviewer" and no table recorded that.

**A third role rather than reusing `nidan_admin`.** `nidan_admin` can write
clinical content (migration 023). Giving it to reviewers would mean the two
clinicians could edit the cases they are judging, and `UX_SPEC` §12.6 is
explicit that the case editor stays closed to them. The point of a review is
that it is performed by someone who did not write the thing.

| Role | Draft `case_versions` | `clinical_reviews` | `cases` |
|---|---|---|---|
| `nidan_app`      | invisible | — | SELECT |
| `nidan_reviewer` | **SELECT** | **INSERT** | SELECT |
| `nidan_admin`    | SELECT + UPDATE | INSERT | INSERT + UPDATE |

`nidan_reviewer` is `NOBYPASSRLS`, like the other two application roles. It gets
SELECT on a **named list** of tables rather than on everything in the schema:
migrations 020 and 023 both used `ALL TABLES`, which was defensible for roles
that serve the whole application, but a reviewer's whole job touches nine
tables and there is no reason for them to be able to read `audit_log`,
`llm_calls` or anyone's billing.

**`review_assignments` is a table, not a column on `case_versions`.** A column
holds one reviewer; `PRD` FR-12.4 has two clinicians and `UX_SPEC` §12.6 shows
both an "Assigned to me" and an "All pending" tab, which only makes sense when a
version can be with more than one of them. It also keeps an editorial workflow
fact out of the row that holds clinical content, and records who assigned it and
when — the questions asked when a review has been sitting untouched for a week.

**Why no RLS on `review_assignments`.** Enabling it would require a policy for
every role that reads it, and the table holds no personal data: it is a pair of
ids saying who should look at which draft. The tables it references are
protected; this one is a worklist.
"""

from __future__ import annotations

from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None

ROLE = "nidan_reviewer"

# Everything the review workflow reads, and nothing else. Playtest (T-022) runs
# the assessment engine over a draft, which is why the content master tables and
# `engine_versions` are here: the engine's thresholds are data, not constants.
_READABLE = (
    "cases", "case_versions", "clinical_reviews", "review_assignments",
    "profiles", "examinations", "investigations", "topic_lexicon",
    "topic_phrases", "engine_versions",
)


def upgrade() -> None:
    bind = op.get_bind()

    bind.exec_driver_sql("""
        CREATE TABLE review_assignments (
            case_version_id UUID NOT NULL
                            REFERENCES case_versions(id) ON DELETE CASCADE,
            reviewer_id     UUID NOT NULL REFERENCES profiles(id),
            assigned_by     UUID NOT NULL REFERENCES profiles(id),
            assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

            -- Composite key, not a surrogate id: the same reviewer cannot be
            -- assigned the same version twice, and two reviewers can both hold
            -- it. Assigning again is then an idempotent no-op rather than a
            -- duplicate row that makes the queue count wrong.
            PRIMARY KEY (case_version_id, reviewer_id)
        );

        -- The "Assigned to me" tab, newest first.
        CREATE INDEX review_assignments_for_reviewer
            ON review_assignments (reviewer_id, assigned_at DESC);
    """)

    # CREATE ROLE has no IF NOT EXISTS, and a failed CREATE aborts the whole
    # transaction -- the same guard, and reason, as migrations 020 and 023.
    bind.exec_driver_sql(f"""
        DO $do$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
            CREATE ROLE {ROLE} NOLOGIN NOBYPASSRLS;
          END IF;
        END
        $do$;
    """)
    # Explicit rather than implied by CREATE: the role may survive from an
    # earlier partial run, and the argument above rests on this attribute.
    bind.exec_driver_sql(f"ALTER ROLE {ROLE} NOBYPASSRLS")

    bind.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    # Needed to call auth.uid() from inside a policy.
    bind.exec_driver_sql(f"GRANT USAGE ON SCHEMA auth TO {ROLE}")
    bind.exec_driver_sql(f"GRANT SELECT ON {', '.join(_READABLE)} TO {ROLE}")
    # INSERT only. A recorded judgement is evidence; one that can be revised
    # afterwards cannot support the publication gate that rests on it
    # (migration 007).
    bind.exec_driver_sql(f"GRANT INSERT ON clinical_reviews TO {ROLE}")
    bind.exec_driver_sql(f"GRANT {ROLE} TO CURRENT_USER")

    # SELECT, never write. A reviewer who could edit the case they are judging
    # is not a reviewer. Permissive and OR-ed with `read_published_cases`, so
    # what any other role sees is unchanged.
    bind.exec_driver_sql(f"""
        CREATE POLICY reviewer_reads_case_versions ON case_versions
          FOR SELECT TO {ROLE} USING (true)
    """)

    # Migrations 020 and 023 granted SELECT on ALL TABLES *as they stood then*;
    # that is a one-off grant, not a standing rule, so a table created now
    # reaches none of those roles without being named here.
    bind.exec_driver_sql(
        "GRANT SELECT, INSERT, DELETE ON review_assignments TO nidan_admin")
    bind.exec_driver_sql(
        "GRANT SELECT ON review_assignments TO nidan_service")


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql(
        "DROP POLICY IF EXISTS reviewer_reads_case_versions ON case_versions")
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
    bind.exec_driver_sql("DROP TABLE IF EXISTS review_assignments CASCADE")
