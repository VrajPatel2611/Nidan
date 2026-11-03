"""
Shared fixtures (BUILD_PLAN T-002).

The `_no_real_llm` fixture below is autouse: it applies to every test in the
suite whether the test asks for it or not. That is deliberate — criterion 1 is
that *no test makes a network call*, and a guarantee that depends on each test
author remembering to opt in is not a guarantee.
"""

import os
import subprocess
import sys

import pytest
import sqlalchemy as sa

from nidan.config import settings
from nidan.domain.content.cases import get_case
from nidan.domain.session import create_session
from nidan.infra.auth import jwks
from tests.app_config import TRUNCATE_SESSION_TABLES, llm_patch_targets
from tests.fakes.auth import AUDIENCE, ISSUER_URL, SigningAuthority
from tests.fakes.llm import FakeLLM

# Every domain test that needs a timestamp uses this one. Fixed, so any test
# that accidentally depends on wall-clock time fails consistently rather than
# once a year at midnight.
FIXED_START = "2026-01-01T09:00:00+00:00"


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── the database ─────────────────────────────────────────────────────
#
# These moved up from tests/db/conftest.py in T-013. Session state is no longer
# a dictionary in memory, so the consultation routes need a real database too —
# not only the schema tests. One container serves both.

@pytest.fixture(scope="session")
def pg_url() -> str:
    """A migrated database. Skips rather than fails when Docker is unavailable."""
    try:
        # The community path is the current one; the old location still works
        # but warns. Try both so the suite is quiet on either version.
        try:
            from testcontainers.community.postgres import PostgresContainer
        except ImportError:
            from testcontainers.postgres import PostgresContainer
    except ImportError:                                   # pragma: no cover
        pytest.skip("testcontainers not installed")

    try:
        container = PostgresContainer("pgvector/pgvector:pg16", driver="psycopg")
        container.start()
    except Exception as e:                                # pragma: no cover
        pytest.skip(f"Docker unavailable: {e}")

    url = container.get_connection_url()
    # sys.executable -m alembic, not bare "alembic": pytest may be running
    # without an activated venv, and then the console script is not on PATH.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO, capture_output=True, text=True,
        env=dict(os.environ, ALEMBIC_DATABASE_URL=url),
    )
    if result.returncode != 0:
        container.stop()
        pytest.fail(f"migrations failed:\n{result.stdout}\n{result.stderr}")

    yield url
    container.stop()


@pytest.fixture(scope="session")
def seeded_case_slugs(pg_url) -> list:
    """
    The slugs of the cases created by migration 019.

    SLUGS, not ids. Ids are generated fresh every time the migration runs, and
    `test_downgrade_to_base_then_upgrade_again` rebuilds the whole schema
    mid-session — after which a session-scoped list of ids refers to rows that
    no longer exist, and the teardown deletes all five seeded cases as
    "not seeded". Slugs are deterministic, so they survive the rebuild.

    Captured rather than hard-coded so it keeps working when cases 6-10 are
    authored.
    """
    engine = sa.create_engine(pg_url)
    with engine.connect() as conn:
        slugs = list(conn.execute(sa.text("SELECT slug FROM cases")).scalars())
    engine.dispose()
    return slugs



# ── authentication (T-014) ───────────────────────────────────────────

@pytest.fixture
def authority(monkeypatch):
    """
    A signing authority whose public key the cache will serve.

    `_fetch` is patched rather than the HTTP layer so the test can count
    fetches — which is what the rotation and rate-limit tests assert on.
    """
    auth = SigningAuthority()
    monkeypatch.setattr(settings, "SUPABASE_URL", ISSUER_URL)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", AUDIENCE)

    auth.fetches = 0

    def fake_fetch(self):
        auth.fetches += 1
        return dict(auth.keys)

    auth.keys = {auth.kid: auth.public_key}
    monkeypatch.setattr(jwks.KeyCache, "_fetch", fake_fetch)
    jwks.cache.clear()
    yield auth
    jwks.cache.clear()



# ── the network guard ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """
    Make a real model call impossible.

    Patches the provider's client factory rather than `call_llm`, because that
    is the single point where a network connection is actually constructed.
    Anything that reaches it — including code a future test forgets to stub —
    fails loudly here instead of quietly spending Groq quota.

    T-031 moved that point: the factory used to be `gateway._get_client` and
    is now `GroqProvider._get_client`, behind the provider seam. Patched on the
    class, so it covers the instance `provider.for_name()` caches for the
    process as well as any built later.
    """
    def _forbidden(self):
        raise AssertionError(
            "A test tried to construct a real LLM client. Tests must never call "
            "a live model — use the `fake_llm` fixture, or FakeLLM directly."
        )

    monkeypatch.setattr(
        "nidan.infra.llm.provider.GroqProvider._get_client", _forbidden)
    monkeypatch.setenv("GROQ_API_KEY", "test-key-never-used")


@pytest.fixture
def fake_llm(monkeypatch):
    """
    A FakeLLM patched in at every import site.

    `call_llm` is imported by name into the modules that use it, so patching
    `gateway.call_llm` alone would not affect those already-bound references.
    Each site is patched explicitly.

    The list lives in `tests/app_config.py` and `test_no_network.py` reads the
    same one. It used to be here and the guard kept its own copy, which is the
    stale-list bug the guard exists to catch, one level up.
    """
    llm = FakeLLM()
    for site in llm_patch_targets():
        monkeypatch.setattr(site, llm)
    return llm


# ── content and session fixtures ─────────────────────────────────────

@pytest.fixture
def case():
    """case_1 — the chest pain trap. Cardiac anchor, reflux truth."""
    return get_case("case_1")


@pytest.fixture
def blank_session():
    """A session with nothing recorded yet."""
    return create_session("case_1", started_at=FIXED_START)


@pytest.fixture
def session_factory():
    """
    Builds a session in whatever state a test needs.

        session_factory(questions=["..."], investigations=["ecg"])

    Sessions are plain dicts, so a test could build one literally — but then
    every test would encode the dict's shape, and changing that shape (T-013
    will) would mean editing every test rather than this one function.
    """
    def _make(case_id="case_1", questions=None, exams=None,
              investigations=None, diagnosis=None, topics=None,
              start=FIXED_START, end=None):
        questions = list(questions or [])
        return {
            "case_id": case_id,
            "question_count": len(questions),
            "questions_asked": questions,
            "topics_covered": list(topics or []),
            "exams_performed": list(exams or []),
            "investigations_ordered": list(investigations or []),
            "early_diagnosis": None,
            "diagnosis_submitted": diagnosis,
            "start_time": start,
            "end_time": end,
        }
    return _make


# ── routes that need the database (T-013) ────────────────────────────

@pytest.fixture
def live_db(pg_url, seeded_case_slugs, monkeypatch):
    """
    Point the application's engine at the test container, for tests that drive
    HTTP routes.

    Before T-013 the consultation routes needed nothing but memory, so they were
    smoke tests costing 0.15 s. Now every one of them replays an event log, and
    a test that avoided the database would be testing a code path that no longer
    exists. `tests/db/test_routes.py` holds those tests; this fixture is what
    they run against.
    """
    from nidan.config import settings
    from nidan.infra.db import engine as engine_mod

    monkeypatch.setattr(settings, "DATABASE_URL", pg_url)
    engine_mod.dispose_engine()

    admin = sa.create_engine(pg_url)
    yield admin

    engine_mod.dispose_engine()
    with admin.begin() as c:
        c.exec_driver_sql(TRUNCATE_SESSION_TABLES)
    admin.dispose()
