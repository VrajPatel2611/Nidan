"""
T-002 criterion 4 · property tests (TECH_SPEC §12).

The invariants below must hold for every detector, on every case, for any
session a learner could produce:

    a ≤ q                 alternative questions never exceed total questions
    score ∈ [0, 1]        every score is a proportion
    detected ⇒ score > 0  a flag always carries weight

Unit tests check chosen examples. These check the whole input space, using
hypothesis to generate sessions rather than relying on the cases someone
thought to write down — which is how the tests find inputs a human would not.
"""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from nidan.domain.assessment.bias import (
    detect_all_biases,
    detect_anchoring,
    detect_confirmation_bias,
    detect_premature_closure,
)
from nidan.domain.content.cases import CASES, get_case

CASE_IDS = sorted(CASES)
DETECTORS = [detect_anchoring, detect_premature_closure, detect_confirmation_bias]

# Free text a learner might type, plus the clinical vocabulary that actually
# trips the detectors — random strings alone would never match a keyword and
# the properties would be tested only on the trivial path.
VOCAB = ["heart problem", "angina", "troponin", "heartburn", "burning", "reflux",
         "ibuprofen", "gaviscon", "pain", "when did it start", "", "  ", "?",
         "CAPITALS", "émoji ✨", "a" * 300]

questions = st.lists(st.sampled_from(VOCAB), min_size=0, max_size=25)
topics = st.lists(st.sampled_from([
    "pain_character", "meal_relationship", "radiation", "associated_symptoms",
    "medications", "family_history", "duration_pattern", "relieving_factors",
    "not_a_real_topic"]), max_size=9, unique=True)
diagnoses = st.one_of(st.none(), st.sampled_from(
    ["GERD", "Myocardial infarction", "heart attack", "", "unsure", "reflux"]))


def _session(case_id, qs, tp, dx):
    return {
        "case_id": case_id, "question_count": len(qs), "questions_asked": qs,
        "topics_covered": tp, "exams_performed": [], "investigations_ordered": [],
        "early_diagnosis": None, "diagnosis_submitted": dx,
        "start_time": "2026-01-01T09:00:00+00:00", "end_time": None,
    }


SETTINGS = settings(max_examples=150, deadline=None,
                    suppress_health_check=[HealthCheck.function_scoped_fixture])


@pytest.mark.parametrize("case_id", CASE_IDS)
@given(qs=questions, tp=topics, dx=diagnoses)
@SETTINGS
def test_scores_are_always_proportions(case_id, qs, tp, dx):
    """score ∈ [0, 1] — it is presented as a proportion, so it must be one."""
    case = get_case(case_id)
    s = _session(case_id, qs, tp, dx)
    for detector in DETECTORS:
        score = detector(s, case)["score"]
        assert 0.0 <= score <= 1.0, (
            f"{detector.__name__} on {case_id} returned {score} for "
            f"{len(qs)} questions"
        )


@pytest.mark.parametrize("case_id", CASE_IDS)
@given(qs=questions, tp=topics, dx=diagnoses)
@SETTINGS
def test_a_detection_always_carries_a_positive_score(case_id, qs, tp, dx):
    """
    detected ⇒ score > 0.

    A flag with a zero score would render as a finding with no weight behind
    it — the learner is told something went wrong and shown nothing.
    """
    case = get_case(case_id)
    s = _session(case_id, qs, tp, dx)
    for detector in DETECTORS:
        r = detector(s, case)
        if r["detected"]:
            assert r["score"] > 0, f"{detector.__name__} flagged with score 0"


@pytest.mark.parametrize("case_id", CASE_IDS)
@given(qs=questions, tp=topics, dx=diagnoses)
@SETTINGS
def test_alternative_count_never_exceeds_question_count(case_id, qs, tp, dx):
    """
    a ≤ q.

    Each question is counted at most once as exploring an alternative. If the
    `break` after a keyword match were ever lost, a question containing several
    alternative terms would be counted several times and the ratio could exceed
    1 — the class of arithmetic error that produces impossible percentages.
    """
    case = get_case(case_id)
    s = _session(case_id, qs, tp, dx)
    reason = detect_anchoring(s, case)["reason"]
    if "questions exploring" in reason:
        alt = int(reason.split("You asked ")[1].split(" questions")[0])
        assert alt <= len(qs), f"a={alt} > q={len(qs)}"


@pytest.mark.parametrize("case_id", CASE_IDS)
@given(qs=questions, tp=topics, dx=diagnoses)
@SETTINGS
def test_every_detector_returns_the_full_contract(case_id, qs, tp, dx):
    """
    Shape stability. Callers index these keys directly, so a missing one is a
    KeyError at the end of a consultation — after the learner's work is done.
    """
    case = get_case(case_id)
    s = _session(case_id, qs, tp, dx)
    for detector in DETECTORS:
        r = detector(s, case)
        # `rule_fired` and `counters` joined the contract in T-016
        # (DATA_MODEL §8.5). counters is what lets a recomputation mismatch be
        # localised to a specific intermediate value rather than merely
        # observed as a different score.
        assert set(r) == {"detected", "score", "rule_fired", "reason",
                          "evidence", "counters"}
        assert isinstance(r["detected"], bool)
        assert isinstance(r["score"], (int, float))
        assert isinstance(r["reason"], str) and r["reason"]
        assert isinstance(r["evidence"], list)
        assert isinstance(r["counters"], dict) and r["counters"]
        # None when nothing fired, and a rule name exactly when it did: a
        # detection with no rule attached cannot be explained to a learner or
        # replayed under different thresholds.
        assert (r["rule_fired"] is None) is (not r["detected"])
        assert all(isinstance(v, (int, float)) for v in r["counters"].values())


@pytest.mark.parametrize("case_id", CASE_IDS)
@given(qs=questions, tp=topics, dx=diagnoses)
@SETTINGS
def test_evidence_is_always_traceable_to_the_learner(case_id, qs, tp, dx):
    """
    Property P2 (ADR-0004): a flag cites the learner's own questions.

    Anchoring evidence must be questions the learner actually asked — never
    paraphrased, never invented. This is the property that makes a judgement
    arguable rather than oracular.
    """
    case = get_case(case_id)
    s = _session(case_id, qs, tp, dx)
    for quoted in detect_anchoring(s, case)["evidence"]:
        assert quoted in qs, f"cited a question the learner never asked: {quoted!r}"


@pytest.mark.parametrize("case_id", CASE_IDS)
@given(qs=questions, tp=topics, dx=diagnoses)
@SETTINGS
def test_detectors_never_mutate_the_session(case_id, qs, tp, dx):
    """
    Assessment reads; it does not write.

    If a detector mutated the session, running the three in a different order
    would give different answers — and replaying stored events would not
    reproduce the stored result (ADR-0003).
    """
    import copy
    case = get_case(case_id)
    s = _session(case_id, qs, tp, dx)
    before = copy.deepcopy(s)
    detect_all_biases(s, case)
    assert s == before, "a detector mutated the session it was given"
