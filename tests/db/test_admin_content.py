"""
T-044 · the clinical-content and topic-lexicon editors (`UX_SPEC` A-06, A-07).

One class per BUILD_PLAN criterion, plus the console's standing obligations:
404 for everyone who is not an administrator, and an audit row for every
write.

**These tests clean up master-list rows themselves.** `app_db` truncates the
data tables but not `examinations` / `investigations`, and
`tests/db/test_seed.py` asserts those equal `cases.py`. A row left behind here
would fail a test about seeding, two files away, in whichever order pytest
picked.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from nidan.domain.assessment.topics import TOPIC_KEYWORDS
from nidan.infra.db.actor import AdminUser, AuthenticatedUser
from nidan.infra.db.repositories import repo_scope
from tests.app_config import TEST_SECRET

ADMIN_ID = uuid.UUID("0000c0c0-0000-4000-8000-00000000ad01")
LEARNER_ID = uuid.UUID("0000c0c0-0000-4000-8000-00000000be02")
NEW_KEY = "zz_test_troponin"


@pytest.fixture
def client(app_db):
    return create_app({"TESTING": True, "SECRET_KEY": TEST_SECRET}).test_client()


@pytest.fixture
def profile(app_db):
    def _make(user_id: uuid.UUID, *, role: str = "user") -> uuid.UUID:
        with app_db.begin() as c:
            c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id) "
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
def admin(profile, authority):
    profile(ADMIN_ID, role="admin")
    return {"Authorization": f"Bearer {authority.token(sub=str(ADMIN_ID))}"}


@pytest.fixture(autouse=True)
def _restore_master_lists(app_db):
    yield
    with app_db.begin() as c:
        for table in ("examinations", "investigations"):
            c.execute(sa.text(f"DELETE FROM {table} WHERE key LIKE 'zz_test_%'"))  # noqa: S608
        c.execute(sa.text(
            "UPDATE topic_phrases SET match_count = 0, last_matched_at = NULL"))


def _audits(app_db, action: str) -> list:
    with app_db.connect() as c:
        return c.execute(sa.text(
            "SELECT actor_id, metadata FROM audit_log WHERE action = :a"),
            {"a": action}).all()


def _add(client, admin, **over):
    data = {"key": NEW_KEY, "label": "High-sensitivity troponin (test)",
            "group_name": "Cardiac", "normal_result": "< 14 ng/L",
            "reference_range": "0–14 ng/L", **over}
    return client.post("/admin/content/investigations", data=data, headers=admin)


class TestRefusals:

    @pytest.mark.parametrize("path", [
        "/admin/content/investigations", "/admin/content/examinations/new",
        "/admin/content/lexicon",
    ])
    def test_a_learner_gets_the_same_404_as_nobody(self, client, profile,
                                                   authority, path):
        profile(LEARNER_ID)
        learner = {"Authorization": f"Bearer {authority.token(sub=str(LEARNER_ID))}"}
        signed_in, anonymous = client.get(path, headers=learner), client.get(path)
        assert signed_in.status_code == anonymous.status_code == 404
        assert signed_in.data == anonymous.data

    def test_a_learner_cannot_add_an_item(self, client, profile, authority):
        profile(LEARNER_ID)
        r = client.post("/admin/content/investigations",
                        data={"key": NEW_KEY, "label": "x", "group_name": "x",
                              "normal_result": "x"},
                        headers={"Authorization":
                                 f"Bearer {authority.token(sub=str(LEARNER_ID))}"})
        assert r.status_code == 404

    def test_an_unknown_table_is_a_404_not_an_error(self, client, admin):
        assert client.get("/admin/content/profiles", headers=admin).status_code == 404


class TestCriterion1_CrudWithoutDelete:

    def test_lists_every_item_with_how_many_cases_use_it(self, client, admin):
        r = client.get("/admin/content/investigations", headers=admin)
        assert r.status_code == 200
        page = r.get_data(as_text=True)
        assert "<code>ecg</code>" in page
        # The ten seeded cases are drafts. "Used by" counts them anyway, or
        # every item would read "0 cases" on the day it matters most.
        assert re.search(r"<code>ecg</code>.*?(\d+) cases?", page, re.S).group(1) != "0"

    def test_adding_puts_it_on_the_learners_menu_and_audits_it(
            self, client, admin, app_db):
        r = _add(client, admin)
        assert r.status_code == 303
        with repo_scope(AdminUser(user_id=ADMIN_ID)) as db:
            menu = [m["key"] for m in db.catalog.investigations()]
            entry = db.catalog.master_entry("investigations", NEW_KEY)
        assert menu[-1] == NEW_KEY, "a new item goes at the end of the menu"
        assert entry["normal_result"] == "< 14 ng/L"
        [(actor, meta)] = _audits(app_db, "master_list.item_added")
        assert actor == ADMIN_ID and meta["key"] == NEW_KEY

    def test_a_reused_key_is_a_sentence_not_a_crash(self, client, admin):
        _add(client, admin)
        r = _add(client, admin, label="Again")
        assert r.status_code == 400
        assert "already in use" in r.get_data(as_text=True)

    def test_a_malformed_key_is_refused(self, client, admin):
        r = _add(client, admin, key="Troponin HS")
        assert r.status_code == 400
        assert "lowercase letters" in r.get_data(as_text=True)

    def test_editing_never_changes_the_key(self, client, admin):
        _add(client, admin)
        r = client.post(f"/admin/content/investigations/{NEW_KEY}",
                        data={"key": "zz_test_renamed", "label": "Renamed",
                              "group_name": "Cardiac", "normal_result": "normal"},
                        headers=admin)
        assert r.status_code == 303
        with repo_scope(AdminUser(user_id=ADMIN_ID)) as db:
            assert db.catalog.admin_entry("investigations", NEW_KEY)["label"] == "Renamed"
            assert db.catalog.admin_entry("investigations", "zz_test_renamed") is None

    def test_delete_is_not_offered_and_the_database_refuses_it(
            self, client, admin, app_db):
        page = client.get("/admin/content/investigations", headers=admin).get_data(as_text=True)
        assert "Delete" not in page
        with app_db.begin() as c:
            c.exec_driver_sql("SET LOCAL ROLE nidan_admin")
            with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
                c.exec_driver_sql("DELETE FROM investigations WHERE key = 'ecg'")

    def test_retiring_removes_it_from_the_menu_only(self, client, admin, app_db):
        _add(client, admin)
        r = client.post(f"/admin/content/investigations/{NEW_KEY}/active",
                        data={"active": "0"}, headers=admin)
        assert r.status_code == 303
        with repo_scope(AdminUser(user_id=ADMIN_ID)) as db:
            assert NEW_KEY not in [m["key"] for m in db.catalog.investigations()]
            assert db.catalog.master_entry("investigations", NEW_KEY) is None
            assert db.catalog.admin_entry("investigations", NEW_KEY)["is_active"] is False
        assert _audits(app_db, "master_list.item_retired")

    def test_retiring_a_used_item_needs_confirmation(self, client, admin):
        r = client.post("/admin/content/investigations/ecg/active",
                        data={"active": "0"}, headers=admin)
        assert r.status_code == 409
        assert "case(s)" in r.get_data(as_text=True)
        with repo_scope(AdminUser(user_id=ADMIN_ID)) as db:
            assert db.catalog.admin_entry("investigations", "ecg")["is_active"] is True


class TestCriterion2_TheWarning:

    def test_the_add_form_says_every_case_returns_the_normal_result(
            self, client, admin):
        page = client.get("/admin/content/investigations/new",
                          headers=admin).get_data(as_text=True)
        assert "This appears on every case immediately" in page
        with repo_scope(AdminUser(user_id=ADMIN_ID)) as db:
            n = db.catalog.case_count()
        assert f"all {n} current cases will return the normal result" in " ".join(page.split())
        assert "may hint at that diagnosis" in page

    def test_the_edit_form_does_not_repeat_it(self, client, admin):
        page = client.get("/admin/content/investigations/ecg/edit",
                          headers=admin).get_data(as_text=True)
        assert "every case immediately" not in page


class TestCriterion3_LexiconEditorAndTester:

    def test_the_page_lists_every_topic_from_the_code(self, client, admin):
        page = client.get("/admin/content/lexicon", headers=admin).get_data(as_text=True)
        assert f"{len(TOPIC_KEYWORDS)} topics" in page
        for key in TOPIC_KEYWORDS:
            assert f'value="{key}"' in page

    def test_the_tester_uses_the_engines_matcher(self, client, admin):
        r = client.post("/admin/content/lexicon/test", headers=admin, data={
            "topic": "meal_relationship",
            "question": "Does a rich evening dinner set it off?"})
        assert "NOT COVERED" in r.get_data(as_text=True)

    def test_a_proposed_phrase_changes_the_test_and_nothing_else(
            self, client, admin, app_db):
        r = client.post("/admin/content/lexicon", headers=admin, data={
            "action": "add_phrase", "topic": "meal_relationship",
            "phrase": "Evening Dinner"})
        page = r.get_data(as_text=True)
        assert "proposed for meal_relationship" in page
        assert 'value="meal_relationship::evening dinner"' in page   # normalised, carried
        r = client.post("/admin/content/lexicon/test", headers=admin, data={
            "topic": "meal_relationship", "add": "meal_relationship::evening dinner",
            "question": "Does a rich evening dinner set it off?"})
        assert "COVERED" in r.get_data(as_text=True)
        assert "NOT COVERED" not in r.get_data(as_text=True)
        with app_db.connect() as c:
            n = c.execute(sa.text("SELECT count(*) FROM topic_phrases "
                                  "WHERE phrase = 'evening dinner'")).scalar()
        assert n == 0, "the editor proposes; it never writes the lexicon"

    def test_a_two_letter_phrase_is_refused(self, client, admin):
        page = client.post("/admin/content/lexicon", headers=admin, data={
            "action": "add_phrase", "topic": "meal_relationship", "phrase": "ea",
        }).get_data(as_text=True)
        assert "at least 3 characters" in page
        assert "meal_relationship::ea" not in page

    def test_export_is_audited_and_downloadable(self, client, admin, app_db):
        data = {"add": "meal_relationship::evening dinner",
                "new_topic": "zz_night_sweats::Night sweats"}
        data_with_phrase = {**data, "add": [data["add"], "zz_night_sweats::sweats at night"]}
        r = client.post("/admin/content/lexicon/export", headers=admin,
                        data=data_with_phrase)
        assert r.status_code == 200
        page = r.get_data(as_text=True)
        assert "_lexicon_edit.py" in page and "TOPIC_KEYWORDS" in page
        assert _audits(app_db, "lexicon.export_generated")
        d = client.post("/admin/content/lexicon/export.py", headers=admin,
                        data=data_with_phrase)
        assert d.headers["Content-Disposition"].startswith("attachment;")
        compile(d.get_data(as_text=True), "generated.py", "exec")

    def test_a_topic_left_empty_blocks_the_export(self, client, admin):
        r = client.post("/admin/content/lexicon/export", headers=admin,
                        data={"new_topic": "zz_empty::Empty"})
        assert r.status_code == 400
        assert "would have no phrases left" in r.get_data(as_text=True)


class TestCriterion4_DeadPhrases:

    def test_before_the_job_has_run_it_says_so(self, client, admin):
        page = client.get("/admin/content/lexicon", headers=admin).get_data(as_text=True)
        assert "Match counts have not been computed yet" in page
        assert "no match 90 d" not in page, "never-counted is not the same as dead"

    def test_after_the_job_it_reports_and_marks_dead_phrases(
            self, client, admin, app_db, profile, published_case):
        from nidan.jobs.lexicon import count_matches
        learner = profile(LEARNER_ID)
        with repo_scope(AuthenticatedUser(user_id=learner)) as db:
            sid = db.sessions.create(case_version_id=published_case())["id"]
            db.events.append(sid, "question",
                             {"text": "Is it worse after eating?", "char_count": 25})
        report = count_matches()
        assert report.questions == 1 and report.matched >= 1

        page = client.get("/admin/content/lexicon?topic=meal_relationship",
                          headers=admin).get_data(as_text=True)
        assert "have not matched a learner" in page
        with app_db.connect() as c:
            row = c.execute(sa.text(
                "SELECT match_count, last_matched_at FROM topic_phrases p "
                "JOIN topic_lexicon l ON l.id = p.topic_id "
                "WHERE l.topic_key = 'meal_relationship' AND phrase = 'after eating'"
            )).one()
        assert row.match_count == 1
        assert row.last_matched_at > datetime.now(UTC) - timedelta(minutes=5)
        assert "no match 90 d" in page   # every other phrase in the topic

    def test_the_job_stores_counts_and_never_text(self, app_db, profile,
                                                  published_case):
        from nidan.jobs.lexicon import count_matches
        learner = profile(LEARNER_ID)
        secret = "unique-sentinel-words after eating"
        with repo_scope(AuthenticatedUser(user_id=learner)) as db:
            sid = db.sessions.create(case_version_id=published_case())["id"]
            db.events.append(sid, "question", {"text": secret, "char_count": 30})
        count_matches()
        with app_db.connect() as c:
            dumped = c.execute(sa.text(
                "SELECT coalesce(string_agg(metadata::text, ' '), '') FROM audit_log "
                "WHERE action = 'lexicon.matches_counted'")).scalar()
        assert "sentinel" not in dumped

    def test_the_job_cannot_rewrite_a_phrase(self, app_db):
        with app_db.begin() as c:
            c.exec_driver_sql("SET LOCAL ROLE nidan_service")
            with pytest.raises(sa.exc.ProgrammingError, match="permission denied"):
                c.exec_driver_sql("UPDATE topic_phrases SET phrase = 'x'")
