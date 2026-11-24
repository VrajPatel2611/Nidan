"""
The leakage queue screen (T-040 criterion 2, `TECH_SPEC` §5.3).

The repository is tested in `tests/db/test_leakage.py`. What is worth a route
test is the console's own obligations:

* the dashboard's "needs attention" figure is real, because it was a literal
  `2` for as long as the screen existed;
* confirming is **audited**, because it removes a session from the research
  export and the one question anyone will ask later is who decided it;
* the refusals are 404s like every other admin refusal (`UX_SPEC` §12.1), not
  403s that would confirm the console exists;
* a verdict that lost a race says so rather than silently overwriting.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from nidan.infra.db.actor import AdminUser, AuthenticatedUser
from nidan.infra.db.repositories import repo_scope
from tests.app_config import TEST_SECRET

ADMIN_ID = uuid.UUID("0000a0a0-0000-4000-8000-00000000ad01")
LEARNER_ID = uuid.UUID("0000a0a0-0000-4000-8000-00000000be02")


@pytest.fixture
def client(app_db):
    return create_app({"TESTING": True, "SECRET_KEY": TEST_SECRET}).test_client()


@pytest.fixture
def profile(app_db):
    def _make(user_id: uuid.UUID, *, role: str = "user") -> uuid.UUID:
        with app_db.begin() as c:
            c.execute(sa.text(
                "INSERT INTO auth.users (id) VALUES (:id) "
                "ON CONFLICT DO NOTHING"), {"id": user_id})
        with repo_scope(AuthenticatedUser(user_id=user_id)) as db:
            db.profiles.ensure(timezone="Europe/London")
        with app_db.begin() as c:
            c.execute(sa.text(
                "UPDATE profiles SET platform_role = CAST(:r AS platform_role) "
                "WHERE id = :id"), {"r": role, "id": user_id})
        return user_id
    return _make


@pytest.fixture
def flagged(app_db, profile, published_case):
    """
    A learner with one flagged reply. Returns the flag id.

    The reply event is appended so the queue has something to show — the words
    are read live from `session_events`, never copied onto the flag.
    """
    def _make(*, severity: str = "high"):
        learner = profile(LEARNER_ID)
        vid = published_case()
        with repo_scope(AuthenticatedUser(user_id=learner)) as db:
            sid = db.sessions.create(case_version_id=vid)["id"]
            db.events.append(sid, "question",
                             {"text": "Hello.", "char_count": 6})
            reply = db.events.append(
                sid, "patient_reply",
                {"text": "It spreads to my arm.", "matched_topics": []})
            db.leakage.record(sid, event_seq=reply.seq,
                              topics=["radiation"], severity=severity)
        with repo_scope(AdminUser(user_id=profile(ADMIN_ID, role="admin"))) as db:
            return db.leakage.queue()[0]["id"]
    return _make


def _auth(authority, user_id=ADMIN_ID):
    return {"Authorization": f"Bearer {authority.token(sub=str(user_id))}"}


class TestTheQueueScreen:

    def test_an_admin_sees_the_flag_and_the_patients_words(
            self, client, authority, profile, flagged):
        profile(ADMIN_ID, role="admin")
        flagged()
        r = client.get("/admin/leakage", headers=_auth(authority))
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert "radiation" in body
        assert "It spreads to my arm." in body

    def test_the_screen_explains_what_confirming_does(
            self, client, authority, profile, flagged):
        """
        Confirming excludes a consultation from the research export. An
        administrator should not have to know that from a build log.
        """
        profile(ADMIN_ID, role="admin")
        flagged()
        body = client.get("/admin/leakage",
                          headers=_auth(authority)).get_data(as_text=True)
        assert "research export" in body.lower()

    def test_it_uses_no_bias_vocabulary(self, client, authority, profile,
                                        flagged):
        """
        CT-5. "Leakage" and "persona" are ours, not the trainee's — but the
        screen describes the *effect* on a score, and that description must
        not reach for the banned words either (`PRD` P1). The console is
        internal; the habit is what keeps it out of learner-facing copy.
        """
        profile(ADMIN_ID, role="admin")
        flagged()
        body = client.get("/admin/leakage",
                          headers=_auth(authority)).get_data(as_text=True).lower()
        for banned in ("anchoring", "premature closure", "confirmation bias"):
            assert banned not in body

    def test_an_empty_queue_says_so_rather_than_erroring(
            self, client, authority, profile):
        profile(ADMIN_ID, role="admin")
        r = client.get("/admin/leakage", headers=_auth(authority))
        assert r.status_code == 200
        assert "Nothing to review" in r.get_data(as_text=True)

    def test_a_non_admin_gets_404_not_403(self, client, authority, profile,
                                          flagged):
        """
        `UX_SPEC` §12.1. A 403 tells someone probing that an admin console
        exists, and a difference between refusals is the same leak quieter.
        """
        profile(LEARNER_ID, role="user")
        r = client.get("/admin/leakage",
                       headers=_auth(authority, LEARNER_ID))
        assert r.status_code == 404

    def test_no_token_gets_the_same_404(self, client, profile):
        assert client.get("/admin/leakage").status_code == 404


class TestTheDashboardCount:

    def test_it_counts_real_flags(self, client, authority, profile, flagged):
        """
        This was the literal `2` until T-040. A hardcoded "needs attention"
        figure reads as a real backlog nobody can find, and as silence on the
        day there is one.
        """
        profile(ADMIN_ID, role="admin")
        flagged()
        body = client.get("/admin",
                          headers=_auth(authority)).get_data(as_text=True)
        assert "1 leakage flag unreviewed" in body

    def test_it_says_nothing_when_there_is_nothing(self, client, authority,
                                                   profile):
        profile(ADMIN_ID, role="admin")
        body = client.get("/admin",
                          headers=_auth(authority)).get_data(as_text=True)
        # The stat card always renders ("leakage flags to review"), so the
        # thing to assert absent is the attention line, not the phrase.
        assert "unreviewed" not in body
        assert "leakage flags to review" in body


class TestReviewing:

    def test_confirming_records_the_verdict_and_an_audit_row(
            self, client, authority, profile, flagged, app_db):
        profile(ADMIN_ID, role="admin")
        flag_id = flagged()

        r = client.post(f"/admin/leakage/{flag_id}",
                        data={"verdict": "confirm"}, headers=_auth(authority))
        assert r.status_code == 204

        with app_db.begin() as c:
            flag = c.execute(sa.text(
                "SELECT reviewed, confirmed, reviewed_by FROM leakage_flags "
                "WHERE id = :id"), {"id": flag_id}).mappings().first()
            audit = c.execute(sa.text(
                "SELECT action, entity_type, entity_id, reason, actor_id "
                "FROM audit_log WHERE action = 'leakage_flag.reviewed'"
            )).mappings().all()
        assert flag["reviewed"] is True
        assert flag["confirmed"] is True
        assert flag["reviewed_by"] == ADMIN_ID
        assert len(audit) == 1
        assert audit[0]["entity_id"] == flag_id
        assert audit[0]["actor_id"] == ADMIN_ID
        assert "research export" in audit[0]["reason"]

    def test_dismissing_is_audited_too_and_leaves_the_session_in(
            self, client, authority, profile, flagged, app_db):
        profile(ADMIN_ID, role="admin")
        flag_id = flagged()

        r = client.post(f"/admin/leakage/{flag_id}",
                        data={"verdict": "dismiss"}, headers=_auth(authority))
        assert r.status_code == 204

        with app_db.begin() as c:
            flag = c.execute(sa.text(
                "SELECT confirmed FROM leakage_flags WHERE id = :id"),
                {"id": flag_id}).mappings().first()
            reason = c.execute(sa.text(
                "SELECT reason FROM audit_log "
                "WHERE action = 'leakage_flag.reviewed'")).scalar()
        assert flag["confirmed"] is False
        assert "not a leak" in reason

    def test_a_second_verdict_is_a_409_rather_than_an_overwrite(
            self, client, authority, profile, flagged):
        profile(ADMIN_ID, role="admin")
        flag_id = flagged()
        first = client.post(f"/admin/leakage/{flag_id}",
                            data={"verdict": "confirm"},
                            headers=_auth(authority))
        second = client.post(f"/admin/leakage/{flag_id}",
                             data={"verdict": "dismiss"},
                             headers=_auth(authority))
        assert first.status_code == 204
        assert second.status_code == 409

    def test_a_learner_cannot_review(self, client, authority, profile,
                                     flagged):
        profile(LEARNER_ID, role="user")
        flag_id = flagged()
        r = client.post(f"/admin/leakage/{flag_id}",
                        data={"verdict": "confirm"},
                        headers=_auth(authority, LEARNER_ID))
        assert r.status_code == 404

    def test_a_flag_that_does_not_exist_is_a_409_not_a_500(
            self, client, authority, profile):
        profile(ADMIN_ID, role="admin")
        r = client.post(f"/admin/leakage/{uuid.uuid4()}",
                        data={"verdict": "confirm"}, headers=_auth(authority))
        assert r.status_code == 409
