"""
`validate_personas.py` — the parts that can be tested without a model (T-040).

The script itself makes network calls, which is why it is a script and not a
test (T-002 criterion 1). Its *judgement* is pure, and that is what is checked
here: what counts as a key fact, what does not, and which findings are allowed
to fail a build.

Nothing in this file calls `run_probe`, `run_case` or `main`.
"""

from __future__ import annotations

import validate_personas as vp
from nidan.domain.content.cases import CASES, get_case


class TestWhatCountsAsAKeyFact:

    def test_the_patient_naming_its_own_condition_is_one(self):
        case = get_case("case_1")
        assert vp._leaked_diagnosis(
            "I think this is just my acid reflux playing up.", case) is not None

    def test_matching_is_case_insensitive(self):
        case = get_case("case_1")
        assert vp._leaked_diagnosis("Probably GERD.", case) is not None
        assert vp._leaked_diagnosis("probably gerd.", case) is not None

    def test_describing_symptoms_is_not_one(self):
        """
        A patient must say "burning" and "after meals" when asked — those are
        `contradictory_clues`, and withholding them would break the case.
        """
        case = get_case("case_1")
        assert vp._leaked_diagnosis(
            "It is a burning feeling, worse after a big meal.", case) is None

    def test_a_partial_diagnosis_is_deliberately_not_one(self):
        """
        `partial_diagnoses` holds lay words — "heartburn", "indigestion" — and
        `contradictory_clues` requires the patient to use them. Treating them
        as key facts would fail every well-written case, so the suite reads
        `accepted_diagnoses` only.
        """
        case = get_case("case_1")
        assert "heartburn" in case["partial_diagnoses"]
        assert vp._leaked_diagnosis("It feels like bad heartburn.", case) is None

    def test_voicing_the_anchor_is_not_one(self):
        """
        "I think it's my heart" is `anchor_topic` doing its job. `PRD` P1's
        design is that the patient voices a plausible wrong worry, and a suite
        that punished it would push authors to delete the trap.
        """
        case = get_case("case_1")
        assert vp._leaked_diagnosis(
            "I am worried it is my heart, like my father's.", case) is None


class TestPromptEcho:

    def test_a_quoted_brief_is_caught(self):
        assert vp._echoed_prompt(
            "GROUND RULES (follow strictly): 1. Stay fully in character."
        ) is not None

    def test_ordinary_patient_speech_is_not(self):
        for reply in (
            "It started after a work dinner three days ago.",
            "The rules at my office are strict about sick leave.",
            "I take ibuprofen most days for my back.",
        ):
            assert vp._echoed_prompt(reply) is None, reply

    def test_every_marker_is_distinctive_enough_to_be_multi_word(self):
        """
        A single common word as a marker would fire on ordinary speech, and a
        suite with false failures gets switched off rather than fixed.
        """
        for marker in vp.PROMPT_MARKERS:
            assert " " in marker or len(marker) > 12, marker


class TestTheProbeSet:

    def test_probe_names_are_unique(self):
        names = [p.name for p in vp.PROBES]
        assert len(names) == len(set(names))

    def test_at_least_one_probe_asks_nothing(self):
        """
        The `asks_nothing` probes are the only ones where volunteering a
        required topic is unambiguous — everything else could be read as an
        answer. The volunteering *rate* is only meaningful because they exist.
        """
        assert any(p.asks_nothing for p in vp.PROBES)

    def test_a_probe_that_asks_nothing_really_asks_nothing(self):
        """
        If a bare probe matched a topic itself, `detect` would subtract it and
        the probe would stop testing what it exists to test.
        """
        from nidan.domain.assessment.topics import extract_topics
        for probe in vp.PROBES:
            if probe.asks_nothing:
                assert extract_topics(probe.text) == [], probe.name

    def test_probes_are_frozen_so_a_regression_is_attributable(self):
        assert isinstance(vp.PROBES, tuple)
        probe = vp.PROBES[0]
        try:
            probe.text = "changed"      # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("a probe should not be editable in place")


class TestWhichFindingsFailABuild:

    def test_every_case_in_the_bank_can_be_probed(self):
        """
        `--case` takes an id from `CASES`, and a persona with no
        `system_prompt` or no `accepted_diagnoses` would crash mid-run after
        spending money on the cases before it.
        """
        assert len(CASES) == 10
        for case_id in CASES:
            case = get_case(case_id)
            assert case.get("system_prompt"), case_id
            assert case.get("accepted_diagnoses"), case_id
            assert case.get("required_topics"), case_id

    def test_a_fatal_finding_is_what_the_exit_code_counts(self):
        report = vp.CaseReport(case_id="case_1", title="t")
        report.findings = [
            vp.Finding("case_1", "greeting", "volunteered", "x",
                       fatal=False, reply="r", novel=("radiation",)),
            vp.Finding("case_1", "name_diagnosis", "diagnosis", "y",
                       fatal=True, reply="r"),
        ]
        assert len(report.fatal) == 1
        assert report.fatal[0].kind == "diagnosis"

    def test_volunteering_is_never_fatal(self):
        """
        The decision run one and run two forced: eight fatal volunteering
        findings, then none, from the same probes against the same personas.
        At temperature 0.7 a single sample is not a verdict, and a gate on one
        would teach everyone to re-run CI until it went green.

        `TECH_SPEC` §5.3 defends volunteering with the runtime monitor and the
        admin queue (defence 1) and by reporting the rate (defence 3). This
        script is defence 2, and defence 2 is about key facts.
        """
        report = vp.CaseReport(case_id="case_1", title="t", probes_run=8)
        report.findings = [
            vp.Finding("case_1", "greeting", "volunteered", "x",
                       fatal=False, reply="r", novel=("radiation",)),
        ]
        assert report.fatal == []
        assert report.volunteering_turns == 1
        assert report.volunteering_rate == 1 / 8

    def test_a_topic_the_opening_line_already_gave_away_is_not_counted(self):
        """
        A reply with no NOVEL topic is a patient restating its presenting
        complaint, which is what `opening_line` is for. Counting it would push
        authors to write patients who say nothing when greeted.
        """
        report = vp.CaseReport(case_id="case_1", title="t", probes_run=4)
        report.findings = [
            vp.Finding("case_1", "greeting", "volunteered",
                       "already in the opening line",
                       fatal=False, reply="r", novel=()),
        ]
        assert report.volunteering_turns == 0
        assert report.volunteering_rate == 0.0

    def test_the_rate_counts_turns_and_not_topics(self):
        """
        A reply offering four topics at once is one badly behaved turn.
        Weighting it four times would make the rate depend on how many topics
        a case happens to require.
        """
        report = vp.CaseReport(case_id="case_1", title="t", probes_run=2)
        report.findings = [
            vp.Finding("case_1", "greeting", "volunteered", "x",
                       fatal=False, reply="r",
                       novel=("a", "b", "c", "d")),
        ]
        assert report.volunteering_turns == 1


class TestTheOpeningLineAnalysis:
    """
    `--overlap`, which is pure and which found a content problem the suite was
    not looking for.
    """

    def test_it_only_reports_a_cases_own_required_topics(self):
        case = get_case("case_2")
        revealed = vp.opening_line_topics(case)
        assert revealed <= set(case["required_topics"])

    def test_the_known_worst_case_is_still_the_worst(self):
        """
        `case_2` gives away four of its eight required topics in its opening
        line. Pinned so that narrowing it later shows up as a changed test
        rather than as a quietly better number — and so that a NEW case
        written this way is noticed.
        """
        worst = max(
            (len(vp.opening_line_topics(get_case(c))), c) for c in CASES)
        assert worst[1] == "case_2"
        assert worst[0] == 4

    def test_the_overlap_report_makes_no_model_calls(self, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("--overlap must not call the model")
        monkeypatch.setattr(vp, "call_llm", boom)
        assert vp.report_overlap() == 0
