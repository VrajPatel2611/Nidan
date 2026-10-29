"""
The clinical review workflow's data layer (BUILD_PLAN T-023, migration 024).

Three things Yogesh reported as blockers, each proved fixed and proved still
closed to the wrong role:

- a reviewer can read a **draft** and record a review (V-1)
- an assignment has somewhere to live (V-2)
- a version can be published, and refuses to be without an approval (V-3)

The permission tests go round the repository and issue the statement directly,
because the Python guards are a courtesy and the grants are the boundary.
"""

from __future__ import annotations

import json
import uuid

import pytest
import sqlalchemy as sa

from nidan.infra.db.repositories import (
    AdminUser,
    AuthenticatedUser,
    ReviewerUser,
    repo_scope,
)
from nidan.infra.db.repositories.cases import AlreadyPublished, PublicationBlocked
from nidan.infra.db.repositories.reviews import RubricViolation


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
        },
    }
    base.update(overrides)
    return base


GOOD_SCORES = {"clinical_plausibility": 5, "internal_consistency": 4,
               "trap_validity": 5, "solvability": 4}


def _account(app_db, platform_role="user"):
    uid = uuid.uuid4()
    with app_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": uid})
        c.execute(sa.text(
            "INSERT INTO profiles (id, platform_role) VALUES (:id, :role)"),
            {"id": uid, "role": platform_role})
    return uid


@pytest.fixture
def admin(app_db):
    return _account(app_db, "admin")


@pytest.fixture
def reviewer(app_db):
    return _account(app_db, "reviewer")


@pytest.fixture
def learner(app_db):
    return _account(app_db, "user")


@pytest.fixture
def draft(app_db, admin):
    """A draft version, authored by the admin, ready to be reviewed."""
    with repo_scope(AdminUser(admin)) as db:
        case_id = db.cases.create_case(slug=f"case-{uuid.uuid4().hex[:8]}")
        return case_id, db.cases.create_draft(case_id, content())


# ── V-1 · a reviewer can read a draft and record a review ────────────────

def test_a_reviewer_can_read_a_draft(app_db, reviewer, draft):
    """
    The blocker itself. `read_published_cases` is SELECT-only on published
    rows, so before migration 024 this returned nothing and Playtest had
    nothing to open.
    """
    _, version_id = draft
    with repo_scope(ReviewerUser(reviewer)) as db:
        row = db.conn.execute(sa.text(
            "SELECT status, title FROM case_versions WHERE id = :id"),
            {"id": version_id}).mappings().first()
    assert row is not None
    assert row["status"] == "draft"


def test_a_learner_still_cannot_read_a_draft(app_db, learner, draft):
    """The new policy is scoped `TO nidan_reviewer` and widens nothing else."""
    _, version_id = draft
    with repo_scope(AuthenticatedUser(learner)) as db:
        visible = db.conn.execute(sa.text(
            "SELECT count(*) FROM case_versions WHERE id = :id"),
            {"id": version_id}).scalar()
    assert visible == 0


def test_a_reviewer_can_record_a_review(app_db, reviewer, draft):
    _, version_id = draft
    with repo_scope(ReviewerUser(reviewer)) as db:
        review_id = db.reviews.record(
            version_id, decision="approved", scores=GOOD_SCORES,
            comments="Plausible and solvable.")

    with app_db.begin() as c:
        row = c.execute(sa.text(
            "SELECT reviewer_id, decision, scores FROM clinical_reviews "
            "WHERE id = :id"), {"id": review_id}).mappings().one()
    assert row["reviewer_id"] == reviewer
    assert row["decision"] == "approved"
    scores = row["scores"] if isinstance(row["scores"], dict) else json.loads(row["scores"])
    assert scores["rubric_version"] == "v1"


def test_the_grant_is_the_boundary_for_reviews(app_db):
    """`nidan_app` cannot insert a review however it is asked to."""
    with app_db.connect() as c:
        with c.begin():
            c.exec_driver_sql("SET LOCAL ROLE nidan_app")
            with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
                c.execute(sa.text(
                    "INSERT INTO clinical_reviews "
                    "(case_version_id, reviewer_id, decision, scores) "
                    "VALUES (gen_random_uuid(), gen_random_uuid(), "
                    "'approved', '{}'::jsonb)"))


def test_a_reviewer_cannot_write_clinical_content(app_db):
    """
    The reason this is a third role and not `nidan_admin`.

    A reviewer who could edit the case they are judging is not performing a
    review.
    """
    with app_db.connect() as c:
        with c.begin():
            c.exec_driver_sql("SET LOCAL ROLE nidan_reviewer")
            with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
                c.execute(sa.text("INSERT INTO cases (slug) VALUES ('sneaked-in')"))


def test_the_reviewer_role_does_not_bypass_rls(app_db):
    with app_db.begin() as c:
        bypasses = c.execute(sa.text(
            "SELECT rolbypassrls FROM pg_roles WHERE rolname = 'nidan_reviewer'"
        )).scalar()
    assert bypasses is False


# ── The rubric rule, enforced at the write ───────────────────────────────

def test_a_dimension_below_four_cannot_be_approved(app_db, reviewer, draft):
    """
    `PRD` FR-12.5. The screen disables the button; this is why that is not the
    only thing standing between a 2-out-of-5 case and publication.
    """
    _, version_id = draft
    weak = dict(GOOD_SCORES, trap_validity=2)
    with repo_scope(ReviewerUser(reviewer)) as db:
        with pytest.raises(RubricViolation) as exc:
            db.reviews.record(version_id, decision="approved", scores=weak)
    assert "trap validity scored 2" in str(exc.value)

    with app_db.begin() as c:
        approvals = c.execute(sa.text(
            "SELECT count(*) FROM clinical_reviews "
            "WHERE case_version_id = :v AND decision = 'approved'"),
            {"v": version_id}).scalar()
    assert approvals == 0


def test_the_same_scores_may_be_recorded_as_changes_requested(app_db, reviewer,
                                                              draft):
    """A 2 is not a blocked reviewer. It is a different decision."""
    _, version_id = draft
    weak = dict(GOOD_SCORES, trap_validity=2)
    with repo_scope(ReviewerUser(reviewer)) as db:
        db.reviews.record(version_id, decision="changes_requested", scores=weak,
                          comments="The trap is not convincing yet.")


def test_a_rejection_needs_a_comment(app_db, reviewer, draft):
    _, version_id = draft
    with repo_scope(ReviewerUser(reviewer)) as db:
        with pytest.raises(RubricViolation, match="needs a comment"):
            db.reviews.record(version_id, decision="rejected",
                              scores=dict(GOOD_SCORES, solvability=1))


def test_every_dimension_must_be_scored(app_db, reviewer, draft):
    _, version_id = draft
    partial = {"clinical_plausibility": 5, "internal_consistency": 5}
    with repo_scope(ReviewerUser(reviewer)) as db:
        with pytest.raises(RubricViolation, match="trap_validity"):
            db.reviews.record(version_id, decision="approved", scores=partial)


# ── V-2 · assignment ─────────────────────────────────────────────────────

def test_an_admin_assigns_and_the_reviewer_sees_it(app_db, admin, reviewer,
                                                   draft):
    _, version_id = draft
    with repo_scope(AdminUser(admin)) as db:
        db.reviews.assign(version_id, reviewer)

    with repo_scope(ReviewerUser(reviewer)) as db:
        mine = db.reviews.assigned_to_me()
    assert [row["case_version_id"] for row in mine] == [version_id]


def test_assigning_twice_is_a_no_op(app_db, admin, reviewer, draft):
    """The composite key makes it impossible; ON CONFLICT makes it painless."""
    _, version_id = draft
    with repo_scope(AdminUser(admin)) as db:
        db.reviews.assign(version_id, reviewer)
        db.reviews.assign(version_id, reviewer)

    with app_db.begin() as c:
        rows = c.execute(sa.text(
            "SELECT count(*) FROM review_assignments WHERE case_version_id = :v"),
            {"v": version_id}).scalar()
    assert rows == 1


def test_two_reviewers_can_hold_the_same_version(app_db, admin, draft):
    """
    The reason this is a table and not a column. The project has two
    clinicians, and `UX_SPEC` §12.6 shows both "Assigned to me" and "All
    pending".
    """
    _, version_id = draft
    first, second = _account(app_db, "reviewer"), _account(app_db, "reviewer")
    with repo_scope(AdminUser(admin)) as db:
        db.reviews.assign(version_id, first)
        db.reviews.assign(version_id, second)

    for who in (first, second):
        with repo_scope(ReviewerUser(who)) as db:
            assert len(db.reviews.assigned_to_me()) == 1


def test_a_reviewer_cannot_assign_themselves_work(app_db, reviewer, draft):
    _, version_id = draft
    with repo_scope(ReviewerUser(reviewer)) as db:
        with pytest.raises(PermissionError, match="AdminUser"):
            db.reviews.assign(version_id, reviewer)


def test_a_reviewed_version_leaves_my_queue_but_stays_pending(app_db, admin,
                                                              draft):
    """
    One of two reviewers finishing does not clear the version — it clears it
    for them.
    """
    _, version_id = draft
    first, second = _account(app_db, "reviewer"), _account(app_db, "reviewer")
    with repo_scope(AdminUser(admin)) as db:
        db.reviews.assign(version_id, first)
        db.reviews.assign(version_id, second)

    with repo_scope(ReviewerUser(first)) as db:
        db.reviews.record(version_id, decision="changes_requested",
                          scores=dict(GOOD_SCORES, solvability=3),
                          comments="Needs a clearer path to the diagnosis.")

    with repo_scope(ReviewerUser(first)) as db:
        assert db.reviews.assigned_to_me() == []
    with repo_scope(ReviewerUser(second)) as db:
        assert len(db.reviews.assigned_to_me()) == 1
    with repo_scope(AdminUser(admin)) as db:
        assert version_id in [r["case_version_id"] for r in db.reviews.pending()]


def test_unassigning_leaves_a_recorded_review_alone(app_db, admin, reviewer,
                                                    draft):
    _, version_id = draft
    with repo_scope(AdminUser(admin)) as db:
        db.reviews.assign(version_id, reviewer)
    with repo_scope(ReviewerUser(reviewer)) as db:
        db.reviews.record(version_id, decision="approved", scores=GOOD_SCORES)
    with repo_scope(AdminUser(admin)) as db:
        db.reviews.unassign(version_id, reviewer)
        assert db.reviews.has_approval(version_id) is True


def test_is_author_warns_rather_than_blocks(app_db, admin, draft):
    """
    `UX_SPEC` §12.6 warns and does not block — a two-person team sometimes has
    nobody else. The repository answers the question; the console shows it.
    """
    _, version_id = draft
    with repo_scope(AdminUser(admin)) as db:
        assert db.reviews.is_author(version_id, admin) is True


# ── V-3 · publishing ─────────────────────────────────────────────────────

def test_publishing_without_an_approval_is_refused(app_db, admin, draft):
    """
    Migration 007's trigger, surfaced as something a console can show.
    """
    _, version_id = draft
    with repo_scope(AdminUser(admin)) as db:
        assert db.reviews.has_approval(version_id) is False
        with pytest.raises(PublicationBlocked, match="no approving clinical review"):
            db.cases.publish(version_id)

    with app_db.begin() as c:
        status = c.execute(sa.text(
            "SELECT status FROM case_versions WHERE id = :id"),
            {"id": version_id}).scalar()
    assert status == "draft"


def test_publishing_with_an_approval_succeeds(app_db, admin, reviewer, draft):
    _, version_id = draft
    with repo_scope(ReviewerUser(reviewer)) as db:
        db.reviews.record(version_id, decision="approved", scores=GOOD_SCORES)
    with repo_scope(AdminUser(admin)) as db:
        db.cases.publish(version_id)

    with app_db.begin() as c:
        row = c.execute(sa.text(
            "SELECT status, published_at FROM case_versions WHERE id = :id"),
            {"id": version_id}).mappings().one()
    assert row["status"] == "published"
    assert row["published_at"] is not None


def test_publishing_is_idempotent(app_db, admin, reviewer, draft):
    _, version_id = draft
    with repo_scope(ReviewerUser(reviewer)) as db:
        db.reviews.record(version_id, decision="approved", scores=GOOD_SCORES)
    with repo_scope(AdminUser(admin)) as db:
        db.cases.publish(version_id)
        db.cases.publish(version_id)          # no error, no second timestamp


def test_a_second_published_version_is_refused(app_db, admin, reviewer, draft):
    """`one_published_version_per_case`, as a typed exception."""
    case_id, first = draft
    with repo_scope(ReviewerUser(reviewer)) as db:
        db.reviews.record(first, decision="approved", scores=GOOD_SCORES)
    with repo_scope(AdminUser(admin)) as db:
        db.cases.publish(first)
        second = db.cases.create_draft(case_id, content(title="Version two"))
    with repo_scope(ReviewerUser(reviewer)) as db:
        db.reviews.record(second, decision="approved", scores=GOOD_SCORES)
    with repo_scope(AdminUser(admin)) as db:
        with pytest.raises(AlreadyPublished):
            db.cases.publish(second)


def test_a_reviewer_cannot_publish(app_db, reviewer, draft):
    _, version_id = draft
    with repo_scope(ReviewerUser(reviewer)) as db:
        with pytest.raises(PermissionError, match="AdminUser"):
            db.cases.publish(version_id)


# ── V-6 · listing reviewers, without the RLS bypass (migration 025) ──────

def test_an_admin_can_see_the_reviewers_they_may_assign(
        app_db, admin, reviewer):
    """
    The gap migration 025 closes.

    `own_profile` (migration 016) has no `TO` clause, so it bound
    `nidan_admin` like everyone else and the assign dropdown came back with
    only the administrator in it. The grant was never missing — migration 023
    gave `nidan_admin` SELECT on every table — so this failed in a way that
    looks nothing like a permissions problem.
    """
    with repo_scope(AdminUser(admin)) as db:
        ids = {p["id"] for p in db.reviews.reviewers()}
    assert reviewer in ids, "the reviewer to assign is invisible"
    assert admin in ids, "admins are assignable too"


def test_a_reviewer_can_resolve_their_colleagues_names(
        app_db, reviewer, admin):
    """
    Why the policy names `nidan_reviewer` as well.

    `UX_SPEC` §12.6 shows who reviewed a version on the Completed tab, so a
    reviewer resolves `reviewer_id` to a name on rows they already see.
    Admin-only would have meant keeping the bypass or rendering 'a reviewer'.
    """
    with repo_scope(ReviewerUser(reviewer)) as db:
        ids = {p["id"] for p in db.reviews.reviewers()}
    assert {reviewer, admin} <= ids


def test_the_policy_is_the_boundary_not_the_python_check(
        app_db, admin, learner):
    """
    **The test that matters.** Round the repository, straight at the role.

    If this passed only because `reviewers()` writes `WHERE platform_role IN
    (...)`, the narrowing would be a convention — one forgotten clause away
    from an admin screen listing every learner. The policy must refuse the
    row even when the SQL asks for everything.
    """
    with app_db.connect() as c:
        with c.begin():
            c.exec_driver_sql("SET LOCAL ROLE nidan_admin")
            c.execute(sa.text(
                "SELECT set_config('request.jwt.claim.sub', :me, true)"),
                {"me": str(admin)})
            visible = {r[0] for r in c.execute(sa.text("SELECT id FROM profiles"))}

    assert learner not in visible, (
        "a learner's profile is readable by nidan_admin — the policy is not "
        "doing the narrowing and the repository's WHERE clause is all that "
        "stands between an admin screen and everyone's row")
    assert admin in visible, "own_profile should still apply"


def test_a_learner_cannot_enumerate_privileged_accounts(
        app_db, learner, reviewer):
    """Migration 025 is scoped to two roles and widens nothing for `nidan_app`."""
    with app_db.connect() as c:
        with c.begin():
            c.exec_driver_sql("SET LOCAL ROLE nidan_app")
            c.execute(sa.text(
                "SELECT set_config('request.jwt.claim.sub', :me, true)"),
                {"me": str(learner)})
            visible = {r[0] for r in c.execute(sa.text("SELECT id FROM profiles"))}
    assert visible == {learner}


def test_a_soft_deleted_reviewer_is_not_assignable(app_db, admin, reviewer):
    """A dropdown is the wrong place to learn that an account once existed."""
    with app_db.begin() as c:
        c.execute(sa.text(
            "UPDATE profiles SET deleted_at = now() WHERE id = :id"),
            {"id": reviewer})
    with repo_scope(AdminUser(admin)) as db:
        assert reviewer not in {p["id"] for p in db.reviews.reviewers()}


def test_listing_reviewers_no_longer_takes_a_service_actor(app_db, learner):
    """
    The bypass is gone, and an ordinary scope still cannot do this.

    `ADR-0016` confined the RLS bypass to one module; this was briefly a
    second. The guard is now a plain refusal rather than an escalation.
    """
    with repo_scope(AuthenticatedUser(learner)) as db:
        with pytest.raises(PermissionError, match="AdminUser or ReviewerUser"):
            db.reviews.reviewers()
