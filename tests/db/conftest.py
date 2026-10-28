"""
Database fixtures (BUILD_PLAN T-010).

A real PostgreSQL 16 with pgvector in a container, migrated from scratch. Not
SQLite, not a mock: every guarantee these tests check — partial unique indexes,
CHECK constraints, append-only triggers, the publication gate, RLS — is a
PostgreSQL feature. Testing them anywhere else would test nothing.

The container starts once per session and each test runs inside a transaction
that is rolled back, so tests neither wait for 16 migrations nor see each
other's rows.
"""

from __future__ import annotations

import hashlib
import os
import uuid

import pytest
import sqlalchemy as sa

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Tables holding only test rows, safe to truncate wholesale.
#
# `cases` and `case_versions` are NOT here, and that is the point. They were,
# until T-011 seeded the five clinical cases into them — at which point the
# truncate silently destroyed real content and every seed assertion failed in
# whichever test file happened to run next. The bug was mine, introduced in
# T-010 by a list that was correct when those tables held nothing but fixtures.
#
# Master content (examinations, investigations, topic_lexicon, topic_phrases,
# engine_versions) was never here for the same reason.
_DATA_TABLES = (
    "session_events", "session_results", "feedback_texts", "sessions",
    "clinical_reviews", "review_assignments",
    "subscriptions", "user_case_history", "user_progress",
    "llm_calls", "leakage_flags", "idempotency_keys", "audit_log",
)


@pytest.fixture
def db(pg_url, seeded_case_slugs):
    """
    A connection whose work is undone afterwards.

    The default is a transaction rolled back at the end, so tests insert freely
    without cleaning up and a failure cannot leave rows that break the next one.

    A test that needs its rows visible to a SECOND connection — the RLS tests —
    must commit, which ends that transaction. The teardown therefore also
    truncates: rollback covers the normal case, truncate covers the committed
    one. Without this, an RLS test's rows stay visible to every test that runs
    afterwards and the failure surfaces somewhere unrelated.
    """
    engine = sa.create_engine(pg_url)
    conn = engine.connect()
    txn = conn.begin()

    yield conn

    # conn.in_transaction(), not txn.is_active: after the test commits, the
    # transaction object is deassociated but still reports itself active, and
    # rolling it back then warns.
    if conn.in_transaction():
        txn.rollback()
    else:
        with conn.begin():
            # TRUNCATE, not DELETE, because session_events and audit_log carry
            # append-only triggers that refuse a DELETE by design. TRUNCATE
            # bypasses row triggers, which is exactly what a test teardown wants
            # and exactly what application code must never be able to do.
            #
            # Deliberately WITHOUT CASCADE. Cascade propagates outward to every
            # table holding a foreign key INTO these — and `cases.created_by`
            # references `profiles`, so `TRUNCATE profiles CASCADE` silently
            # took the five seeded cases with it. Listing the tables explicitly
            # means an FK we have forgotten fails loudly instead.
            conn.exec_driver_sql("TRUNCATE " + ", ".join(_DATA_TABLES))

            # Cases a test created, never the seeded five.
            conn.exec_driver_sql(
                "DELETE FROM cases WHERE slug <> ALL(%s)", (seeded_case_slugs,))
            # After the cases, because cases.created_by references profiles.
            conn.exec_driver_sql("DELETE FROM profiles")
            conn.exec_driver_sql("DELETE FROM auth.users")
    conn.close()
    engine.dispose()


# ── builders ─────────────────────────────────────────────────────────
# Every table worth testing hangs off profiles -> cases -> case_versions ->
# sessions. These make a test say what it is about rather than spend ten lines
# constructing ancestors.

@pytest.fixture
def make_user(db):
    def _make() -> uuid.UUID:
        uid = uuid.uuid4()
        db.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": uid})
        db.execute(sa.text("INSERT INTO profiles (id) VALUES (:id)"), {"id": uid})
        return uid
    return _make


@pytest.fixture
def make_case(db):
    def _make(slug: str | None = None) -> uuid.UUID:
        cid = uuid.uuid4()
        db.execute(sa.text("INSERT INTO cases (id, slug) VALUES (:id, :slug)"),
                   {"id": cid, "slug": slug or f"case-{cid.hex[:8]}"})
        return cid
    return _make


@pytest.fixture
def make_case_version(db, make_case):
    def _make(case_id=None, version: int = 1, status: str = "draft") -> uuid.UUID:
        case_id = case_id or make_case()
        vid = uuid.uuid4()
        # Column list taken from the migrated schema, not from memory: every
        # NOT NULL column without a default must be supplied.
        db.execute(sa.text("""
            INSERT INTO case_versions (
                id, case_id, version, status, content, title, anchor_topic,
                minimum_questions, required_topic_count, key_investigation_count,
                content_hash, published_at)
            VALUES (
                :id, :case_id, :version, CAST(:status AS case_status),
                '{}'::jsonb, 'Test case', 'cardiac', 7, 8, 4,
                :content_hash,
                CASE WHEN :status = 'published' THEN now() ELSE NULL END)
        """), {"id": vid, "case_id": case_id, "version": version,
               "status": status, "content_hash": hashlib.md5(vid.bytes).hexdigest()})
        return vid
    return _make


# ── T-012: fixtures for tests that go through the application's own pool ──
#
# The `db` fixture above hands out a connection and rolls it back. Repository
# tests cannot use it: `repo_scope` opens its own connection from
# `nidan.infra.db.engine` and commits, which is the whole point -- a test that
# borrowed the fixture's transaction would be testing a connection the
# application never uses, with the migrating role's privileges, and RLS would
# be exempt exactly as it is for the migration.

@pytest.fixture
def app_db(pg_url, seeded_case_slugs, monkeypatch):
    """
    Point the application's engine at the test container, and clean up after.

    Yields an admin engine for the setup that must bypass the layer being
    tested -- creating `auth.users` rows, which belongs to Supabase Auth in
    production and to no repository here.
    """
    from nidan.config import settings
    from nidan.infra.db import engine as engine_mod

    monkeypatch.setattr(settings, "DATABASE_URL", pg_url)
    engine_mod.dispose_engine()          # drop any pool built against another URL

    admin = sa.create_engine(pg_url)
    yield admin

    # Dispose first: TRUNCATE waits behind any connection still holding a lock,
    # and a leaked scope would hang the suite rather than fail it.
    engine_mod.dispose_engine()
    with admin.begin() as c:
        # _DATA_TABLES, not a second hand-written list: `llm_calls` references
        # `sessions`, so a shorter list fails outright -- and the next table
        # added would fail the same way in whichever test ran next, which is
        # precisely the T-010 bug this file already carries a scar from.
        c.exec_driver_sql("TRUNCATE " + ", ".join(_DATA_TABLES))
        c.exec_driver_sql(
            "DELETE FROM case_versions WHERE case_id IN "
            "(SELECT id FROM cases WHERE slug <> ALL(%s))", (seeded_case_slugs,))
        c.exec_driver_sql(
            "DELETE FROM cases WHERE slug <> ALL(%s)", (seeded_case_slugs,))
        c.exec_driver_sql("DELETE FROM profiles")
        c.exec_driver_sql("DELETE FROM auth.users")
    admin.dispose()


@pytest.fixture
def make_account(app_db):
    """
    A user that exists in `auth.users` but has no profile yet.

    Separate from `make_user` above because these tests create the profile
    *through* the repository -- that is one of the things being tested.
    """
    def _make() -> uuid.UUID:
        uid = uuid.uuid4()
        with app_db.begin() as c:
            c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": uid})
        return uid
    return _make


@pytest.fixture
def published_case(app_db):
    """A published case version, since migration 019 seeds only drafts."""
    def _make(slug: str | None = None, status: str = "published") -> uuid.UUID:
        cid, vid = uuid.uuid4(), uuid.uuid4()
        slug = slug or f"scope-test-{cid.hex[:8]}"
        with app_db.begin() as c:
            c.execute(sa.text("INSERT INTO cases (id, slug) VALUES (:id, :slug)"),
                      {"id": cid, "slug": slug})
            c.execute(sa.text("""
                INSERT INTO case_versions (
                    id, case_id, version, status, content, title, anchor_topic,
                    minimum_questions, required_topic_count,
                    key_investigation_count, content_hash, published_at)
                VALUES (:id, :case_id, 1, CAST(:status AS case_status), '{}'::jsonb,
                        'Scope test case', 'cardiac', 7, 8, 4, :hash,
                        CASE WHEN :status = 'published' THEN now() END)
            """), {"id": vid, "case_id": cid, "status": status,
                   "hash": hashlib.md5(vid.bytes).hexdigest()})
        return vid
    return _make
