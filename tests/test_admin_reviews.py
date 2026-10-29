"""
Clinical review (BUILD_PLAN T-023, UX_SPEC §12.6).

Against a real database. The two tests the brief singles out:

- `test_an_approval_with_any_score_below_4_is_refused` — the rubric floor, at
  the route and, with the route's own check bypassed, at the repository;
- `test_the_trigger_refuses_a_direct_publish` — the publication gate holds
  when the application is not involved at all.

Both were watched failing before being called done: see the T-023 build log.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from nidan.infra.db.repositories import ReviewerUser, repo_scope
from nidan.web.admin.reviews import routes as review_routes

pytestmark = pytest.mark.usefixtures("live_db")

GOOD = {"clinical_plausibility": 5, "internal_consistency": 4,
        "trap_validity": 5, "solvability": 4}


@pytest.fixture
def client(live_db, authority):
    return create_app({"TESTING": True, "SECRET_KEY": "t023"}).test_client()


@pytest.fixture
def account(live_db, authority):
    """(id, headers) for a new account with a platform role. Removed afterwards."""
    made: list[uuid.UUID] = []

    def _make(role: str = "reviewer", name: str | None = None):
        uid = uuid.uuid4()
        with live_db.begin() as c:
            c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": uid})
            c.execute(sa.text(
                "INSERT INTO profiles (id, platform_role, display_name) "
                "VALUES (:id, CAST(:r AS platform_role), :n)"),
                {"id": uid, "r": role, "n": name or f"Dr {role.title()}"})
        made.append(uid)
        return uid, {"Authorization": f"Bearer {authority.token(sub=str(uid))}"}

    yield _make

    with live_db.begin() as c:
        # TRUNCATE: audit_log and clinical_reviews refuse DELETE by design.
        c.exec_driver_sql("TRUNCATE audit_log, clinical_reviews, review_assignments")
        c.execute(sa.text("UPDATE case_versions SET status = 'draft', published_at = NULL "
                          "WHERE status = 'published'"))
        for uid in made:
            c.execute(sa.text("UPDATE cases SET created_by = NULL WHERE created_by = :id"),
                      {"id": uid})
            c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": uid})
            c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": uid})


@pytest.fixture
def draft(live_db):
    """The seeded chest-pain version — a draft, as all five seeded cases are."""
    with live_db.connect() as c:
        return c.execute(sa.text("""
            SELECT cv.case_id, cv.id, cv.status FROM case_versions cv
            JOIN cases c ON c.id = cv.case_id WHERE c.slug = 'chest-pain-gerd'
        """)).mappings().one()


def _record(client, headers, version_id, decision, scores=GOOD, comments=""):
    return client.post(f"/admin/reviews/{version_id}/record", headers=headers,
                       json={"decision": decision, "scores": scores,
                             "comments": comments})


def _decisions(live_db, version_id) -> list[str]:
    with live_db.connect() as c:
        return list(c.execute(sa.text(
            "SELECT decision FROM clinical_reviews WHERE case_version_id = :v"),
            {"v": version_id}).scalars())


def _status(live_db, version_id) -> str:
    with live_db.connect() as c:
        return c.execute(sa.text("SELECT status FROM case_versions WHERE id = :v"),
                         {"v": version_id}).scalar_one()


# ── 1. Access ────────────────────────────────────────────────────────

def test_the_queue_404s_identically_except_for_reviewers_and_admins(
        client, account, authority):
    reviewer, reviewer_h = account("reviewer")
    admin, admin_h = account("admin")
    _, learner_h = account("user")
    expired = {"Authorization": f"Bearer {authority.token(sub=str(reviewer), expires_in=-60)}"}

    assert client.get("/admin/reviews", headers=reviewer_h).status_code == 200
    assert client.get("/admin/reviews", headers=admin_h).status_code == 200

    refused = [client.get("/admin/reviews"),
               client.get("/admin/reviews", headers=learner_h),
               client.get("/admin/reviews", headers=expired)]
    assert {r.status_code for r in refused} == {404}
    assert len({r.get_data(as_text=True) for r in refused}) == 1


def test_a_reviewer_cannot_assign_publish_or_edit(client, account, draft):
    _, reviewer_h = account("reviewer")
    reviewer2, _ = account("reviewer")
    refused = [
        client.post("/admin/reviews/assign", headers=reviewer_h,
                    data={"case_version_id": str(draft["id"]), "reviewer_id": str(reviewer2)}),
        client.post(f"/admin/reviews/{draft['id']}/publish", headers=reviewer_h),
        client.get(f"/admin/cases/{draft['case_id']}/versions/{draft['id']}", headers=reviewer_h),
    ]
    assert {r.status_code for r in refused} == {404}


# ── Assignment, and criterion 1 ──────────────────────────────────────

def test_assigning_a_reviewer_writes_the_audit_log(client, account, draft, live_db):
    admin, admin_h = account("admin")
    reviewer, _ = account("reviewer", name="Dr Mehta")

    res = client.post("/admin/reviews/assign", headers=admin_h,
                      data={"case_version_id": str(draft["id"]), "reviewer_id": str(reviewer)})
    assert res.status_code == 302

    with live_db.connect() as c:
        row = c.execute(sa.text(
            "SELECT actor_id, action, entity_id, metadata FROM audit_log "
            "WHERE action = 'case_version.review_assigned'")).mappings().one()
    assert row["actor_id"] == admin
    assert row["entity_id"] == draft["id"]
    assert row["metadata"]["reviewer_id"] == str(reviewer)


def test_a_learner_cannot_be_assigned(client, account, draft, live_db):
    _, admin_h = account("admin")
    learner, _ = account("user")
    client.post("/admin/reviews/assign", headers=admin_h,
                data={"case_version_id": str(draft["id"]), "reviewer_id": str(learner)})
    with live_db.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM review_assignments")).scalar() == 0


def test_an_assigned_reviewer_sees_it_and_opens_the_draft_in_playtest(
        client, account, draft):
    _, admin_h = account("admin")
    reviewer, reviewer_h = account("reviewer")
    client.post("/admin/reviews/assign", headers=admin_h,
                data={"case_version_id": str(draft["id"]), "reviewer_id": str(reviewer)})

    queue = client.get("/admin/reviews?tab=mine", headers=reviewer_h).get_data(as_text=True)
    playtest = f"/admin/cases/{draft['case_id']}/versions/{draft['id']}/playtest?review=1"
    assert "Assigned to me (1)" in queue
    assert playtest in queue

    page = client.get(playtest, headers=reviewer_h)
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Student view" in html and "Clinical review" in html   # alongside
    assert "Publish this version" not in html                      # admin only


def test_the_author_is_warned_not_blocked(client, account, draft, live_db):
    reviewer, reviewer_h = account("reviewer")
    with live_db.begin() as c:
        c.execute(sa.text("UPDATE cases SET created_by = :r WHERE id = :c"),
                  {"r": reviewer, "c": draft["case_id"]})
    page = client.get(f"/admin/cases/{draft['case_id']}/versions/{draft['id']}/playtest?review=1",
                      headers=reviewer_h).get_data(as_text=True)
    assert "You created this case" in page
    assert _record(client, reviewer_h, draft["id"], "approved").status_code == 200


# ── 2. The rubric floor ──────────────────────────────────────────────

@pytest.mark.parametrize("dimension", list(GOOD))
def test_an_approval_with_any_score_below_4_is_refused(
        client, account, draft, live_db, dimension):
    _, reviewer_h = account("reviewer")
    res = _record(client, reviewer_h, draft["id"], "approved", {**GOOD, dimension: 3})
    assert res.status_code == 400
    assert "cannot be approved" in res.get_json()["error"]
    assert "approved" not in _decisions(live_db, draft["id"])


def test_the_repository_still_refuses_when_the_route_check_is_bypassed(
        client, account, draft, live_db, monkeypatch):
    """The route's check is the courtesy; the repository is the rule."""
    monkeypatch.setattr(review_routes, "check_rubric", lambda *a: None)
    _, reviewer_h = account("reviewer")
    res = _record(client, reviewer_h, draft["id"], "approved", {**GOOD, "trap_validity": 2})
    assert res.status_code == 400
    assert _decisions(live_db, draft["id"]) == []


def test_a_low_score_can_still_request_changes(client, account, draft, live_db):
    _, reviewer_h = account("reviewer")
    res = _record(client, reviewer_h, draft["id"], "changes_requested",
                  {**GOOD, "solvability": 2}, "The ECG result gives the answer away.")
    assert res.status_code == 200
    assert _decisions(live_db, draft["id"]) == ["changes_requested"]


# ── 3. Comments are required to say no ───────────────────────────────

@pytest.mark.parametrize("decision", ["changes_requested", "rejected"])
@pytest.mark.parametrize("comments", ["", "   "])
def test_saying_no_without_a_comment_is_refused(
        client, account, draft, live_db, decision, comments):
    _, reviewer_h = account("reviewer")
    res = _record(client, reviewer_h, draft["id"], decision, GOOD, comments)
    assert res.status_code == 400
    assert _decisions(live_db, draft["id"]) == []


# ── 4–6. Publishing ──────────────────────────────────────────────────

def test_publishing_without_an_approving_review_is_409(client, account, draft, live_db):
    _, admin_h = account("admin")
    _, reviewer_h = account("reviewer")
    _record(client, reviewer_h, draft["id"], "changes_requested", GOOD, "Not yet.")

    res = client.post(f"/admin/reviews/{draft['id']}/publish", headers=admin_h)
    assert res.status_code == 409
    assert "no approving clinical review" in res.get_json()["error"]
    assert _status(live_db, draft["id"]) == "draft"


def test_the_trigger_refuses_a_direct_publish(live_db, draft):
    """Bypass the application entirely. The database still says no."""
    with pytest.raises(sa.exc.DBAPIError, match="has no approving clinical review"):
        with live_db.begin() as c:
            c.execute(sa.text("UPDATE case_versions SET status = 'published', "
                              "published_at = now() WHERE id = :v"), {"v": draft["id"]})
    assert _status(live_db, draft["id"]) == "draft"


def test_publishing_with_an_approving_review_succeeds_and_is_audited(
        client, account, draft, live_db):
    admin, admin_h = account("admin")
    _, reviewer_h = account("reviewer")
    assert _record(client, reviewer_h, draft["id"], "approved").status_code == 200

    res = client.post(f"/admin/reviews/{draft['id']}/publish", headers=admin_h)
    assert res.status_code == 200
    assert _status(live_db, draft["id"]) == "published"
    with live_db.connect() as c:
        assert c.execute(sa.text(
            "SELECT actor_id FROM audit_log WHERE action = 'case_version.published'"
        )).scalar_one() == admin


def test_a_recorded_review_shows_on_the_completed_tab(client, account, draft):
    _, reviewer_h = account("reviewer", name="Dr Rao")
    _record(client, reviewer_h, draft["id"], "rejected", GOOD, "Trap is unfair.")
    html = client.get("/admin/reviews?tab=completed", headers=reviewer_h).get_data(as_text=True)
    assert "Rejected" in html and "Dr Rao" in html and "Trap is unfair." in html


# ── The read path added for reviewers ────────────────────────────────

def test_for_review_reads_a_draft_but_the_reviewer_role_cannot_write_it(
        account, draft):
    reviewer, _ = account("reviewer")
    with repo_scope(ReviewerUser(reviewer)) as db:
        row = db.cases.for_review(draft["id"])
    assert row["status"] == "draft" and row["content"]

    with pytest.raises(PermissionError):
        with repo_scope(ReviewerUser(reviewer)) as db:
            db.cases.update_draft(draft["id"], row["content"], expected_updated_at=None)

    with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
        with repo_scope(ReviewerUser(reviewer)) as db:
            db.conn.execute(sa.text("UPDATE case_versions SET title = 'x' WHERE id = :v"),
                            {"v": draft["id"]})
