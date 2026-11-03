"""
T-030 slice 4 · concluding a consultation (`API_CONTRACT` §6).

Contract tests **CT-4**, **CT-5** and **CT-8** live here, and CT-5 is the one
that caught something real: the detectors' own `reason` strings contain the
words it forbids — "No significant anchoring pattern detected", "Confirmation
bias occurs when…" — so forwarding `bias_detail` would ship them to a learner.
`nidan/api/v1/reasoning.py` rebuilds the prose from `counters` instead.

**Several tests here assert values rather than shapes, on purpose.** Slices 2b
and 3 passed their own tests while badly broken: `cases.content()` returns the
case_versions ROW and the stored payload is its nested `content` key, so the
patient came back with every field None, the LLM got an empty system prompt,
and every examination returned the master normal result because the
case-specific block was never found. Every assertion was about keys being
present, and all of them held. The tests marked SUBSTANCE below are the ones
that would have failed.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from tests.app_config import TEST_SECRET, TRUNCATE_SESSION_TABLES


@pytest.fixture
def app(live_db):
    return create_app({"TESTING": True, "SECRET_KEY": TEST_SECRET})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def account(live_db, authority):
    user_id = uuid.uuid4()
    with live_db.begin() as c:
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": user_id})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, timezone) "
            "VALUES (:id, 'Test Learner', 'UTC')"), {"id": user_id})

    yield user_id, {"Authorization": f"Bearer {authority.token(sub=str(user_id))}"}

    with live_db.begin() as c:
        c.exec_driver_sql(TRUNCATE_SESSION_TABLES)
        c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": user_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": user_id})


@pytest.fixture
def published_version(live_db):
    """The chest-pain case, published through a real approving review."""
    reviewer_id = uuid.uuid4()
    with live_db.begin() as c:
        version_id = c.execute(sa.text(
            "SELECT cv.id FROM case_versions cv JOIN cases c ON c.id = cv.case_id "
            "WHERE c.slug = 'chest-pain-gerd'")).scalar_one()
        c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                  {"id": reviewer_id})
        c.execute(sa.text(
            "INSERT INTO profiles (id, display_name, platform_role, timezone) "
            "VALUES (:id, 'Dr Fixture', 'reviewer', 'UTC')"), {"id": reviewer_id})
        c.execute(sa.text("""
            INSERT INTO clinical_reviews (case_version_id, reviewer_id,
                                          decision, scores)
            VALUES (:vid, :rid, 'approved', CAST(:s AS jsonb))
        """), {"vid": version_id, "rid": reviewer_id,
               "s": '{"clinical_plausibility": 5, "internal_consistency": 4,'
                    ' "trap_validity": 5, "solvability": 4,'
                    ' "rubric_version": "v1"}'})
        c.execute(sa.text(
            "UPDATE case_versions SET status = 'published', published_at = now() "
            "WHERE id = :id"), {"id": version_id})

    yield version_id

    with live_db.begin() as c:
        c.execute(sa.text("DELETE FROM clinical_reviews WHERE reviewer_id = :r"),
                  {"r": reviewer_id})
        c.execute(sa.text(
            "UPDATE case_versions SET status = 'draft', published_at = NULL "
            "WHERE id = :id"), {"id": version_id})
        c.execute(sa.text("DELETE FROM profiles WHERE id = :r"), {"r": reviewer_id})
        c.execute(sa.text("DELETE FROM auth.users WHERE id = :r"), {"r": reviewer_id})


@pytest.fixture
def started(client, account, published_version):
    r = client.post("/v1/sessions", json={}, headers=account[1])
    assert r.status_code == 201, r.get_json()
    return r.get_json()


# ── SUBSTANCE · what slices 2b and 3 got wrong ───────────────────────

def test_substance_the_patient_has_actual_details(started):
    """
    **SUBSTANCE.** The bug slice 2b shipped: `case_json` was handed the
    case_versions row instead of its `content`, so every patient field was
    None. `set(case["patient"]) == {...}` passed, because the keys were all
    there — holding None.
    """
    patient = started["case"]["patient"]
    assert patient["name"], "no patient name; the content was not unwrapped"
    assert isinstance(patient["age"], int) and patient["age"] > 0
    assert patient["sex"]
    assert patient["presenting_complaint"]
    assert patient["intro"]
    assert started["case"]["opening_line"], "the patient has no opening line"


def test_substance_an_examination_the_case_cares_about_is_abnormal(
        client, account, started):
    """
    **SUBSTANCE.** The bug slice 3 shipped: the case-specific block was never
    found, so every result was the master normal report and no case had any
    abnormal finding at all. `assert body["result"]` passed throughout.

    The chest-pain case marks `abdomen` key, with epigastric tenderness. The
    master normal result for an abdomen is unremarkable, so the two differ —
    and if they ever stop differing, the case has lost the finding its whole
    trap depends on.
    """
    _, headers = account
    sid = started["session_id"]
    r = client.post(f"/v1/sessions/{sid}/examinations",
                    json={"key": "abdomen"}, headers=headers)
    assert r.status_code == 201, r.get_json()
    finding = r.get_json()["result"].lower()
    assert "epigastric" in finding, (
        "the case-specific finding was not used; this is the master normal "
        f"result. Got: {finding[:120]}")


def test_substance_the_patient_prompt_reaches_the_model(
        client, account, started, monkeypatch):
    """
    **SUBSTANCE.** Slice 3 passed `""` as the system instruction, so the
    patient had no persona — every reply came from a model told nothing about
    who it was playing. Nothing failed, because the fake LLM answers anything.
    """
    seen: dict = {}

    def capture(messages, system_instruction, **kwargs):
        seen["system"] = system_instruction
        return "Yes, after meals mostly."

    monkeypatch.setattr("nidan.api.v1.consultation.call_llm", capture)

    _, headers = account
    r = client.post(f"/v1/sessions/{started['session_id']}/questions",
                    json={"text": "Worse after meals?"}, headers=headers)
    assert r.status_code == 201
    assert seen["system"], "the model was given no system prompt"
    assert "GROUND RULES" in seen["system"], (
        "the system prompt is not the case's patient persona")


# ── §6 · submitting ──────────────────────────────────────────────────

def test_submitting_concludes_the_consultation(client, account, started, fake_llm):
    _, headers = account
    sid = started["session_id"]
    r = client.post(f"/v1/sessions/{sid}/diagnosis",
                    json={"text": "GERD, likely NSAID-induced"}, headers=headers)
    assert r.status_code == 201, r.get_json()
    assert r.get_json() == {"session_id": sid, "status": "completed",
                            "feedback_ready": True}


def test_submitting_twice_is_409_with_the_time_of_the_first(
        client, account, started, fake_llm):
    _, headers = account
    sid = started["session_id"]
    client.post(f"/v1/sessions/{sid}/diagnosis", json={"text": "GERD"},
                headers=headers)
    again = client.post(f"/v1/sessions/{sid}/diagnosis", json={"text": "GERD"},
                        headers=headers)
    assert again.status_code == 409
    assert again.get_json()["error"]["code"] == "session_concluded"
    assert again.get_json()["error"]["details"]["submitted_at"]


@pytest.mark.parametrize(("text", "code"), [
    ("", "diagnosis_empty"),
    ("   ", "diagnosis_empty"),
    ("x" * 201, "diagnosis_too_long"),
])
def test_a_bad_diagnosis_is_refused(client, account, started, text, code):
    _, headers = account
    r = client.post(f"/v1/sessions/{started['session_id']}/diagnosis",
                    json={"text": text}, headers=headers)
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == code


def test_zero_questions_is_permitted_and_assessed(
        client, account, started, fake_llm, live_db):
    """
    `PRD` FR-7 edge cases: "Zero questions is permitted. Assessment runs and
    flags premature closure."

    A learner who guesses immediately has done something the product has an
    opinion about, and refusing the submission would deny them the opinion.
    """
    _, headers = account
    sid = started["session_id"]
    r = client.post(f"/v1/sessions/{sid}/diagnosis",
                    json={"text": "Myocardial infarction"}, headers=headers)
    assert r.status_code == 201

    with live_db.connect() as c:
        flagged = c.execute(sa.text(
            "SELECT premature_closure_detected FROM session_results "
            "WHERE session_id = :sid"), {"sid": sid}).scalar_one()
    assert flagged is True, "zero questions did not flag history completeness"


# ── §6 · the feedback payload, CT-4 and CT-5 ─────────────────────────

# `API_CONTRACT` §11's CT-5 terms, and `PRD` P1's, spelled out here rather
# than imported from `reasoning.BANNED_VOCABULARY`. A test that asks the code
# what it should hide agrees with the code by construction.
# `anchored` is absent on purpose: it is a `diagnosis_verdict` enum value
# that §7's `verdict_distribution` example carries, and §11's CT-5 does
# not list it. Banning it made the progress payload fail its own contract.
CT5_TERMS = ("anchoring", "premature closure", "premature_closure",
             "confirmation bias", "confirmation_bias")

# §6 point 1: the three behavioural identifiers, and nothing else.
CT4_IDS = ("diagnostic_focus", "history_completeness", "evidence_exploration")


@pytest.fixture
def concluded(client, account, started, fake_llm):
    """A finished consultation: three questions, an examination, a diagnosis."""
    _, headers = account
    sid = started["session_id"]
    for text in ("Is the pain burning?", "Worse after meals?",
                 "Any medications you take daily?"):
        assert client.post(f"/v1/sessions/{sid}/questions", json={"text": text},
                           headers=headers).status_code == 201
    client.post(f"/v1/sessions/{sid}/examinations", json={"key": "abdomen"},
                headers=headers)
    r = client.post(f"/v1/sessions/{sid}/diagnosis",
                    json={"text": "GERD, NSAID-induced"}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return sid


def test_ct5_no_bias_vocabulary_reaches_the_learner(client, account, concluded):
    """
    **CT-5**, which `API_CONTRACT` §11 calls one of "the most important tests
    in the codebase": "No response body anywhere contains 'anchoring',
    'premature closure', 'confirmation bias'."

    This is not a hypothetical. The detectors' own `reason` strings say "No
    significant anchoring pattern detected", "No premature closure detected"
    and "Confirmation bias occurs when we seek only evidence that supports our
    first instinct" — so the obvious implementation, forwarding `bias_detail`,
    fails this on three of six branches. `reasoning.py` rebuilds the prose
    from `counters` so the internal text never reaches the boundary.
    """
    _, headers = account
    raw = client.get(f"/v1/sessions/{concluded}/feedback",
                     headers=headers).get_data(as_text=True).lower()
    leaked = [term for term in CT5_TERMS if term in raw]
    assert not leaked, f"bias vocabulary in the feedback payload: {leaked}"


def test_ct4_reasoning_uses_behavioural_identifiers(client, account, concluded):
    """
    **CT-4.** §6 point 1: the ids are `diagnostic_focus`,
    `history_completeness`, `evidence_exploration` — "the internal names never
    cross the API boundary."
    """
    _, headers = account
    reasoning = client.get(f"/v1/sessions/{concluded}/feedback",
                           headers=headers).get_json()["reasoning"]
    assert [r["id"] for r in reasoning] == list(CT4_IDS)
    assert [r["label"] for r in reasoning] == [
        "Diagnostic focus", "History completeness", "Evidence exploration"]


def test_every_dimension_is_present_whether_flagged_or_not(
        client, account, concluded):
    """
    §6 point 2 — the reason is "always present and always cites the user's own
    actions".

    All three, always. Showing only what went wrong turns the screen into a
    list of failures; showing all three describes how someone reasoned.
    """
    _, headers = account
    reasoning = client.get(f"/v1/sessions/{concluded}/feedback",
                           headers=headers).get_json()["reasoning"]
    assert len(reasoning) == 3
    for dimension in reasoning:
        assert dimension["reason"], f"{dimension['id']} has no reason"
        assert isinstance(dimension["flagged"], bool)
        if not dimension["flagged"]:
            assert dimension["status_line"] is None


def test_substance_the_reason_cites_the_learners_own_numbers(
        client, account, concluded):
    """
    **SUBSTANCE**, and `PRD` P3 / `ADR-0004`: a judgement must cite what the
    learner actually did. Three questions were asked, so the history
    dimension must say three — a reason built from the wrong counters, or from
    none, would still be a non-empty string.
    """
    _, headers = account
    reasoning = client.get(f"/v1/sessions/{concluded}/feedback",
                           headers=headers).get_json()["reasoning"]
    completeness = next(r for r in reasoning
                        if r["id"] == "history_completeness")
    assert "3 questions" in completeness["reason"], completeness["reason"]


def test_the_feedback_payload_carries_the_answer_and_the_prose(
        client, account, concluded):
    """
    `answer` is returned here and that is not a CT-1 violation: FR-3.4 forbids
    those fields in the **case** object during a consultation, and afterwards
    the answer is the point (`PRD` FR-8.8 keeps it collapsed in the UI).
    """
    _, headers = account
    body = client.get(f"/v1/sessions/{concluded}/feedback",
                      headers=headers).get_json()
    assert body["verdict"] in ("correct", "partial", "anchored", "other")
    assert body["summary"]["question_count"] == 3
    assert body["tutor_feedback"]["lines"]
    assert body["tutor_feedback"]["generator"] in ("llm", "rule_fallback")
    assert body["answer"]["correct_diagnosis"], (
        "no correct diagnosis; the content was not unwrapped")


def test_feedback_before_concluding_is_409(client, account, started):
    _, headers = account
    r = client.get(f"/v1/sessions/{started['session_id']}/feedback",
                   headers=headers)
    assert r.status_code == 409
    assert r.get_json()["error"]["code"] == "session_not_concluded"


def test_viewing_feedback_is_recorded_in_the_log(
        client, account, concluded, live_db):
    """`ADR-0003` — if it happened, it is an event."""
    _, headers = account
    client.get(f"/v1/sessions/{concluded}/feedback", headers=headers)
    with live_db.connect() as c:
        n = c.execute(sa.text(
            "SELECT count(*) FROM session_events "
            "WHERE session_id = :sid AND type = 'feedback_viewed'"),
            {"sid": concluded}).scalar_one()
    assert n >= 1


# ── §2.8 · CT-8 ──────────────────────────────────────────────────────

def test_ct8_the_same_key_and_body_replays_the_stored_response(
        client, account, started, fake_llm):
    """
    **CT-8.** §2.8: "A repeat with the same key and the same body returns the
    identical response."

    Concluding is irreversible, so a client whose first request timed out must
    not be told it failed when it succeeded — and must not conclude twice.
    Without the key the second call is a 409, which is correct but tells a
    retrying client the wrong story.
    """
    _, headers = account
    sid = started["session_id"]
    key = {"Idempotency-Key": str(uuid.uuid4()), **headers}

    first = client.post(f"/v1/sessions/{sid}/diagnosis",
                        json={"text": "GERD"}, headers=key)
    second = client.post(f"/v1/sessions/{sid}/diagnosis",
                         json={"text": "GERD"}, headers=key)

    assert first.status_code == 201
    assert second.status_code == 201, "a retry with the same key was not replayed"
    assert second.get_json() == first.get_json()


def test_the_same_key_with_a_different_body_is_422(
        client, account, started, fake_llm):
    """
    §2.8: "A repeat with the same key and a **different** body returns
    `422 idempotency_key_reused`."
    """
    _, headers = account
    sid = started["session_id"]
    key = {"Idempotency-Key": str(uuid.uuid4()), **headers}

    client.post(f"/v1/sessions/{sid}/diagnosis", json={"text": "GERD"},
                headers=key)
    other = client.post(f"/v1/sessions/{sid}/diagnosis",
                        json={"text": "Myocardial infarction"}, headers=key)
    assert other.status_code == 422
    assert other.get_json()["error"]["code"] == "idempotency_key_reused"


def test_field_order_in_the_body_does_not_count_as_a_different_body(
        client, account, started, fake_llm):
    """
    The hash is canonicalised with sorted keys. A client that serialises its
    JSON in a different order on the retry is making the same request, and a
    422 there would turn a correct retry into an error.
    """
    _, headers = account
    sid = started["session_id"]
    key = {"Idempotency-Key": str(uuid.uuid4()), **headers}

    client.post(f"/v1/sessions/{sid}/diagnosis",
                json={"text": "GERD", "note": "x"}, headers=key)
    retry = client.post(f"/v1/sessions/{sid}/diagnosis",
                        json={"note": "x", "text": "GERD"}, headers=key)
    assert retry.status_code == 201, retry.get_json()


# ── §6 · rating and abandoning ───────────────────────────────────────

def test_rating_the_feedback_is_stored(client, account, concluded, live_db):
    _, headers = account
    r = client.post(f"/v1/sessions/{concluded}/feedback/rating",
                    json={"was_helpful": True}, headers=headers)
    assert r.status_code == 204
    with live_db.connect() as c:
        row = c.execute(sa.text(
            "SELECT was_helpful, rated_at FROM feedback_texts "
            "WHERE session_id = :sid"), {"sid": concluded}).mappings().one()
    assert row["was_helpful"] is True
    assert row["rated_at"] is not None


def test_re_rating_overwrites_rather_than_adding(
        client, account, concluded, live_db):
    """
    `UX_SPEC` UX-3 is one control with two states, so a learner changing their
    mind is a correction and not a second data point.
    """
    _, headers = account
    client.post(f"/v1/sessions/{concluded}/feedback/rating",
                json={"was_helpful": True}, headers=headers)
    client.post(f"/v1/sessions/{concluded}/feedback/rating",
                json={"was_helpful": False}, headers=headers)
    with live_db.connect() as c:
        rows = c.execute(sa.text(
            "SELECT was_helpful FROM feedback_texts WHERE session_id = :sid"),
            {"sid": concluded}).scalars().all()
    assert rows == [False]


def test_a_non_boolean_rating_is_refused(client, account, concluded):
    _, headers = account
    r = client.post(f"/v1/sessions/{concluded}/feedback/rating",
                    json={"was_helpful": "yes"}, headers=headers)
    assert r.status_code == 422


def test_abandoning_sets_the_status_and_keeps_the_allowance_spent(
        client, account, started, live_db):
    """
    §6 → 204, status `abandoned`, and "**Still counts toward the monthly
    allowance**" (`PRD` FR-3 edge cases).

    The second half needs no code: `sessions_started_since()` counts started
    sessions whatever their status, so abandoning has never been a way to get
    a free attempt. Asserted here because that is easy to break later.
    """
    user_id, headers = account
    sid = started["session_id"]
    r = client.post(f"/v1/sessions/{sid}/abandon", headers=headers)
    assert r.status_code == 204

    with live_db.connect() as c:
        status = c.execute(sa.text("SELECT status FROM sessions WHERE id = :id"),
                           {"id": sid}).scalar_one()
        counted = c.execute(sa.text(
            "SELECT count(*) FROM sessions WHERE user_id = :uid"),
            {"uid": user_id}).scalar_one()
    assert status == "abandoned"
    assert counted == 1, "the abandoned session stopped counting"


def test_abandoning_a_concluded_consultation_is_409(
        client, account, started, fake_llm):
    """A diagnosis is irreversible; abandoning afterwards would lose it."""
    _, headers = account
    sid = started["session_id"]
    client.post(f"/v1/sessions/{sid}/diagnosis", json={"text": "GERD"},
                headers=headers)
    r = client.post(f"/v1/sessions/{sid}/abandon", headers=headers)
    assert r.status_code == 409
    assert r.get_json()["error"]["code"] == "session_concluded"


# ── the shape mismatch, pinned ───────────────────────────────────────

def _case_keys_the_domain_reads() -> set[str]:
    """
    Every `case["x"]` and `case.get("x")` in `nidan/domain`, by walking the
    AST rather than by remembering.

    Hand-maintaining this list is the bug it exists to catch: the stored
    `case_versions.content` (`DATA_MODEL` §8.1) and the domain's `Case` shape
    (`nidan/domain/content/cases.py`) differ in three places, and finding the
    third one — `patient_intro`, flat in the domain and nested under
    `patient` in storage — cost a KeyError in the middle of generating
    feedback, after two merged slices had already shipped the first two.
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "nidan" / "domain"
    keys: set[str] = set()
    for py in root.rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in ("case", "case_config")
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)):
                keys.add(node.slice.value)
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in ("case", "case_config")
                    and node.args
                    and isinstance(node.args[0], ast.Constant)):
                keys.add(node.args[0].value)
    return keys


def test_the_case_adapter_supplies_every_key_the_domain_reads(
        live_db, published_version):
    """
    `case_for_session()` must produce the domain's `Case` shape, not the
    stored one.

    A missing key here is not a quiet degradation — it is a KeyError inside
    the assessment or the feedback builder, i.e. a 500 at the moment a learner
    submits their diagnosis, after they have done all the work. Checked
    against the AST so a new `case["something"]` in the domain fails here
    rather than in production.
    """
    from nidan.infra.db.actor import AuthenticatedUser
    from nidan.infra.db.repositories import repo_scope
    from nidan.infra.db.repositories.cases import CaseRepository

    wanted = _case_keys_the_domain_reads()
    assert wanted, "the AST walk found nothing; has domain/ moved?"

    with repo_scope(AuthenticatedUser(uuid.uuid4())) as db:
        case = CaseRepository(db.conn, db.actor).case_for_session(published_version)

    assert case is not None, "a published version returned no case"
    missing = sorted(wanted - set(case))
    assert not missing, (
        f"the domain reads these keys and the adapter does not supply them: "
        f"{missing}. A KeyError here surfaces as a 500 when a learner submits.")


def test_the_adapter_returns_nothing_for_an_unpublished_version(
        live_db, published_version):
    """
    A draft is unreachable to a learner however complete it looks in the
    editor — the same rule `candidates()` enforces for selection, applied at
    the point of reading content.
    """
    from nidan.infra.db.actor import AuthenticatedUser
    from nidan.infra.db.repositories import repo_scope
    from nidan.infra.db.repositories.cases import CaseRepository

    with live_db.begin() as c:
        c.execute(sa.text(
            "UPDATE case_versions SET status = 'draft' WHERE id = :id"),
            {"id": published_version})
    try:
        with repo_scope(AuthenticatedUser(uuid.uuid4())) as db:
            case = CaseRepository(db.conn, db.actor).case_for_session(
                published_version)
        assert case is None
    finally:
        with live_db.begin() as c:
            c.execute(sa.text(
                "UPDATE case_versions SET status = 'published' WHERE id = :id"),
                {"id": published_version})
