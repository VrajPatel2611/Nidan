"""
T-010 criterion 5 · the migration chain is reversible.

A migration that only goes forwards is a migration you cannot roll back when a
deploy goes wrong at 2 a.m. The round-trip is tested because an untested
downgrade is not a downgrade — it is an assumption.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
import sqlalchemy as sa

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EXPECTED_TABLES = {
    "profiles", "subscriptions", "user_progress", "user_case_history",
    "cases", "case_versions", "clinical_reviews",
    "examinations", "investigations", "topic_lexicon", "topic_phrases",
    "sessions", "session_events", "session_results", "engine_versions",
    "feedback_texts",
    "llm_calls", "leakage_flags", "idempotency_keys", "audit_log", "feature_flags",
}


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO, capture_output=True, text=True,
        env=dict(os.environ, ALEMBIC_DATABASE_URL=url),
    )


def test_every_specified_table_exists(db):
    got = set(db.execute(sa.text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    )).scalars())
    got.discard("alembic_version")
    missing = EXPECTED_TABLES - got
    extra = got - EXPECTED_TABLES
    assert not missing, f"tables in DATA_MODEL but not created: {sorted(missing)}"
    assert not extra, f"tables created but not in DATA_MODEL: {sorted(extra)}"


def test_every_declared_enum_type_exists_and_no_others(db):
    """
    An enum is part of the contract (`DATA_MODEL` §3), so adding one is a
    deliberate act and this test is where it gets declared. It was named
    `test_all_six_enum_types_exist` until T-020 added a seventh — the failure
    is the point, not an inconvenience.
    """
    enums = set(db.execute(sa.text(
        "SELECT typname FROM pg_type WHERE typtype='e'")).scalars())
    assert enums == {
        # migration 003
        "professional_role", "subscription_tier", "case_status",
        "case_origin", "session_status", "event_type",
        # migration 022 — who may reach the admin console (UX_SPEC §12.1)
        "platform_role",
    }


def test_the_head_revision_matches_the_latest_migration_file(db):
    """
    Asserted against the filesystem rather than a literal, so adding a
    migration does not require remembering to update this test. It was written
    as `== "016"` in T-010 and went stale the moment T-011 added three more.
    """
    import pathlib
    versions = pathlib.Path(__file__).resolve().parents[2] / "migrations" / "versions"
    latest = max(f.name.split("_")[0] for f in versions.glob("[0-9]*.py"))
    assert db.execute(sa.text(
        "SELECT version_num FROM alembic_version")).scalar() == latest


@pytest.mark.slow
def test_downgrade_to_base_then_upgrade_again(pg_url):
    """
    The acceptance criterion, run literally.

    Marked slow: it tears the schema down and rebuilds it, so it cannot share
    the session database with tests that expect tables to exist. It runs last.
    """
    down = _alembic(pg_url, "downgrade", "base")
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    engine = sa.create_engine(pg_url)
    with engine.connect() as c:
        remaining = set(c.execute(sa.text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
    remaining.discard("alembic_version")
    assert not remaining, f"downgrade left tables behind: {sorted(remaining)}"

    up = _alembic(pg_url, "upgrade", "head")
    assert up.returncode == 0, f"re-upgrade failed:\n{up.stdout}\n{up.stderr}"

    with engine.connect() as c:
        rebuilt = set(c.execute(sa.text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
    rebuilt.discard("alembic_version")
    assert rebuilt == EXPECTED_TABLES
    engine.dispose()
