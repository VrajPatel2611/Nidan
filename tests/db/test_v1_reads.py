"""
T-030 slice 2 · the read surface (`API_CONTRACT` §4, §5, §7).

Contract tests CT-3 and CT-9 live here, against a real PostgreSQL, because
both are properties of what the database hands back rather than of what a
handler remembers to filter:

- **CT-3** — the catalogue must carry no `category` or `is_key`. The menu is
  universal (`PRD` FR-5.1), so a menu that varied by case would *be* the
  answer.
- **CT-9** — another user's session is 404, never 403. Not asserted against a
  mock: the guarantee is migration 016's `own_sessions` policy, and a test
  that stubbed the repository would be testing the stub.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from tests.app_config import TEST_SECRET


@pytest.fixture
def app(live_db):
    return create_app({"TESTING": True, "SECRET_KEY": TEST_SECRET})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def account(live_db, authority):
    """A profile with a token for it, as the API's own endpoints would make."""
    user_id = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": user_id})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, timezone) "
            "VALUES (:id, 'Test Learner', 'UTC')"), {"id": user_id})

    yield user_id, {"Authorization": f"Bearer {authority.token(sub=str(user_id))}"}

    # Same reason as `published_version`: `live_db` truncates sessions, not
    # profiles, so without this every test in this file leaves an account
    # behind for whatever runs next to count.
    with live_db.begin() as c:
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": user_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": user_id})


# ── §5 · the catalogue, and CT-3 ─────────────────────────────────────

LEAKY_FIELDS = ("category", "is_key", "key_investigation", "relevance",
                "normal_result", "finding", "result")


@pytest.mark.parametrize("menu", ["examinations", "investigations"])
def test_ct3_the_catalogue_leaks_no_relevance(client, menu):
    """
    CT-3. `API_CONTRACT` §5, in bold: the response "must never include
    `category`, `is_key`, or any case-specific field."

    `normal_result` is in the list too, though no contract clause names it.
    It is the text a learner sees when they order an irrelevant test, and
    shipping all 91 of them up front would let a client diff them against what
    a case actually returns — which is the same leak by a longer route.
    """
    r = client.get(f"/v1/catalog/{menu}")
    assert r.status_code == 200
    items = r.get_json()["data"]
    assert items, "the menu is empty; migration 017 should have seeded it"
    for item in items:
        leaked = sorted(set(item) & set(LEAKY_FIELDS))
        assert not leaked, f"{item['key']} leaked {leaked}"
        assert set(item) == {"key", "label", "group", "display_order"}


def test_the_catalogue_needs_no_account(client):
    """§5: "anonymous or user". The trial has no account yet (`PRD` FR-2)."""
    assert client.get("/v1/catalog/examinations").status_code == 200


def test_the_catalogue_is_cacheable(client):
    """§5 names the header. It is requested on every consultation page load."""
    r = client.get("/v1/catalog/investigations")
    assert r.headers["Cache-Control"] == "public, max-age=3600"


def test_the_catalogue_is_ordered_for_display(client):
    """
    `display_order` is the order the chips appear in. Returned sorted so a
    client does not have to know that, and so two clients cannot disagree.
    """
    orders = [i["display_order"]
              for i in client.get("/v1/catalog/examinations").get_json()["data"]]
    assert orders == sorted(orders)


# ── §4 · PATCH /me ───────────────────────────────────────────────────

def test_patch_updates_only_what_was_sent(client, account, live_db):
    _, headers = account
    r = client.patch("/v1/me", json={"display_name": "Dr Changed"},
                     headers=headers)
    assert r.status_code == 200
    assert r.get_json()["display_name"] == "Dr Changed"
    assert r.get_json()["timezone"] == "UTC", "an unsent field was overwritten"


def test_patch_refuses_an_unknown_field(client, account):
    _, headers = account
    r = client.patch("/v1/me", json={"platform_role": "admin"}, headers=headers)
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "validation_failed"
    assert "platform_role" in r.get_json()["error"]["message"]


def test_patch_refuses_privilege_escalation_by_name(client, account, live_db):
    """
    The field above is not arbitrary. `platform_role` is what `require_admin`
    reads, so a PATCH that accepted it would be the whole admin console.
    """
    user_id, headers = account
    client.patch("/v1/me", json={"platform_role": "admin"}, headers=headers)
    with live_db.connect() as c:
        role = c.execute(sa.text(
            "SELECT platform_role::text FROM profiles WHERE id = :id"),
            {"id": user_id}).scalar()
    assert role == "user"


def test_consent_without_a_version_is_refused_with_its_own_code(client, account):
    """
    §4 gives this its own code, `consent_version_required` — which was
    referenced there and missing from the §10 catalogue until this endpoint
    was written. Consent to an unnamed document is not consent.
    """
    _, headers = account
    r = client.patch("/v1/me", json={"consent_research": True}, headers=headers)
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "consent_version_required"


def test_consent_with_a_version_is_recorded_with_a_server_timestamp(
        client, account, live_db):
    """
    `consent_at` is stamped by the server. A caller that could choose it could
    backdate a consent, and the row is the record that it was given.
    """
    user_id, headers = account
    r = client.patch("/v1/me",
                     json={"consent_research": True, "consent_version": "v2"},
                     headers=headers)
    assert r.status_code == 200
    with live_db.connect() as c:
        row = c.execute(sa.text(
            "SELECT consent_research, consent_version, consent_at "
            "FROM profiles WHERE id = :id"), {"id": user_id}).mappings().one()
    assert row["consent_research"] is True
    assert row["consent_version"] == "v2"
    assert row["consent_at"] is not None


def test_patch_on_a_missing_profile_is_404_not_a_create(client, authority, live_db):
    """
    §4 gives `POST /me` the job of creating one. A PATCH that created one
    quietly would make the two interchangeable for a client that got its order
    wrong — and the created row would have no `research_pid` generation or
    trial claim behind it.
    """
    stranger = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                  {"id": stranger})
    r = client.patch("/v1/me", json={"display_name": "Nobody"},
                     headers={"Authorization": f"Bearer {authority.token(sub=str(stranger))}"})
    assert r.status_code == 404
    with live_db.connect() as c:
        assert c.execute(sa.text(
            "SELECT count(*) FROM profiles WHERE id = :id"),
            {"id": stranger}).scalar() == 0


# ── §7 · GET /sessions, and CT-9 ─────────────────────────────────────

@pytest.fixture
def published_version(live_db):
    """
    A published case version, which `sessions.case_version_id` references.

    **Published the way the product publishes**, which took a correction: the
    first version of this fixture flipped `status` directly and migration
    007's `require_clinical_approval` trigger refused it —

        Case version f30d1a52… has no approving clinical review

    — which is the gate doing its job to a test that had not earned it. A
    reviewer and an approving `clinical_reviews` row come first, so the
    fixture exercises the same path a clinician does rather than a shortcut
    only a test can take.

    Published rather than draft because a learner's session pins something a
    clinician approved, and a draft would have worked here and hidden that.
    """
    reviewer_id = uuid.uuid4()
    with live_db.begin() as c:
        version_id = c.execute(sa.text(
            "SELECT id FROM case_versions ORDER BY created_at LIMIT 1")).scalar()
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                  {"id": reviewer_id})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, platform_role, timezone) "
            "VALUES (:id, 'Dr Fixture', 'reviewer', 'UTC')"), {"id": reviewer_id})
        # Every dimension at or above the approval floor of 4 (`DATA_MODEL`
        # §8.4). Below it the application refuses to record an approval, so a
        # fixture with a 3 would be approving something the product would not.
        c.execute(sa.text("""
            INSERT INTO clinical_reviews (case_version_id, reviewer_id,
                                          decision, scores)
            VALUES (:vid, :rid, 'approved', CAST(:scores AS jsonb))
        """), {"vid": version_id, "rid": reviewer_id,
               "scores": '{"clinical_plausibility": 5, "internal_consistency": 4,'
                         ' "trap_validity": 5, "solvability": 4,'
                         ' "rubric_version": "v1"}'})
        c.execute(sa.text(
            "UPDATE case_versions SET status = 'published', published_at = now() "
            "WHERE id = :id"), {"id": version_id})

    yield version_id

    # Undone explicitly, because `live_db` cannot do it. Its teardown
    # truncates sessions and results, but this fixture publishes a case
    # version that migration 019 seeded — a row older than the test — and
    # `clinical_reviews` is not in its truncate list either.
    #
    # Found the honest way: `test_a_draft_version_is_playtestable` passed
    # alone and failed in the full suite, because it looked for a draft and
    # found the one this fixture had published. A fixture that mutates seeded
    # content and does not put it back is a test that breaks a different file.
    with live_db.begin() as c:
        c.execute(sa.text(
            "DELETE FROM clinical_reviews WHERE reviewer_id = :rid"),
            {"rid": reviewer_id})
        c.execute(sa.text(
            "UPDATE case_versions SET status = 'draft', published_at = NULL "
            "WHERE id = :id"), {"id": version_id})
        c.execute(sa.text("DELETE FROM profiles WHERE id = :rid"),
                  {"rid": reviewer_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :rid"),
                  {"rid": reviewer_id})


@pytest.fixture
def stranger(live_db, authority):
    """
    A second account, for the tenant-isolation tests.

    A profile and not just a token: `require_auth` reads `platform_role` from
    the row, so a token with no profile behind it fails earlier and for the
    wrong reason — which would make a CT-9 test pass without testing CT-9.
    """
    other = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": other})
        c.execute(sa.text(
            "INSERT INTO profiles (id, timezone) VALUES (:id, 'UTC')"),
            {"id": other})

    yield {"Authorization": f"Bearer {authority.token(sub=str(other))}"}

    with live_db.begin() as c:
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": other})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": other})


def _make_sessions(live_db, user_id, version_id, n, *, with_results=0):
    """`n` completed sessions, `with_results` of them scored."""
    ids = []
    with live_db.begin() as c:
        for i in range(n):
            sid = uuid.uuid4()
            c.execute(sa.text("""
                INSERT INTO sessions (id, user_id, case_version_id, sequence_index,
                                      status, started_at, ended_at)
                VALUES (:id, :uid, :vid, :seq, 'completed',
                        now() - (:i || ' minutes')::interval,
                        now() - (:i || ' minutes')::interval)
            """), {"id": sid, "uid": user_id, "vid": version_id,
                   "seq": i + 1, "i": i})
            if i < with_results:
                # Column list taken from the migrated schema, not from
                # memory: every NOT NULL column without a default must be
                # supplied, and the scorecards and key-investigation counters
                # are among them (`DATA_MODEL` §8.6).
                c.execute(sa.text("""
                    INSERT INTO session_results (
                        session_id, question_count, examination_count,
                        investigation_count, coverage_pct, topics_hit,
                        topics_missed, diagnosis_submitted, diagnosis_verdict,
                        anchoring_detected, anchoring_score,
                        premature_closure_detected, premature_closure_score,
                        confirmation_bias_detected, confirmation_bias_score,
                        bias_detail, exam_scorecard, investigation_scorecard,
                        key_investigations_done, key_investigations_total,
                        engine_version_id)
                    VALUES (:id, 9, 3, 4, 75.00, '{}', '{}', 'gerd', 'correct',
                            false, 0.1, false, 0.1, false, 0.1,
                            CAST('{}' AS jsonb), CAST('{}' AS jsonb),
                            CAST('{}' AS jsonb), 2, 4,
                            (SELECT id FROM engine_versions WHERE is_current))
                """), {"id": sid})
            ids.append(sid)
    return ids


def test_history_is_newest_first_with_the_case_title(
        client, account, live_db, published_version):
    user_id, headers = account
    _make_sessions(live_db, user_id, published_version, 3, with_results=3)

    body = client.get("/v1/sessions", headers=headers).get_json()
    assert len(body["data"]) == 3
    starts = [row["started_at"] for row in body["data"]]
    assert starts == sorted(starts, reverse=True), "not newest first"
    first = body["data"][0]
    assert first["case_title"], "no title; the case_versions join is not working"
    assert first["verdict"] == "correct"
    assert first["coverage_pct"] == 75.0, "Decimal did not become a JSON number"


def test_a_session_with_no_result_still_appears(
        client, account, live_db, published_version):
    """
    LEFT JOIN, deliberately. An abandoned consultation has no
    `session_results` row, and dropping it would hide the learner's own
    unfinished work from their own history.
    """
    user_id, headers = account
    _make_sessions(live_db, user_id, published_version, 2, with_results=1)

    rows = client.get("/v1/sessions", headers=headers).get_json()["data"]
    assert len(rows) == 2
    unscored = [r for r in rows if r["verdict"] is None]
    assert len(unscored) == 1
    assert unscored[0]["coverage_pct"] is None


def test_the_cursor_walks_the_whole_history_once(
        client, account, live_db, published_version):
    """
    The property §2.5 chose cursors for: every row exactly once, no
    duplicates and no gaps.
    """
    user_id, headers = account
    _make_sessions(live_db, user_id, published_version, 7)

    seen, cursor, pages = [], None, 0
    while True:
        url = "/v1/sessions?limit=3" + (f"&cursor={cursor}" if cursor else "")
        body = client.get(url, headers=headers).get_json()
        seen += [r["session_id"] for r in body["data"]]
        pages += 1
        cursor = body["pagination"]["next_cursor"]
        if not cursor:
            assert body["pagination"]["has_more"] is False
            break
        assert pages < 10, "the cursor is not advancing"

    assert len(seen) == 7
    assert len(set(seen)) == 7, "a session appeared on two pages"
    assert pages == 3


def test_the_last_page_reports_no_more(
        client, account, live_db, published_version):
    user_id, headers = account
    _make_sessions(live_db, user_id, published_version, 2)
    body = client.get("/v1/sessions?limit=5", headers=headers).get_json()
    assert body["pagination"] == {"next_cursor": None, "has_more": False}


def test_limit_is_clamped_not_refused(client, account, live_db, published_version):
    """
    §2.5 states a maximum, not a validation rule. A 422 for an optimistic
    limit would be refusing a request that is merely hopeful.
    """
    user_id, headers = account
    _make_sessions(live_db, user_id, published_version, 2)
    assert client.get("/v1/sessions?limit=5000", headers=headers).status_code == 200


def test_a_corrupt_cursor_is_refused_rather_than_ignored(client, account):
    """
    Silently restarting at page one makes an infinite scroll jump to the top
    with no error, which reads to a user as data loss.
    """
    _, headers = account
    r = client.get("/v1/sessions?cursor=not-a-cursor", headers=headers)
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "validation_failed"


def test_ct9_another_learners_sessions_are_invisible(
        client, account, live_db, published_version, stranger):
    """
    CT-9. §2.7: "404 rather than 403 for another user's resource. Returning
    403 confirms the resource exists."

    Here the collection form: a stranger's history is empty, not forbidden.
    Enforced by migration 016's `own_sessions` policy, not by a WHERE clause
    in the handler — `page()` deliberately has none, so a forgotten filter
    returns nothing rather than everything (`ADR-0016`).
    """
    user_id, _ = account
    _make_sessions(live_db, user_id, published_version, 3, with_results=3)

    r = client.get("/v1/sessions", headers=stranger)
    assert r.status_code == 200
    assert r.get_json()["data"] == [], "one learner can see another's history"


def test_history_needs_an_account(client):
    assert client.get("/v1/sessions").status_code == 401


# ── §6 · the case object, and CT-1 ───────────────────────────────────

# `PRD` FR-3.4's list, verbatim, plus the four `case_view.FORBIDDEN` adds for
# reasons given there. Spelled out rather than imported from the module under
# test: a test that asks the code what it should hide agrees with the code by
# construction.
FR_3_4_FORBIDDEN = (
    "correct_diagnosis", "anchor_topic", "anchor_keywords", "required_topics",
    "contradictory_clues", "investigations", "examination", "system_prompt",
    "accepted_diagnoses", "partial_diagnoses", "alternative_topics",
    "minimum_questions",
)


# Of those, the ones whose names cannot collide with a legitimate field. A
# raw-substring sweep of the body catches a leak nested anywhere, including
# inside a string — but only for terms that mean nothing else.
#
# `examination` and `investigations` are deliberately NOT in this set, and
# that is the whole subtlety: §6 requires `examinations_done` and
# `investigations_done` on the session payload, and `examination` is a
# substring of the first. The first version of this test swept the raw body
# for all twelve and failed on the response the contract asks for.
UNAMBIGUOUS = (
    "correct_diagnosis", "anchor_topic", "anchor_keywords",
    "contradictory_clues", "alternative_topics", "system_prompt",
    "accepted_diagnoses", "partial_diagnoses", "minimum_questions",
    "required_topics",
)


def _keys_at_every_depth(node, found=None):
    """
    Every key anywhere in the payload.

    Recursive because a leak three levels inside `case.patient` satisfies a
    shallow check on the top-level dict and still reaches the client.
    """
    found = set() if found is None else found
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            _keys_at_every_depth(value, found)
    elif isinstance(node, list):
        for item in node:
            _keys_at_every_depth(item, found)
    return found


def _assert_no_leak(response, where: str):
    """CT-1, both ways: exact keys at any depth, and unambiguous substrings."""
    body = response.get_json()
    leaked_keys = sorted(_keys_at_every_depth(body) & set(FR_3_4_FORBIDDEN))
    assert not leaked_keys, f"FR-3.4 keys in {where}: {leaked_keys}"

    raw = response.get_data(as_text=True)
    leaked_text = [t for t in UNAMBIGUOUS if t in raw]
    assert not leaked_text, f"FR-3.4 terms in the {where} body: {leaked_text}"


def _start_session(client, headers):
    r = client.post("/v1/sessions", json={"confidence_pre": 3}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_ct1_starting_a_session_leaks_nothing_about_the_case(
        client, account, published_version):
    """
    **CT-1.** `PRD` FR-3.4, which `API_CONTRACT` §11 calls "the leak that
    would invalidate everything".

    Asserted against the raw serialised body, not the parsed object. A key
    nested three levels down inside `case.patient` would satisfy a shallow
    check on `response["case"]` and still reach the client.

    A learner who can read `anchor_keywords` knows which questions the
    detector is watching for, and every measurement taken afterwards is of
    something else.
    """
    _, headers = account
    r = client.post("/v1/sessions", json={}, headers=headers)
    assert r.status_code == 201, r.get_json()
    _assert_no_leak(r, "POST /sessions")


def test_ct1_resuming_leaks_nothing_either(
        client, account, published_version):
    """
    The same assertion on `GET /sessions/{id}`.

    Both endpoints return a `case` object and `nidan/api/v1/case_view.py`
    exists so there is one serialiser — but "there is one" is a claim, and
    this is what makes it checkable. Two serialisers would both pass on the
    day they were written.
    """
    _, headers = account
    created = _start_session(client, headers)

    r = client.get(f"/v1/sessions/{created['session_id']}", headers=headers)
    assert r.status_code == 200, r.get_json()
    _assert_no_leak(r, "GET /sessions/{id}")


def test_the_case_object_carries_what_a_learner_needs(
        client, account, published_version):
    """
    The other half of CT-1, and the half a deny-list would pass vacuously.

    A serialiser that returned `{}` leaks nothing and is also useless; the
    learner cannot start without knowing who walked in.
    """
    _, headers = account
    case = _start_session(client, headers)["case"]
    assert set(case) == {"title", "patient", "opening_line"}
    assert case["title"]
    assert set(case["patient"]) == {"name", "age", "sex",
                                    "presenting_complaint", "intro"}


def test_starting_a_session_matches_the_contracts_field_names(
        client, account, published_version):
    """
    §6 names `session_id`, not `id`.

    `openapi.yaml`'s Session schema said `id` until slice 2b and nothing
    compared the two halves of the contract, so both were "right" and a
    generated client would have been wrong.
    """
    body = _start_session(client, headers=account[1])
    assert "session_id" in body and "id" not in body
    assert body["sequence_index"] >= 1
    assert body["status"] == "active"
    assert body["transcript"] == []
    assert body["examinations_done"] == []
    assert body["investigations_done"] == []


def test_no_assessment_state_reaches_a_live_consultation(
        client, account, published_version):
    """
    CT-2 and `PRD` P2, on the responses rather than on the schema.

    `questions_remaining` is in this list and stays there: API-6 settled it
    as permanently absent on 11 Nov 2026. §6 had argued for it while citing
    `UX_SPEC` S-10, which lists "Question counter | U2" among what it says no
    one should add; §6 has been corrected, so the sources now agree. Removing
    this entry means reopening API-6, not fixing a test.
    """
    _, headers = account
    created = _start_session(client, headers)
    detail = client.get(f"/v1/sessions/{created['session_id']}",
                        headers=headers).get_data(as_text=True)

    for banned in ("coverage", "topics_covered", "topics_missed",
                   "matched_topics", "questions_remaining", "readiness",
                   "completeness", "anchoring", "premature", "confirmation"):
        assert banned not in detail, f"{banned!r} reached a live consultation"


def test_ct9_another_learners_session_is_404_not_403(
        client, account, published_version, stranger):
    """
    **CT-9.** §2.7: "404 rather than 403 for another user's resource.
    Returning 403 confirms the resource exists."

    Nothing in the handler implements this. `sessions.get()` carries no owner
    filter and migration 016's `own_sessions` policy returns no row, so the
    refusal takes the same path as a genuinely absent id — which is the only
    way the two can be indistinguishable (`ADR-0016`).
    """
    _, headers = account
    created = _start_session(client, headers)

    r = client.get(f"/v1/sessions/{created['session_id']}", headers=stranger)
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "not_found"

    absent = client.get(f"/v1/sessions/{uuid.uuid4()}", headers=headers)
    assert absent.status_code == 404
    assert absent.get_json() == r.get_json(), (
        "'not yours' and 'does not exist' are distinguishable")
