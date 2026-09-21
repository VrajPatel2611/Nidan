"""platform_role

Revision ID: 022
Revises: 021

Add platform_role enum ('user', 'reviewer', 'admin') and platform_role column
to profiles table (BUILD_PLAN T-020).
"""

from __future__ import annotations

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("""
        DO $do$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'platform_role') THEN
            CREATE TYPE platform_role AS ENUM ('user', 'reviewer', 'admin');
          END IF;
        END
        $do$;

        ALTER TABLE profiles
          ADD COLUMN IF NOT EXISTS platform_role platform_role NOT NULL DEFAULT 'user';
    """)


def downgrade() -> None:
    bind = op.get_bind()
    bind.exec_driver_sql("""
        ALTER TABLE profiles DROP COLUMN IF EXISTS platform_role;
        DROP TYPE IF EXISTS platform_role CASCADE;
    """)
