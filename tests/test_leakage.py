"""
`domain/leakage.py` — the persona-leakage detector (T-040).

Pure: no database, no network, no clock. The same properties the engine's
tests assert, for the same reason — a flag is evidence, and evidence that
cannot be recomputed from the log is not evidence (`ADR-0003`).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from nidan.domain.events import Event
from nidan.domain.leakage import Leak, detect, topics_asked

REQUIRED = ("pain_character", "meal_relationship", "radiation",
            "family_history")


def _event(seq: int, type_: str, text: str | None = None) -> Event:
    payload = {} if text is None else {"text": text}
    return Event(seq=seq, type=type_, payload=payload,
                 created_at=datetime(2026, 11, 24, tzinfo=UTC))


class TestWhatCountsAsALeak:

    def test_a_topic_in_the_reply_that_the_question_did_not_ask_about(self):
        leak = detect(reply="It also spreads into my left arm.",
                      question="How long has this been going on?",
                      required_topics=REQUIRED)
        assert leak == Leak(topics=("radiation",), severity="high")

    def test_answering_what_was_asked_is_not_a_leak(self):
        assert detect(reply="No, it does not radiate anywhere.",
                      question="Does the pain radiate at all?",
                      required_topics=REQUIRED) is None

    def test_a_topic_outside_the_required_list_is_not_a_leak(self):
        """
        Coverage is scored over `required_topics`, so an unrequired topic
        cannot inflate it. Narrowing to the required set is the definition of
        the measurement being affected, not a convenience.
        """
        assert detect(reply="I sleep badly and my work is stressful.",
                      question="Hello.",
                      required_topics=("radiation",)) is None

    def test_a_case_with_no_required_topics_can_never_leak(self):
        assert detect(reply="It spreads to my arm after every meal.",
                      question="Hello.", required_topics=()) is None

    def test_several_leaked_topics_come_back_sorted(self):
        """
        Sorted so two runs over the same log produce the same
        `leaked_topics` array. An array whose order moves between runs cannot
        be diffed against a recomputation.
        """
        leak = detect(
            reply="It is a burning pain after meals and it spreads to my arm.",
            question="Hello.", required_topics=REQUIRED)
        assert leak is not None
        assert leak.topics == tuple(sorted(leak.topics))
        assert set(leak.topics) == {"pain_character", "meal_relationship",
                                    "radiation"}


class TestSeverity:
    """
    The split is the consequence, not the size. `high` means the session's
    numbers are wrong; `low` means the patient repeated itself.
    """

    def test_high_when_the_learner_never_asked_about_it(self):
        leak = detect(reply="It spreads to my arm.", question="Hello.",
                      required_topics=REQUIRED, asked_before=())
        assert leak is not None and leak.severity == "high"

    def test_low_when_an_earlier_question_had_already_covered_it(self):
        leak = detect(reply="As I said, it spreads to my arm.",
                      question="Hello.", required_topics=REQUIRED,
                      asked_before={"radiation"})
        assert leak is not None and leak.severity == "low"

    def test_high_when_any_one_of_several_was_never_asked(self):
        """
        One corrupted topic corrupts the session's coverage figure, so a
        mixed leak takes the worse severity rather than an average.
        """
        leak = detect(reply="It spreads to my arm, and it burns after meals.",
                      question="Hello.", required_topics=REQUIRED,
                      asked_before={"radiation"})
        assert leak is not None and leak.severity == "high"

    def test_asked_before_never_decides_whether_there_is_a_leak(self):
        """
        §7.2's rule is per-turn: revealed, and not asked for *here*. Earlier
        questions change the severity and nothing else — a patient that keeps
        volunteering an answer is still volunteering it.
        """
        kwargs = dict(reply="It spreads to my arm.", question="Hello.",
                      required_topics=REQUIRED)
        assert detect(**kwargs, asked_before=()) is not None
        assert detect(**kwargs, asked_before=set(REQUIRED)) is not None


class TestTopicsAsked:

    def test_reads_questions_and_ignores_everything_else(self):
        events = [
            _event(1, "session_started"),
            _event(2, "question", "Does it radiate anywhere?"),
            _event(3, "patient_reply", "It burns after every meal."),
            _event(4, "examination", None),
        ]
        # `radiation` from the question is in. What the REPLY said is not —
        # those are the topics we are trying to detect, and counting them
        # would make every leak invisible on the following turn.
        #
        # Asserted as membership rather than equality because the lexicon is
        # shared across all ten cases and one phrase legitimately matches
        # several topics ("arm" is `radiation` and `focal_neuro_signs`). A
        # test pinned to the exact set would fail on every lexicon addition
        # and say nothing about this function.
        asked = topics_asked(events)
        assert "radiation" in asked
        assert "meal_relationship" not in asked
        assert "pain_character" not in asked

    def test_a_question_with_no_text_is_skipped_not_fatal(self):
        """
        Migration 033's erasure rewrites `payload->'text'` to
        `"[redacted]"`, and a replay of an erased session must still run.
        """
        events = [_event(1, "question"), _event(2, "question", "[redacted]")]
        assert topics_asked(events) == set()

    def test_it_accumulates_across_the_whole_log(self):
        events = [
            _event(1, "question", "Does it radiate?"),
            _event(2, "question", "Any family history of this?"),
        ]
        assert {"radiation", "family_history"} <= topics_asked(events)


class TestItIsDeliberatelySensitive:
    """
    The opposite of `domain/guard.py`, and the asymmetry is the point: a false
    flag costs an administrator one click, a miss costs the validity of every
    measurement taken through that persona.
    """

    def test_a_substring_match_is_enough(self):
        leak = detect(reply="My father had something similar.",
                      question="Hello.", required_topics=("family_history",))
        assert leak is not None

    def test_the_detector_never_excludes_anything_itself(self):
        """
        `detect` returns a severity and no verdict. Only `confirmed = true`,
        written by a person, removes a session from the research export —
        there is no code path by which a detector discards its own
        inconvenient data (`ADR-0005`).
        """
        leak = detect(reply="It spreads to my arm.", question="Hello.",
                      required_topics=REQUIRED)
        assert leak is not None
        assert not hasattr(leak, "confirmed")
        assert not hasattr(leak, "exclude")
        assert set(vars(leak)) == {"topics", "severity"}


class TestTheShapeIsFrozen:

    def test_a_leak_cannot_be_edited_after_it_is_made(self):
        leak = Leak(topics=("radiation",), severity="high")
        with pytest.raises(dataclasses.FrozenInstanceError):
            leak.severity = "low"       # type: ignore[misc]
