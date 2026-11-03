"""
T-031 · the `llm_calls` row, against a real database.

`tests/test_llm_accounting.py` checks what the gateway hands back. This checks
what survives the trip into Postgres, which is a different question: the
`purpose` CHECK, the `status` CHECK, the `NUMERIC(10,6)` scale, the nullable
`session_id`, and which roles may write at all.

**The role assertions are the ones worth having.** Migration 024 withheld
`llm_calls` from `nidan_reviewer` deliberately — "no reason for them to be able
to read `audit_log`, `llm_calls` or anyone's billing" — and that sentence is
the reason the admin Playtest route records nothing. A grant widened by
accident would make the comment at that call site false while every other test
still passed.
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa

from nidan.infra.db.actor import AuthenticatedUser, ReviewerUser
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.llm import PURPOSES, UnaccountablePurpose


def _user(make_account) -> uuid.UUID:
    uid = make_account()
    with repo_scope(AuthenticatedUser(uid)) as db:
        db.profiles.ensure(display_name="Test Learner")
    return uid


class _Call:
    """A gateway `LLMCall`'s duck shape, which is all `record_call` reads."""

    def __init__(self, **kw):
        self.purpose = kw.get("purpose", "patient")
        self.provider = kw.get("provider", "groq")
        self.model = kw.get("model", "llama-3.3-70b-versatile")
        self.prompt_tokens = kw.get("prompt_tokens", 412)
        self.output_tokens = kw.get("output_tokens", 58)
        self.cost_usd = kw.get("cost_usd", Decimal("0.000289"))
        self.latency_ms = kw.get("latency_ms", 731)
        self.status = kw.get("status", "ok")
        self.attempt = kw.get("attempt", 1)


def _rows(app_db):
    with app_db.begin() as c:
        return c.execute(sa.text(
            "SELECT * FROM llm_calls ORDER BY id")).mappings().all()


# ── the row ──────────────────────────────────────────────────────────

def test_a_call_is_recorded_against_its_session(app_db, make_account, published_case):
    uid, cv = _user(make_account), published_case()
    with repo_scope(AuthenticatedUser(uid)) as db:
        session_id = db.sessions.create(cv)["id"]
        db.llm_calls.record_call(_Call(), session_id=session_id)

    row = _rows(app_db)[0]
    assert row["session_id"] == session_id
    assert row["purpose"] == "patient"
    assert row["provider"] == "groq"
    assert row["prompt_tokens"] == 412
    assert row["output_tokens"] == 58
    assert row["latency_ms"] == 731
    assert row["attempt"] == 1


def test_a_call_may_belong_to_no_session(app_db, make_account):
    """
    `session_id` is nullable (`DATA_MODEL` §7.1) and this is why: an extraction
    run belongs to no consultation. A NOT NULL here would have forced the Case
    Factory to invent a session.
    """
    uid = _user(make_account)
    with repo_scope(AuthenticatedUser(uid)) as db:
        db.llm_calls.record_call(_Call(purpose="extraction"), session_id=None)

    assert _rows(app_db)[0]["session_id"] is None


def test_the_cost_keeps_its_six_decimal_places(app_db, make_account):
    """
    A single patient turn costs fractions of a cent. Rounded to four places it
    would store as zero, and the cost dashboard would read zero for a product
    that was spending money.
    """
    uid = _user(make_account)
    with repo_scope(AuthenticatedUser(uid)) as db:
        db.llm_calls.record_call(_Call(cost_usd=Decimal("0.000123")))

    assert _rows(app_db)[0]["cost_usd"] == Decimal("0.000123")


def test_a_retried_call_records_the_attempt_it_succeeded_on(app_db, make_account):
    uid = _user(make_account)
    with repo_scope(AuthenticatedUser(uid)) as db:
        db.llm_calls.record_call(_Call(status="retried", attempt=3))

    row = _rows(app_db)[0]
    assert row["status"] == "retried"
    assert row["attempt"] == 3


# ── the purpose catalogue ────────────────────────────────────────────

@pytest.mark.parametrize("purpose", sorted(PURPOSES))
def test_every_catalogued_purpose_is_accepted_by_the_check(
        app_db, make_account, purpose):
    """
    `PURPOSES` mirrors migration 015's CHECK. If the two drift, the catalogue
    is worse than no catalogue: it would refuse a purpose the column allows,
    or wave through one it does not.
    """
    uid = _user(make_account)
    with repo_scope(AuthenticatedUser(uid)) as db:
        db.llm_calls.record_call(_Call(purpose=purpose))

    assert _rows(app_db)[0]["purpose"] == purpose


def test_playtest_is_refused_in_python_not_by_the_constraint(make_account):
    """
    Playtest passes `purpose="playtest"` to the gateway, which is right for the
    log line and absent from migration 015's CHECK. The route records nothing,
    so this never fires in production — but a CheckViolation here would abort a
    transaction opened for work that mattered more, and name a constraint
    rather than the mistake.
    """
    uid = _user(make_account)
    with repo_scope(AuthenticatedUser(uid)) as db:
        with pytest.raises(UnaccountablePurpose, match="playtest"):
            db.llm_calls.record_call(_Call(purpose="playtest"))


def test_the_catalogue_matches_the_constraint_exactly(app_db):
    """
    Read the CHECK out of the catalog and compare. The parametrised test above
    proves every catalogued purpose is allowed; this proves there is no
    allowed purpose the catalogue has forgotten — the direction that would let
    a real cost bucket go unaccounted.
    """
    with app_db.begin() as c:
        clause = c.execute(sa.text("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = 'llm_calls'::regclass
              AND pg_get_constraintdef(oid) LIKE '%purpose%'
        """)).scalar_one()

    # Postgres normalises `IN (...)` to `= ANY (ARRAY[...])`, so the literals
    # are pulled out by pattern rather than by slicing between brackets.
    in_constraint = set(re.findall(r"'([a-z_]+)'::text", clause))
    assert in_constraint == set(PURPOSES), clause


# ── who may write one ────────────────────────────────────────────────

def test_a_reviewer_cannot_record_a_call(app_db, make_account):
    """
    Migration 024's own words. The reviewer role is the narrowest one in the
    product and `llm_calls` was kept out of it on purpose; this is the test
    the Playtest comment leans on.
    """
    uid = make_account()
    with app_db.begin() as c:
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, platform_role, timezone) "
            "VALUES (:id, 'Dr Fixture', 'reviewer', 'UTC')"), {"id": uid})

    with repo_scope(ReviewerUser(uid)) as db:
        with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
            db.llm_calls.record_call(_Call())


def test_a_trial_visitor_s_calls_are_recorded_too(app_db, published_case):
    """
    The unauthenticated path is the one whose cost someone would watch — free,
    rate-limited, and the obvious thing to abuse. Leaving it out of `llm_calls`
    would make the dashboard under-report exactly that traffic.
    """
    from nidan.infra.db.repositories.anonymous import anonymous_scope

    cv = published_case()
    with anonymous_scope("trial-visitor-" + uuid.uuid4().hex[:8]) as db:
        session_id = db.sessions.create(cv)["id"]
        db.llm_calls.record_call(_Call(), session_id=session_id)

    row = _rows(app_db)[0]
    assert row["session_id"] == session_id
    assert row["purpose"] == "patient"
