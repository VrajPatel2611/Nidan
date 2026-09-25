"""
The case editor's write path (BUILD_PLAN T-021, migration 023).

Two things are being proved here, and they are not the same thing.

**That an administrator can author content.** Migration 020 granted the
application SELECT and nothing more on `cases` and `case_versions`, so until now
the editor had nowhere to save. `nidan_admin` is the role that can.

**That nobody else can** -- and specifically that the guarantee does not rest on
the Python check in `CaseRepository._require_admin`. `test_the_grant_is_the_
boundary_not_the_python_check` bypasses the repository entirely and issues the
INSERT as `nidan_app` over a raw connection. If that ever succeeds, every other
test in this file is decoration.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest
import sqlalchemy as sa

from nidan.infra.db.repositories import AdminUser, AuthenticatedUser, repo_scope
from nidan.infra.db.repositories.cases import (
    ConcurrentEdit,
    ContentInvariantViolation,
)


# A minimal but honest case payload: every field `_denormalised` needs, and a
# trap whose anchor keywords do not touch its clues.
def content(**overrides):
    base = {
        "title": "The Chest Pain Trap",
        "patient": {"name": "Ramesh Kumar", "age": 48, "sex": "male"},
        "correct_diagnosis": "GERD",
        "accepted_diagnoses": ["gerd", "acid reflux"],
        "anchor_topic": "cardiac / heart disease",
        "anchor_keywords": ["cardiac", "angina", "troponin"],
        "required_topics": ["pain_character", "meal_relationship"],
        "minimum_questions": 7,
        "contradictory_clues": [["burning"], ["ibuprofen"], ["antacid"],
                                ["lying flat"]],
        "investigations": {
            "ecg": {"category": "key", "result": "Normal sinus rhythm"},
            "ogd": {"category": "key", "result": "Erosive oesophagitis"},
            "fbc": {"category": "reasonable", "result": "Hb 138 g/L"},
        },
    }
    base.update(overrides)
    return base


@pytest.fixture
def admin_account(app_db):
    """A signed-in administrator: an auth user, a profile, `platform_role`."""
    uid = uuid.uuid4()
    with app_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": uid})
        c.execute(sa.text(
            "INSERT INTO profiles (id, platform_role) "
            "VALUES (:id, 'admin')"), {"id": uid})
    return uid


@pytest.fixture
def learner_account(app_db):
    uid = uuid.uuid4()
    with app_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": uid})
        c.execute(sa.text("INSERT INTO profiles (id) VALUES (:id)"), {"id": uid})
    return uid


# ── The role itself ──────────────────────────────────────────────────────

def test_the_admin_role_does_not_bypass_rls(app_db):
    """
    The difference between `nidan_admin` and `nidan_service`, in one row.

    A bypassing role would have been one line shorter in the migration and
    would have switched the safety net off for every statement an admin's
    request makes, including the ones touching `sessions` and `profiles`.
    """
    with app_db.begin() as c:
        bypasses = c.execute(sa.text(
            "SELECT rolbypassrls FROM pg_roles WHERE rolname = 'nidan_admin'"
        )).scalar()
    assert bypasses is False


def test_the_grant_is_the_boundary_not_the_python_check(app_db):
    """
    The application role cannot write a case version, repository or no
    repository.

    This is the test the rest of the file rests on. `_require_admin` raises a
    readable error at the right layer, but it is a courtesy: delete it and this
    must still fail.
    """
    with app_db.connect() as c:
        with c.begin():
            c.exec_driver_sql("SET LOCAL ROLE nidan_app")
            with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
                c.execute(sa.text(
                    "INSERT INTO cases (slug) VALUES ('smuggled-in')"))


def test_an_admin_cannot_delete_a_case_version(app_db, admin_account):
    """
    No DELETE grant. A case is retired by setting `retired_at`, which is an
    UPDATE, so DELETE has no legitimate caller and would only ever destroy
    clinical history that a `sessions` row still points at.
    """
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="deletable-case")
        version_id = db.cases.create_draft(case_id, content())

    with app_db.connect() as c:
        with c.begin():
            c.exec_driver_sql("SET LOCAL ROLE nidan_admin")
            with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
                c.execute(sa.text("DELETE FROM case_versions WHERE id = :id"),
                          {"id": version_id})


# ── Authoring ────────────────────────────────────────────────────────────

def test_an_admin_can_create_a_case_and_a_draft(app_db, admin_account):
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="chest-pain-trap", specialty="cardiology")
        version_id = db.cases.create_draft(case_id, content())

    with repo_scope(AdminUser(admin_account)) as db:
        row = db.cases.for_editing(version_id)

    assert row is not None
    assert row["status"] == "draft"
    assert row["version"] == 1
    assert row["slug"] == "chest-pain-trap"
    assert row["title"] == "The Chest Pain Trap"


def test_versions_are_numbered_one_past_the_highest(app_db, admin_account):
    """
    Editing a published version creates the next draft (`UX_SPEC` §12.4), so
    the numbering has to come from the table rather than from the caller.
    """
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="versioned-case")
        db.cases.create_draft(case_id, content())
        db.cases.create_draft(case_id, content(title="Second draft"))
        versions = [v["version"] for v in db.cases.versions(case_id)]

    assert versions == [2, 1]


def test_the_denormalised_columns_are_derived_not_supplied(app_db, admin_account):
    """
    `required_topic_count` and `key_investigation_count` are counted from the
    content, so the copy beside the JSON cannot drift from the JSON.
    """
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="derived-columns")
        version_id = db.cases.create_draft(case_id, content())

    with app_db.begin() as c:
        row = c.execute(sa.text(
            "SELECT required_topic_count, key_investigation_count, minimum_questions "
            "FROM case_versions WHERE id = :id"), {"id": version_id}).mappings().one()

    assert row["required_topic_count"] == 2      # two entries in required_topics
    assert row["key_investigation_count"] == 2   # ecg and ogd, not fbc
    assert row["minimum_questions"] == 7


def test_content_hash_is_the_canonical_sha256(app_db, admin_account):
    """
    The same rule `tests/db/test_seed.py` applies to the five seeded cases.
    A second hashing convention would make the column meaningless for
    near-duplicate detection, which is the one thing it is for.
    """
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="hashed-case")
        version_id = db.cases.create_draft(case_id, content())

    with app_db.begin() as c:
        stored, stored_hash = c.execute(sa.text(
            "SELECT content, content_hash FROM case_versions WHERE id = :id"),
            {"id": version_id}).one()

    if isinstance(stored, str):
        stored = json.loads(stored)
    expected = hashlib.sha256(json.dumps(
        stored, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()
    assert stored_hash == expected


# ── C-4, enforced at the write and not only in the form ──────────────────

def test_c4_violation_is_refused_and_names_the_terms(app_db, admin_account):
    """
    The 14%-sensitivity bug, made unstorable.

    "cardiac" as an anchor keyword against a clue containing "cardiac reflux"
    collides by substring — which is how the detector matches, and why a set
    intersection would let this through.
    """
    bad = content(contradictory_clues=[["burning"], ["cardiac reflux"],
                                       ["antacid"], ["lying flat"]])
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="c4-violating-case")
        with pytest.raises(ContentInvariantViolation) as exc:
            db.cases.create_draft(case_id, bad)

    message = str(exc.value)
    assert "C-4" in message
    assert "cardiac" in message


def test_c4_is_checked_on_update_too(app_db, admin_account):
    """A case can be saved clean and then broken. Both doors, or neither."""
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="c4-on-update")
        version_id = db.cases.create_draft(case_id, content())
        stamp = db.cases.for_editing(version_id)["updated_at"]

    bad = content(contradictory_clues=[["burning"], ["angina pectoris"],
                                       ["antacid"], ["lying flat"]])
    with repo_scope(AdminUser(admin_account)) as db:
        with pytest.raises(ContentInvariantViolation, match="C-4"):
            db.cases.update_draft(version_id, bad, expected_updated_at=stamp)


def test_missing_required_fields_are_named(app_db, admin_account):
    incomplete = content()
    del incomplete["anchor_topic"]
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="incomplete-case")
        with pytest.raises(ContentInvariantViolation, match="anchor_topic"):
            db.cases.create_draft(case_id, incomplete)


# ── Concurrency and immutability ─────────────────────────────────────────

def test_a_stale_updated_at_is_refused(app_db, admin_account):
    """
    Two authors with the same draft open. The second save must be told, not
    silently win — `UX_SPEC` §12.4's "changed by {name} 2 minutes ago".
    """
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="contested-case")
        version_id = db.cases.create_draft(case_id, content())
        stale = db.cases.for_editing(version_id)["updated_at"]

    with repo_scope(AdminUser(admin_account)) as db:
        db.cases.update_draft(version_id, content(title="First author wins"),
                              expected_updated_at=stale)

    with repo_scope(AdminUser(admin_account)) as db:
        with pytest.raises(ConcurrentEdit):
            db.cases.update_draft(version_id, content(title="Second author"),
                                  expected_updated_at=stale)

    with repo_scope(AdminUser(admin_account)) as db:
        assert db.cases.for_editing(version_id)["title"] == "First author wins"


def test_published_versions_cannot_be_updated(app_db, admin_account):
    """
    Published content is immutable. The database does not stop this one —
    `published_requires_timestamp` constrains the status, not the content — so
    the promise is this check.
    """
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="immutable-case")
        version_id = db.cases.create_draft(case_id, content())
        stamp = db.cases.for_editing(version_id)["updated_at"]

    # Publishing is T-023's gate and migration 007 holds it: this UPDATE is
    # refused outright without an approving review, which is the correct
    # behaviour and had to be satisfied rather than worked around to get a
    # published row at all.
    with app_db.begin() as c:
        c.execute(sa.text("""
            INSERT INTO clinical_reviews
                (case_version_id, reviewer_id, decision, scores)
            VALUES (:vid, :rid, 'approved', CAST(:scores AS jsonb))
        """), {"vid": version_id, "rid": admin_account,
                "scores": json.dumps({"clinical_plausibility": 5,
                                      "internal_consistency": 5,
                                      "trap_validity": 5, "solvability": 5,
                                      "rubric_version": "v1"})})
        c.execute(sa.text(
            "UPDATE case_versions SET status = 'published', published_at = now() "
            "WHERE id = :id"), {"id": version_id})

    with repo_scope(AdminUser(admin_account)) as db:
        with pytest.raises(ValueError, match="immutable"):
            db.cases.update_draft(version_id, content(title="Rewritten"),
                                  expected_updated_at=stamp)


# ── Who may read what ────────────────────────────────────────────────────

def test_a_learner_scope_cannot_author(app_db, learner_account):
    with repo_scope(AuthenticatedUser(learner_account)) as db:
        with pytest.raises(PermissionError, match="AdminUser"):
            db.cases.create_case(slug="learner-authored")


def test_a_learner_cannot_read_a_draft_but_an_admin_can(app_db, admin_account,
                                                        learner_account):
    """
    `read_published_cases` is `FOR SELECT USING (status = 'published')`, so a
    draft is invisible to `nidan_app`. `admin_manages_case_versions` is what
    lets the editor open one, and it is scoped `TO nidan_admin` so nothing any
    other role sees changes.
    """
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="unreviewed-case")
        version_id = db.cases.create_draft(case_id, content())

    with repo_scope(AdminUser(admin_account)) as db:
        assert db.cases.for_editing(version_id) is not None

    with repo_scope(AuthenticatedUser(learner_account)) as db:
        # Not merely filtered by the method's own WHERE: the policy denies it.
        assert db.cases.content(version_id) is None
        visible = db.conn.execute(sa.text(
            "SELECT count(*) FROM case_versions WHERE id = :id"),
            {"id": version_id}).scalar()
    assert visible == 0


def test_the_case_bank_shows_drafts(app_db, admin_account):
    """
    `published()` cannot serve the case bank: the five seeded cases are drafts
    on purpose, and would be missing from the one screen whose job is to show
    an author what there is to work on.
    """
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="draft-only-case")
        db.cases.create_draft(case_id, content())
        slugs = {row["slug"] for row in db.cases.bank()}
        published = {row["slug"] for row in db.cases.published()}

    assert "draft-only-case" in slugs
    assert "draft-only-case" not in published


# ── The reason the role exists at all ────────────────────────────────────

def test_an_admin_scope_can_write_an_attributed_audit_row(app_db, admin_account):
    """
    The requirement that ruled `ServiceActor` out.

    `UX_SPEC` §12 wants every admin action in `audit_log`, and
    `AuditRepository.record()` takes the actor from the scope. A service actor
    has no `user_id`, so this row could not have been written by one — it would
    have raised, or worse, recorded that something happened without saying who
    did it.
    """
    with repo_scope(AdminUser(admin_account)) as db:
        case_id = db.cases.create_case(slug="audited-case")
        version_id = db.cases.create_draft(case_id, content())
        db.audit.record("case_version.created", entity_type="case_version",
                        entity_id=version_id, reason="authoring a new case")

    with app_db.begin() as c:
        row = c.execute(sa.text(
            "SELECT actor_id, action FROM audit_log "
            "WHERE entity_id = :id"), {"id": version_id}).mappings().one()

    assert row["actor_id"] == admin_account
    assert row["action"] == "case_version.created"
