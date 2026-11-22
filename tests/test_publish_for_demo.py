"""
`scripts/publish_for_demo.py` — the guard, not the publishing.

The script fabricates an approving clinical review so that a local demo has a
case to serve. On the Supabase project that would mark a case clinically
approved with a fake review behind it, on the database the two real reviewers
will use — and **ten clinician-reviewed cases is the launch gate**, so a
fabricated row in that table is not a tidy-up, it is corrupted evidence for
the one question the table exists to answer.

So the only thing worth testing here is the refusal. The publishing half needs
a database and is exercised by running it; `is_local` is pure, which is why it
is a function rather than an inline condition.

No network, no database, so this runs in the fast suite.
"""

from __future__ import annotations

import pathlib
import sys

import pytest
import sqlalchemy as sa

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scripts.publish_for_demo import is_local  # noqa: E402


def url(dsn: str) -> sa.engine.URL:
    return sa.engine.make_url(dsn)


@pytest.mark.parametrize("dsn", [
    "postgresql+psycopg://nidan:pw@localhost:5433/nidan",
    "postgresql+psycopg://nidan:pw@127.0.0.1:5432/nidan",
    "postgresql+psycopg://nidan:pw@[::1]:5432/nidan",
    # The service name inside docker-compose.yml, which is how the app
    # container reaches Postgres.
    "postgresql+psycopg://nidan:pw@db:5432/nidan",
])
def test_a_local_database_is_allowed(dsn):
    assert is_local(url(dsn))


def test_a_socket_connection_is_local():
    """No host at all means a Unix socket, which cannot be somewhere else."""
    assert is_local(url("postgresql+psycopg:///nidan"))


@pytest.mark.parametrize("dsn", [
    # The shape of ADR-0017's project. A pooler host counts too — same database.
    "postgresql+psycopg://postgres:pw@db.abcdefghijklmnop.supabase.co:5432/postgres",
    "postgresql+psycopg://postgres:pw@aws-0-eu-central-1.pooler.supabase.com:6543/postgres",
    # Anything else that is not this machine.
    "postgresql+psycopg://u:pw@nidan-db.internal:5432/nidan",
    "postgresql+psycopg://u:pw@10.0.0.7:5432/nidan",
    "postgresql+psycopg://u:pw@staging.example.com:5432/nidan",
])
def test_a_remote_database_is_refused(dsn):
    assert not is_local(url(dsn)), (
        "publish_for_demo.py would fabricate a clinical approval on a "
        "non-local database; the fake review would sit in clinical_reviews "
        "alongside the real ones that decide the launch gate")


def test_a_hostname_that_merely_contains_localhost_is_refused():
    """
    `localhost.attacker.example` and `notlocalhost` are not this machine. The
    guard compares the whole host rather than looking for a substring, and a
    substring check is the obvious way to write this wrong.
    """
    for host in ("localhost.example.com", "notlocalhost", "mylocalhost",
                 "localhost.attacker.example"):
        assert not is_local(url(f"postgresql+psycopg://u:p@{host}:5432/n")), host


def test_the_host_comparison_ignores_case():
    assert is_local(url("postgresql+psycopg://u:p@LocalHost:5433/nidan"))
    assert not is_local(url("postgresql+psycopg://u:p@DB.X.SUPABASE.CO:5432/p"))


def test_the_fixture_reviewer_is_named_as_not_a_clinician():
    """
    The row this script writes has to be recognisable as fabricated by someone
    reading `clinical_reviews` later, without having to ask anybody. The name
    is the only part of it a human will see.
    """
    from scripts.publish_for_demo import FIXTURE_NAME, REVIEW_COMMENT

    assert "not a clinician" in FIXTURE_NAME.lower()
    assert "not a clinical review" in REVIEW_COMMENT.lower()


def test_the_rubric_comes_from_the_repository_not_a_copy():
    """
    The scores are built from `ReviewRepository`'s own `RUBRIC`, so a dimension
    added there cannot leave this script writing a review that the real
    validator would reject — which would fail at the trigger, with a message
    about approval rather than about the rubric.
    """
    import inspect

    from scripts import publish_for_demo

    source = inspect.getsource(publish_for_demo)
    assert "from nidan.infra.db.repositories.reviews import" in source
    assert "for dimension in RUBRIC" in source
