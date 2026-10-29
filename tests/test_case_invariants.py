"""
T-003 · Case content invariants C-1 … C-7 (DATA_MODEL §8.1).

Clinical case content is data, not code, so nothing in the type system or the
test suite catches a malformed case. These seven checks are that safety net.

C-4 is why this file exists. Anchor keywords overlapping contradictory clues is
the defect that held the confirmation-bias detector at 14% sensitivity, and it
is invisible on inspection: the terms look unrelated until you notice that the
detector matches by substring, so the anchor keyword "heart" matches a learner
asking about "heartburn" — the exact opposite line of enquiry.

Every test is parametrised per case so a failure names the case, and every
assertion message names the offending terms. A failure you have to go hunting
for is a failure that gets ignored.
"""

import pytest

from nidan.domain.assessment.bias import clue_keywords
from nidan.domain.assessment.topics import TOPIC_KEYWORDS
from nidan.domain.content.cases import (
    CASE_SLUGS,
    CASES,
    MASTER_EXAMINATIONS,
    MASTER_INVESTIGATIONS,
    get_case,
)

CASE_IDS = sorted(CASES)


@pytest.fixture(params=CASE_IDS)
def case(request):
    """Every test in this module runs once per case."""
    return get_case(request.param)


# ── C-1, C-2, C-3 · referential integrity across a JSON boundary ──────────
# The case content references master lists by key. Nothing enforces that the
# key exists, so a typo silently produces a case whose examination never
# returns a finding.

def test_c1_examination_keys_exist(case):
    unknown = sorted(set(case["examination"]) - set(MASTER_EXAMINATIONS))
    assert not unknown, (
        f"C-1 · {case['id']} references examinations that do not exist in "
        f"MASTER_EXAMINATIONS: {unknown}"
    )


def test_c2_investigation_keys_exist(case):
    unknown = sorted(set(case["investigations"]) - set(MASTER_INVESTIGATIONS))
    assert not unknown, (
        f"C-2 · {case['id']} references investigations that do not exist in "
        f"MASTER_INVESTIGATIONS: {unknown}"
    )


def test_c3_required_topics_exist(case):
    unknown = sorted(set(case["required_topics"]) - set(TOPIC_KEYWORDS))
    assert not unknown, (
        f"C-3 · {case['id']} requires topics that have no entry in "
        f"TOPIC_KEYWORDS, so they can never be matched: {unknown}"
    )


# ── C-4 · the one that matters ───────────────────────────────────────────

def test_c4_anchor_keywords_disjoint_from_contradictory_clues(case):
    """
    No anchor keyword may overlap any contradictory-clue keyword.

    Checked as SUBSTRING containment in both directions, not set intersection,
    because that is how the detectors match (`if kw in q_lower`). A plain
    intersection would pass "heart" against "heartburn" and miss the entire
    bug class this invariant exists to prevent.

    When it overlaps, one question is counted as both fixating on the trap
    diagnosis and exploring the evidence against it. The learner is then told
    they anchored, citing as evidence the questions where they did the right
    thing.
    """
    anchors = [a.lower() for a in case["anchor_keywords"]]

    collisions = []
    for i, clue in enumerate(case["contradictory_clues"]):
        for kw in clue_keywords(clue):
            for anchor in anchors:
                if anchor in kw or kw in anchor:
                    collisions.append(
                        f'anchor "{anchor}" ↔ clue[{i}] "{kw}"'
                    )

    assert not collisions, (
        f"C-4 · {case['id']} has anchor keywords overlapping its contradictory "
        f"clues. A question matching one is counted as matching both, which "
        f"inflates the anchoring score and cites the wrong evidence.\n"
        f"  Offending pairs:\n    " + "\n    ".join(collisions)
    )


# ── C-5, C-6, C-7 · thresholds that make the scoring meaningful ──────────

def test_c5_accepted_diagnoses_has_at_least_two(case):
    n = len(case["accepted_diagnoses"])
    assert n >= 2, (
        f"C-5 · {case['id']} accepts only {n} diagnosis phrase(s). Single-phrase "
        f"matching is too brittle — a learner who writes the right diagnosis in "
        f"different words is marked wrong."
    )


def test_c6_at_least_four_contradictory_clues(case):
    n = len(case["contradictory_clues"])
    assert n >= 4, (
        f"C-6 · {case['id']} has {n} contradictory clues. Below 4 the 0.25 "
        f"exploration ratio in the confirmation-bias detector is meaningless."
    )


def test_c7_has_at_least_one_key_investigation(case):
    keys = [k for k, v in case["investigations"].items()
            if v.get("category") == "key"]
    assert keys, (
        f"C-7 · {case['id']} has no investigation with category 'key', so the "
        f"scorecard denominator for key investigations is zero."
    )


# ── coverage guard ───────────────────────────────────────────────────────

def test_every_case_is_checked_and_can_be_identified():
    """
    Guards against the invariants silently covering fewer cases than exist.

    A case added to CASES but not loadable reduces coverage without any test
    failing. A case added without a `CASE_SLUGS` entry loads perfectly and
    then has no stable identifier, so it cannot be seeded into `cases.slug`,
    selected, or reached by URL (`DATA_MODEL` §5.1) — and nothing notices
    until the migration generator runs.

    The count is a floor, not a fixture. It was `== 5` until cases 6 and 7
    were written on 29 October 2026, and three more are planned; pinning the
    number means every new case starts by editing an assertion, which teaches
    people to edit assertions.
    """
    assert len(CASE_IDS) >= 5, f"cases have gone missing: {CASE_IDS}"
    assert all(get_case(cid) for cid in CASE_IDS), "a case in CASES will not load"
    assert sorted(CASE_SLUGS) == CASE_IDS, (
        f"CASES and CASE_SLUGS disagree. Only in CASES: "
        f"{sorted(set(CASE_IDS) - set(CASE_SLUGS))}; only in CASE_SLUGS: "
        f"{sorted(set(CASE_SLUGS) - set(CASE_IDS))}")
    assert len(set(CASE_SLUGS.values())) == len(CASE_SLUGS), (
        "two cases share a slug, and `cases.slug` is UNIQUE")


# ── C-8, C-9 · found during T-002, not yet in DATA_MODEL §8.1 ────────────
# T-003 added C-4 (anchor vs contradictory clues). Writing the detector unit
# tests in T-002 revealed two more collisions of the same family that C-4 does
# not cover. Both are live-bug-derived, not speculative.

def test_c8_anchor_keywords_disjoint_from_alternative_topics(case):
    """
    C-8 · anchor_keywords ∩ alternative_topics = ∅ (substring, both directions).

    Found in T-002: case_1 listed "gi" as an alternative topic, and "gi" is a
    substring of the anchor keyword "anGInal"/"angina". A learner asking a
    purely cardiac question was credited with exploring an alternative cause,
    which suppressed anchoring rule A2 — a false negative on the primary
    detector.

    Not in DATA_MODEL §8.1. It should be; logged as debt in the T-002 build log.
    """
    anchors = [a.lower() for a in case["anchor_keywords"]]
    alternatives = [a.lower() for a in case["alternative_topics"]]

    collisions = [
        f'anchor "{a}" ↔ alternative "{x}"'
        for a in anchors for x in alternatives
        if a in x or x in a
    ]
    assert not collisions, (
        f"C-8 · {case['id']} has anchor keywords overlapping its alternative "
        f"topics. A question counted as both fixating on the trap AND exploring "
        f"an alternative suppresses anchoring rule A2.\n"
        f"  Offending pairs:\n    " + "\n    ".join(collisions)
    )


# Ordinary words that appear in clinical questions but carry no diagnostic
# direction. A keyword that is a substring of one of these is too loose to be
# matched with `if kw in question`.
COMMON_WORDS = [
    "examine", "examination", "vomiting", "abdominal", "allergies", "begin",
    "beginning", "happened", "appetite", "before", "region", "imaging",
    "surgical", "patient", "medication", "history", "family", "describe",
    "previous", "sleeping", "swelling", "admission", "symptoms", "problem",
    "period", "temperature", "operation", "upper", "improve", "people",
    "hospital", "experience", "develop", "complain", "expect", "compare",
]


def test_c9_no_keyword_matches_an_ordinary_word(case):
    """
    C-9 · no anchor or alternative keyword may be a proper substring of a
    common English word.

    The detectors match with `if kw in question.lower()`, so a two-letter
    keyword matches constantly. Found in T-002: "mi" (myocardial infarction)
    matched "exaMIne", "voMIting" and "abdoMInal", so routine questions were
    counted as cardiac fixation — inflating the anchoring score for every
    learner in case_1.

    Not in DATA_MODEL §8.1. Logged as debt in the T-002 build log.
    """
    offenders = []
    for field in ("anchor_keywords", "alternative_topics"):
        for kw in case[field]:
            k = kw.lower()
            hits = [w for w in COMMON_WORDS if k in w and k != w]
            if hits:
                offenders.append(f'{field} "{kw}" ⊂ {hits[:3]}')

    assert not offenders, (
        f"C-9 · {case['id']} has keywords loose enough to match ordinary "
        f"clinical questions. Matching is by substring, so these fire on "
        f"questions with no diagnostic intent.\n"
        f"  Offending terms:\n    " + "\n    ".join(offenders)
    )
