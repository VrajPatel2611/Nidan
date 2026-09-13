"""
The assessment engine against the 16 pilot sessions (BUILD_PLAN T-016 ⭐).

This is the test `BUILD_PLAN` names, and it is the most consequential one in the
repository. The paper's data-integrity check recomputed bias flags from stored
questions and matched all 16 sessions exactly; these tests turn that one-off
verification into something CI runs on every push.

**Two tests, because they check different things.**

`test_the_golden_record_still_matches` is the regression net: today's engine
against a committed record of its own output. Any change to a detector, a
threshold or the lexicon that moves a result fails here, and the diff names
which sessions moved.

`test_the_engine_still_reproduces_the_published_pilot_results` is the research
claim: today's engine against the results **published in the paper**. Fifteen
match exactly. One does not, for a reason that is documented below and is not a
regression.

Neither needs a database. The engine is a pure function, which is the property
that makes this possible at all.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from nidan.domain.assessment.engine import EngineVersion, assess
from nidan.domain.assessment.thresholds import PILOT
from nidan.domain.content.cases import get_case
from tests.pilot import events_from, load, pilot_files

GOLDEN = pathlib.Path(__file__).resolve().parent / "golden" / "pilot_assessments.json"

# The single session whose anchoring result differs from the published record,
# and why. See the module docstring of the test below.
KNOWN_DIVERGENCE = {("P07_case_2_seq1_20260731_114622.json", "anchoring")}


@pytest.fixture(scope="module")
def golden() -> dict:
    assert GOLDEN.exists(), (
        "the golden record is missing — regenerate it with "
        "python scripts/build_golden.py")
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _assess(path: pathlib.Path):
    record = load(path)
    return record, assess(events_from(record), get_case(record["case_id"]))


# ── the regression net ───────────────────────────────────────────────

def test_the_golden_record_still_matches(golden):
    """
    Every number the engine produces for the pilot sessions, pinned.

    If this fails, something changed a result. That may be entirely correct —
    a detector fix, a lexicon addition, a recalibrated threshold — but it must
    be *seen*: regenerate with `python scripts/build_golden.py`, read the diff,
    and commit it as part of the change that caused it.

    Regenerating to make a red build green discards the only artefact that says
    which learners' results moved and by how much.
    """
    drift = []
    for path in pilot_files():
        expected = golden.get(path.name)
        assert expected is not None, (
            f"{path.name} has no golden entry — regenerate the record")

        _, result = _assess(path)
        actual = {
            "coverage_pct": result.coverage_pct,
            "diagnosis_verdict": result.diagnosis_verdict,
            "question_count": result.question_count,
            "scalars": result.scalars,
            "detail": {
                name: {"rule_fired": d["rule_fired"], "counters": d["counters"]}
                for name, d in result.bias_detail.items()
            },
        }
        for key, value in actual.items():
            if expected[key] != value:
                drift.append(f"{path.name}: {key}\n"
                             f"    golden: {expected[key]}\n"
                             f"    now:    {value}")

    assert not drift, ("the engine no longer reproduces its golden record:\n\n"
                       + "\n".join(drift))


def test_every_pilot_session_has_a_golden_entry(golden):
    """A session added to the record without a golden entry is untested."""
    assert {p.name for p in pilot_files()} == set(golden)


# ── determinism (criterion 5) ────────────────────────────────────────

def test_assessing_the_same_events_twice_is_byte_identical():
    """
    Criterion 5, stated exactly. Serialised and compared as bytes rather than
    as objects, because that is the form the result is stored and transmitted
    in — and float formatting is where "equal" and "identical" part company.
    """
    for path in pilot_files():
        _, first = _assess(path)
        _, second = _assess(path)
        assert (json.dumps(first.bias_detail, sort_keys=True)
                == json.dumps(second.bias_detail, sort_keys=True)), path.name
        assert first.scalars == second.scalars
        assert first.coverage_pct == second.coverage_pct


def test_the_engine_reads_its_thresholds_from_the_version_it_is_given():
    """
    Criterion 2, demonstrated rather than asserted: raising the anchoring
    threshold to a value nothing can exceed must change the result, and it must
    do so without touching a line of detector code.

    This is the property that makes calibration a data operation.
    """
    from dataclasses import replace

    record = load(pilot_files()[0])
    events = events_from(record)
    case = get_case(record["case_id"])

    baseline = assess(events, case, EngineVersion.pilot())
    assert baseline.bias_detail["anchoring"]["detected"]

    impossible = EngineVersion(
        version="test", detector_version="test", lexicon_version="test",
        thresholds=replace(PILOT, anchoring_concentration=0.99,
                           anchoring_a2_min_anchor=99))
    assert not assess(events, case, impossible).bias_detail["anchoring"]["detected"]


# ── the published research claim ─────────────────────────────────────

def test_the_engine_still_reproduces_the_published_pilot_results():
    """
    Today's engine against the results stored in the pilot's own session files.

    **Fifteen of sixteen reproduce exactly.** One does not, and it is worth
    knowing precisely why, because it is the difference between a regression
    and a fix.

    `P07_case_2` — the pulmonary embolism case. The learner asked:

        "You mentioned Dubai — did you catch a travel bug on the flight?"

    The pilot-era anchor keyword list for that case contained `"travel bug"`,
    so that question counted as evidence of anchoring: 5 of 7 questions
    "focused on chest infection", which is 0.71 and just over the 0.60
    threshold. Today the keyword is gone and the count is 4 of 7 — 0.571, below
    the threshold — so anchoring is not flagged.

    Case 2's contradictory clues include
    `['flight', 'flew', 'long haul', 'long journey', 'immobile', ...]` — the
    travel history that points AT pulmonary embolism. The anchor keyword
    overlapped a contradictory clue, which is precisely what invariant C-4
    forbids: the detector was counting the single most diagnostically useful
    question in the consultation as evidence against the learner.

    Removing it was the fix working. This is the one case in the published
    pilot where a learner was marked down for asking the best question
    available to them.

    The divergence is pinned rather than tolerated: if a sixteenth appears, or
    if this one changes shape, the test fails and somebody has to explain it.
    """
    divergences = set()
    for path in pilot_files():
        record, result = _assess(path)
        for name, published in record["biases_detected"].items():
            current = result.bias_detail[name]
            same = (bool(published["detected"]) == bool(current["detected"])
                    and round(float(published["score"]), 2)
                        == round(float(current["score"]), 2))
            if not same:
                divergences.add((path.name, name))

    unexpected = divergences - KNOWN_DIVERGENCE
    assert not unexpected, (
        "the engine no longer reproduces the published pilot results for: "
        f"{sorted(unexpected)}. Every divergence must be explained in this "
        "test's docstring before it is accepted.")

    healed = KNOWN_DIVERGENCE - divergences
    assert not healed, (
        f"{sorted(healed)} now matches the published record again. That is not "
        "necessarily good news — the C-4 keyword fix is what caused it to "
        "diverge, so a match may mean the fix has been reverted.")


def test_the_published_divergence_is_the_one_we_think_it_is():
    """
    The divergence above is only acceptable because of its cause, so the cause
    is checked rather than assumed: `"travel bug"` must not be an anchor
    keyword for the PE case, and the travel history must still be a
    contradictory clue.

    If either changes, the explanation in the docstring above stops being true
    and the exception must be re-argued.
    """
    case = get_case("case_2")
    assert "travel bug" not in case["anchor_keywords"], (
        "'travel bug' is an anchor keyword again — it overlaps the travel "
        "history clue that points at the correct diagnosis (invariant C-4)")

    travel_clue = [c for c in case["contradictory_clues"]
                   if any("flight" in k for k in c)]
    assert travel_clue, "the travel history is no longer a contradictory clue"
