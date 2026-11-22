"""
The real-patient-data guard — T-035 criterion 1.

Two halves, and the second is the one that matters more. Catching a pasted
record is the point; **not** blocking a learner who wrote ordinary English is
what decides whether they trust the tool, because `UX_SPEC` S-10 discards the
question when the guard fires. A false block costs real work.

So the false-positive class below is deliberately drawn from how the ten cases
in the bank are actually written, and from the questions the 16 pilot sessions
contain.
"""

from __future__ import annotations

import pytest

from nidan.domain.guard import (
    REASONS,
    Detection,
    classify,
    detect,
    names_an_individual,
)


class TestBlocksRealIdentifiers:
    """Criterion 1: identifiers, DOBs, hospital numbers, named individuals."""

    @pytest.mark.parametrize("text", [
        # Valid NHS numbers (mod-11 checksum passes).
        "the patient's NHS number is 943 476 5919",
        "9434765919 — what should I ask?",
        "nhs 943-476-5919",
    ])
    def test_a_checksummed_nhs_number_blocks(self, text):
        assert detect(text) == Detection("identifier")

    @pytest.mark.parametrize("text", [
        "hospital number 1123456",
        "MRN: A4471",
        "his record number is 889231",
        "UHID 55021 — does he drink?",
        "patient ID 77213",
        "chart no. 4471",
    ])
    def test_a_labelled_record_number_blocks(self, text):
        assert detect(text) == Detection("identifier")

    @pytest.mark.parametrize("text", [
        "DOB 03/04/1978",
        "date of birth: 1978",
        "born on 3.4.1978",
        "03/04/1978",
        "1978-04-03",
        "3rd April 1978",
        "April 3, 1978",
    ])
    def test_a_date_of_birth_blocks(self, text):
        assert detect(text).reason == "date_of_birth"

    @pytest.mark.parametrize("text", [
        "email me at ward7@nhs.net",
        "his number is 07700 900123",   # trunk zero
        "+44 7700 900123",              # country code
        "+91 98765 43210",              # country code, Indian mobile
        "(022) 2654 3210",              # parenthesised area code
        "he lives at SW1A 1AA",
        "postcode CR2 6XH",
    ])
    def test_contact_details_block(self, text):
        assert detect(text).reason == "contact_details"

    def test_a_name_beside_an_identifier_reports_a_named_individual(self):
        """
        The distinction exists for admin review: a bare identifier may be
        someone testing the guard; an identifier next to a name is a real
        person's record.
        """
        assert classify("Mrs Patel, hospital number 1123456") == \
            Detection("named_individual")
        assert classify("hospital number 1123456") == Detection("identifier")


class TestDoesNotBlockOrdinaryQuestions:
    """
    The half that decides whether learners trust it.

    Every string here is a question a trainee could reasonably type, or a
    phrase drawn from how the case bank is written.
    """

    @pytest.mark.parametrize("text", [
        # History taking — the product's whole purpose.
        "Is the pain burning or crushing?",
        "Does it get worse after meals?",
        "When did the pain start?",
        "Has this happened before?",
        "Any family history of heart disease?",
        "What medications are you taking?",
        "Do you smoke? How many a day?",
        # Dates and times that are not dates of birth.
        "Did the pain start before Diwali?",
        "What happened on the 3rd?",
        "Has it been going on since April?",
        "Did this start in 2019?",
        "Is it worse at 3pm?",
        "Have you had it for 3 days?",
        "Did it begin about 2 weeks ago?",
        # Numbers that are clinical, not identifiers.
        "Are you taking 500 mg or 1 g?",
        "Was the BP 132/84?",
        "Is the heart rate above 100?",
        "Did they give you 2.5 mg of bisoprolol?",
        "Was your temperature 38.5?",
        "Is the sat 94% on air?",
        "How many units of alcohol a week — more than 14?",
        # Names without any identifier beside them.
        "Did Dr Mehta mention anything about this?",
        "Is this like the case Professor Rao taught?",
        "Have you seen Mrs Sharma about it?",
        "Did the GP refer you?",
        # Ages — how every case in the bank is written.
        "A 54-year-old man with chest pain",
        "Are you 54?",
        "Did it start when you were 40?",
        # Clinical phrasing that trips naive patterns.
        "Any chest pain on exertion?",
        "Does it radiate to the left arm?",
        "Any orthopnoea or PND?",
        "Is there a history of HLA-B27 positivity?",
        "Did the ECG show ST elevation in II, III and aVF?",
    ])
    def test_a_legitimate_question_passes(self, text):
        found = detect(text)
        assert found is None, (
            f"the guard blocked a legitimate question: {text!r} → "
            f"{found.reason if found else None}. A false block discards the "
            f"learner's question (UX_SPEC S-10) and teaches them the tool is "
            f"broken"
        )

    def test_an_invalid_ten_digit_run_does_not_block(self):
        """
        The mod-11 checksum is what makes blocking a 10-digit run safe: a bare
        run of ten digits is also an Indian mobile number or a phone typed
        without spaces, and the arithmetic rejects about ten in eleven of them.

        `9434765918` is `9434765919` with the check digit changed, so it is the
        same shape and fails the sum.
        """
        assert detect("9434765918") is None

    def test_a_ten_digit_run_that_passes_the_checksum_does_block(self):
        """
        Worth stating because it looks like a false positive and is not.

        `9999999999` satisfies mod-11 (weights sum to 486; 486 % 11 = 2;
        11 - 2 = 9, the tenth digit), so the guard blocks it. I wrote this
        test the other way round first and the implementation was right.

        It is the correct outcome either way: a learner does not type ten
        digits into a question to a synthetic patient, and if they do, a
        ten-digit run is itself either an identifier or a phone number —
        both of which this guard exists to stop.
        """
        assert detect("9999999999") == Detection("identifier")

    def test_an_unlabelled_short_number_does_not_block(self):
        """A ward, a dose, a bed, a time. The label is what carries meaning."""
        for text in ("ward 7", "bed 12", "bay 3", "room 214", "4471"):
            assert detect(text) is None, text


class TestItNeverCarriesTheInput:
    """
    `DATA_MODEL` §8.2 — "never the offending text". The reason is the only
    thing that leaves this module, and `domain/events.py` refuses the event if
    the payload carries the text.
    """

    def test_the_detection_carries_only_a_reason(self):
        secret = "NHS number 943 476 5919"
        found = detect(secret)
        assert found is not None
        # The dataclass has exactly one field, and it is a catalogued code.
        assert set(vars(found)) == {"reason"}
        assert found.reason in REASONS

    def test_no_fragment_of_the_input_appears_in_the_detection(self):
        secret = "Mrs Patel DOB 03/04/1978 hospital number 1123456"
        found = classify(secret)
        rendered = repr(found)
        for fragment in ("Patel", "03/04/1978", "1123456", "1978"):
            assert fragment not in rendered, (
                f"{fragment!r} leaked into the detection, which is written to "
                f"the event log"
            )

    def test_a_reason_outside_the_catalogue_is_refused(self):
        """
        The event log is queried by these strings. A typo that only shows up
        as a row nobody can find later is worth failing loudly for.
        """
        with pytest.raises(ValueError, match="not a guard reason"):
            Detection("looked_dodgy")


class TestEdges:

    @pytest.mark.parametrize("text", ["", "   ", "\n\t "])
    def test_empty_input_is_not_a_detection(self, text):
        """The route rejects empty questions before the guard sees them."""
        assert detect(text) is None

    def test_a_proper_name_alone_is_never_a_detection(self):
        """
        `names_an_individual` is true for things that are not names at all —
        which is exactly why it may not block on its own.
        """
        assert names_an_individual("Last Tuesday")
        assert detect("Last Tuesday") is None
        assert classify("Last Tuesday") is None

    def test_the_longest_allowed_question_does_not_hang(self):
        """
        500 characters is the cap (FR-4.1). Catastrophic backtracking in one
        of these patterns would be a denial of service on the hot path.
        """
        import time
        text = ("does the pain radiate anywhere and is it worse on exertion "
                * 9)[:500]
        start = time.monotonic()
        detect(text)
        assert time.monotonic() - start < 0.05
