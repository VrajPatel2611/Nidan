"""
Playtest (BUILD_PLAN T-022, UX_SPEC §12.5).

Against a real database and real tokens, not mocks: two of the things being
proved — that a playtest writes no consultation rows, and that a draft can be
opened — are statements about the database, and a mocked repository would only
prove what the mock was told.

The test this file exists for is `test_a_playtest_writes_no_consultation_rows`.
Two clinicians playtesting for a week would otherwise put dozens of expert
consultations into a dataset about student reasoning.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nidan.app import create_app
from nidan.domain.assessment.engine import assess
from nidan.domain.assessment.topics import TOPIC_KEYWORDS
from nidan.domain.events import Event
from nidan.web.admin.playtest import instrumentation
from tests.fakes.llm import FakeLLM

pytestmark = pytest.mark.usefixtures("live_db")

# Tables a learner's consultation writes, and the two that hang off a session.
CONSULTATION_TABLES = ("sessions", "session_events", "session_results",
                       "llm_calls", "leakage_flags")


@pytest.fixture
def client(live_db, authority):
    return create_app({"TESTING": True, "SECRET_KEY": "t022"}).test_client()


@pytest.fixture
def account(live_db):
    """auth.users + profile with a platform role. Removed afterwards."""
    made: list[uuid.UUID] = []

    def _make(role: str = "admin") -> uuid.UUID:
        uid = uuid.uuid4()
        with live_db.begin() as c:
            c.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": uid})
            c.execute(sa.text(
                "INSERT INTO profiles (id, platform_role) "
                "VALUES (:id, CAST(:r AS platform_role))"), {"id": uid, "r": role})
        made.append(uid)
        return uid

    yield _make

    with live_db.begin() as c:
        for uid in made:
            c.execute(sa.text("DELETE FROM profiles WHERE id = :id"), {"id": uid})
            c.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": uid})


@pytest.fixture
def admin_headers(account, authority):
    return {"Authorization": f"Bearer {authority.token(sub=str(account('admin')))}"}


@pytest.fixture
def chest_pain(live_db):
    """(case_id, version_id, content) of the seeded chest-pain case — a draft."""
    with live_db.connect() as c:
        row = c.execute(sa.text("""
            SELECT cv.case_id, cv.id, cv.status, cv.content
            FROM case_versions cv JOIN cases c ON c.id = cv.case_id
            WHERE c.slug = 'chest-pain-gerd'
        """)).mappings().one()
    return row


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM(default="I'm not sure, doctor.")
    monkeypatch.setattr("nidan.infra.llm.gateway.call_llm", fake)
    return fake


def _url(case, path: str = "") -> str:
    base = f"/admin/cases/{case['case_id']}/versions/{case['id']}/playtest"
    return f"{base}/{path}" if path else base


def _counts(engine) -> dict[str, int]:
    with engine.connect() as c:
        return {t: c.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar()
                for t in CONSULTATION_TABLES}


def _ask(client, case, headers, events, message):
    res = client.post(_url(case, "ask"), headers=headers,
                      json={"events": events, "message": message})
    assert res.status_code == 200, res.get_data(as_text=True)
    return res.get_json()


# ── 1. Access ────────────────────────────────────────────────────────

def test_playtest_404s_identically_for_anyone_but_a_reviewer_or_admin(
        client, chest_pain, account, authority, admin_headers):
    """
    Anonymous, a learner, an expired admin token — and an admin asking for a
    version that does not exist. One status, one body. Reviewers are let in:
    T-023 has them judge a case by playing it.
    """
    admin = account("admin")
    learner = authority.token(sub=str(account("user")))
    reviewer = authority.token(sub=str(account("reviewer")))
    expired = authority.token(sub=str(admin), expires_in=-60)
    missing = dict(chest_pain, id=uuid.uuid4())

    assert client.get(_url(chest_pain), headers={
        "Authorization": f"Bearer {reviewer}"}).status_code == 200

    responses = [
        client.get(_url(chest_pain)),
        client.get(_url(chest_pain), headers={"Authorization": f"Bearer {learner}"}),
        client.get(_url(chest_pain), headers={"Authorization": f"Bearer {expired}"}),
        client.get(_url(missing), headers=admin_headers),
        client.post(_url(chest_pain, "ask"), json={"events": [], "message": "hi"}),
    ]

    assert {r.status_code for r in responses} == {404}
    assert len({r.get_data(as_text=True) for r in responses}) == 1


# ── 2. Ephemeral ─────────────────────────────────────────────────────

def test_a_playtest_writes_no_consultation_rows(
        client, chest_pain, admin_headers, llm, live_db):
    """
    A whole consultation — questions, an examination, a test, a diagnosis, a
    reset — and not one row in any table a learner's consultation fills.
    """
    before = _counts(live_db)

    d = _ask(client, chest_pain, admin_headers, [], "Is the pain burning?")
    d = _ask(client, chest_pain, admin_headers, d["events"], "I think it is angina")
    for path, body in (("examine", {"key": "vitals"}),
                       ("investigate", {"key": "ecg"}),
                       ("diagnose", {"text": "angina"}),
                       ("state", {})):
        res = client.post(_url(chest_pain, path), headers=admin_headers,
                          json={"events": d["events"], **body})
        assert res.status_code == 200, res.get_data(as_text=True)
        d = res.get_json()

    assert len(d["events"]) == 8   # 2×(question, reply) + early dx + exam + test + dx
    assert _counts(live_db) == before


def test_llm_calls_are_tagged_playtest(client, chest_pain, admin_headers, llm):
    """Excluded from cost-per-session reporting by purpose (UX_SPEC §12.5)."""
    _ask(client, chest_pain, admin_headers, [], "Where is the pain?")
    assert [c["purpose"] for c in llm.calls] == ["playtest"]


# ── 3. The panel is the engine's output ──────────────────────────────

def test_the_panel_shows_what_assess_returned(
        client, chest_pain, admin_headers, llm, monkeypatch):
    """
    Doctor the engine's answer on its way to the panel. If the panel shows the
    doctored values, it is displaying `assess()`; if it computed its own, it
    would show the real ones.
    """
    real_assess = instrumentation.assess

    def doctored(events, case, engine=None):
        result = real_assess(events, case, engine)
        result.bias_detail["anchoring"].update(
            detected=True, score=0.987, rule_fired="A2")
        result.bias_detail["anchoring"]["counters"].update(a=41, m=17)
        return result

    monkeypatch.setattr(instrumentation, "assess", doctored)
    html = _ask(client, chest_pain, admin_headers, [],
                "Is the pain burning?")["instrumentation_html"]

    assert "0.99" in html and "A2" in html
    assert "a=41" in html and "m=17" in html


def test_the_counters_match_a_direct_assessment(
        client, chest_pain, admin_headers, llm):
    """Without doctoring: the panel agrees with `assess()` run independently."""
    d = _ask(client, chest_pain, admin_headers, [], "Is the pain burning?")
    d = _ask(client, chest_pain, admin_headers, d["events"],
             "Do you take ibuprofen or antacids?")

    events = [Event(seq=i, type=e["type"], payload=e["payload"])
              for i, e in enumerate(d["events"], start=1)]
    case = dict(chest_pain["content"], id=str(chest_pain["id"]))
    result = assess(events, case)
    bias = result.bias_detail
    html = d["instrumentation_html"]

    assert f"q={result.question_count}" in html
    assert f"c={len(result.topics_hit)}/{len(case['required_topics'])}" in html
    k, K = bias["confirmation_bias"]["counters"]["k"], bias["confirmation_bias"]["counters"]["K"]
    assert f"k={k}/{K}" in html
    assert f"Clues explored {k} / {K}" in html
    assert "disagrees with the detector" not in html


def test_a_matched_topic_names_the_keyword_that_matched_it(
        client, chest_pain, admin_headers, llm):
    html = _ask(client, chest_pain, admin_headers, [],
                "Is the pain burning?")["instrumentation_html"]
    assert "pain_character" in html
    assert "keyword “burning”" in html


# ── 4. Leakage ───────────────────────────────────────────────────────

def test_leakage_is_flagged_when_a_reply_volunteers_an_unasked_topic(
        client, chest_pain, admin_headers, llm):
    """
    The reply mentions medication; the question did not ask about it. The
    learner would be handed the topic without having thought to ask.
    """
    assert "medications" in chest_pain["content"]["required_topics"]
    keyword = TOPIC_KEYWORDS["medications"][0]
    llm.replies = [f"It's in the middle. I also take {keyword} every day."]

    html = _ask(client, chest_pain, admin_headers, [],
                "Where exactly is it?")["instrumentation_html"]

    assert "Possible leakage" in html
    assert "medications" in html


def test_no_leakage_when_the_question_asked_about_it(
        client, chest_pain, admin_headers, llm):
    keyword = TOPIC_KEYWORDS["medications"][0]
    llm.replies = [f"Yes, {keyword}."]
    html = _ask(client, chest_pain, admin_headers, [],
                f"Do you take {keyword}?")["instrumentation_html"]
    assert "Possible leakage" not in html


# ── 5. Reset ─────────────────────────────────────────────────────────

def test_reset_clears_the_events_and_both_panels(
        client, chest_pain, admin_headers, llm):
    d = _ask(client, chest_pain, admin_headers, [], "Is the pain burning?")
    assert d["events"]

    res = client.post(_url(chest_pain, "state"), headers=admin_headers,
                      json={"events": []})
    assert res.status_code == 200
    d = res.get_json()

    assert d["events"] == []
    assert "q=0" in d["instrumentation_html"]
    assert "Question 1" not in d["instrumentation_html"]
    assert "Is the pain burning?" not in d["student_html"]


# ── 6. Drafts ────────────────────────────────────────────────────────

def test_a_draft_version_is_playtestable(client, chest_pain, admin_headers):
    assert chest_pain["status"] == "draft"
    res = client.get(_url(chest_pain), headers=admin_headers)
    assert res.status_code == 200
    page = res.get_data(as_text=True)
    assert "Student view" in page and "Instrumentation" in page


# ── Guards ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("events", [
    "not a list",
    [{"type": "feedback_viewed", "payload": {}}],
    [{"type": "question", "payload": {"text": "hi"}}],          # no char_count
    [{"type": "question", "payload": {"text": "hi", "char_count": 2, "x": 1}}],
])
def test_an_event_list_this_page_could_not_have_made_is_refused(
        client, chest_pain, admin_headers, events):
    res = client.post(_url(chest_pain, "state"), headers=admin_headers,
                      json={"events": events})
    assert res.status_code == 400


def test_nothing_happens_after_a_diagnosis_until_reset(
        client, chest_pain, admin_headers, llm):
    res = client.post(_url(chest_pain, "diagnose"), headers=admin_headers,
                      json={"events": [], "text": "GERD"})
    events = res.get_json()["events"]
    res = client.post(_url(chest_pain, "ask"), headers=admin_headers,
                      json={"events": events, "message": "One more thing?"})
    assert res.status_code == 409
    assert llm.calls == []


def test_a_case_missing_engine_fields_is_named_not_crashed():
    """A draft saved without `alternative_topics` gets a message, not a 500."""
    case = {"id": "x", "required_topics": [], "anchor_topic": "", "anchor_keywords": [],
            "contradictory_clues": [], "minimum_questions": 7}
    panel = instrumentation.build([], case)
    assert panel["missing"] == ["alternative_topics"]


# ── The case-facts panel a reviewer scores against ───────────────────

class TestTheCaseFactsPanel:
    """
    `_case_facts.html` shows a reviewer the ground truth: the diagnosis, the
    trap, the clues, the findings, the results and the persona brief.

    It exists because the rubric asks four questions and two of them —
    *internal consistency* and *solvability from the information given* —
    cannot be answered from the student view. A reviewer without it scores
    whatever they happened to elicit, and two reviewers score different
    things.
    """

    @staticmethod
    def _render(case: dict, *, reviewing: bool) -> str:
        from flask import render_template

        from nidan.app import create_app
        app = create_app({"TESTING": True})
        with app.test_request_context():
            return render_template("admin/playtest/_case_facts.html",
                                   case=case, review={"x": 1} if reviewing else None)

    def test_it_shows_the_answer_the_learner_must_never_see(self):
        from nidan.domain.content.cases import get_case
        case = get_case("case_1")
        html = self._render(case, reviewing=True)
        assert case["correct_diagnosis"] in html
        assert case["anchor_topic"] in html

    def test_an_examination_renders_its_finding_and_a_test_its_result(self):
        """
        The two shapes are different — an examination is
        `{label, finding, key}` and an investigation is
        `{label, result, category}` — and reading `result` off an
        examination is why the panel first drew six findings as six blank
        rows. Both are asserted, because fixing one and not the other looks
        identical on a page nobody reads carefully.
        """
        from nidan.domain.content.cases import get_case
        case = get_case("case_1")
        html = self._render(case, reviewing=True)

        exam = next(iter(case["examination"].values()))
        assert exam["finding"][:40] in html, "examination finding missing"
        assert exam["label"] in html

        test = next(iter(case["investigations"].values()))
        assert test["result"][:40] in html, "investigation result missing"
        assert test["label"] in html

    def test_every_contradictory_clue_is_listed(self):
        """
        A reviewer judging *trap validity* needs all of them. Showing the
        first few would make a thin case look well-built.
        """
        from nidan.domain.content.cases import get_case
        case = get_case("case_1")
        html = self._render(case, reviewing=True)
        for clue_set in case["contradictory_clues"]:
            assert clue_set[0] in html, clue_set

    def test_the_panel_is_only_included_when_a_reviewer_opened_the_case(self):
        """
        Asserted against `index.html`, which is what decides. Playtest
        without `?review=1` stays a case played blind, which is the right
        way to feel whether a trap works.
        """
        import pathlib

        import nidan.web.admin.playtest.routes as mod
        index = (pathlib.Path(mod.__file__).parent.parent.parent
                 / "templates" / "admin" / "playtest" / "index.html")
        import re
        source = index.read_text(encoding="utf-8")

        # Walk the if/endif nesting rather than slicing to the first
        # `{% if review %}` — there are two in this file, and the first
        # guards a breadcrumb. A slice found that one and failed on a
        # template that was correct.
        depth, guarded, found = [], False, False
        for token in re.finditer(
                r"{%-?\s*(if|elif|else|endif)\b([^%]*)%}|_case_facts\.html", source):
            if token.group(0).endswith("_case_facts.html"):
                found = True
                guarded = any(depth)
                break
            kind, expr = token.group(1), (token.group(2) or "").strip()
            if kind == "if":
                depth.append(expr == "review")
            elif kind == "endif" and depth:
                depth.pop()
        assert found, "index.html does not include the case-facts panel at all"
        assert guarded, "the panel is included outside `{% if review %}`"
