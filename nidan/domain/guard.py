"""
The real-patient-data guard (T-035).

`PRD` P4 is not a nicety: "All patients are synthetic. The product never
advises on a real case, and actively blocks attempts to enter real patient
data… it is what keeps us outside medical-device regulation." A trainee
pasting a ward patient into a synthetic simulator is the one input that
changes what this product legally is.

Pure — no I/O, no clock, no randomness, so it belongs in `domain/` and is
testable without a database or a model call.

## What it returns, and what it must never return

`detect()` returns a **reason code** or `None`. It never returns, logs or
echoes the matched text. `DATA_MODEL` §8.2 says `input_blocked` records
"never the offending text", and `domain/events.py` enforces it by refusing
the event if the payload carries `text`, `content`, `message` or `input`.
Storing what we blocked would put the very thing we refused into the table we
keep for ever, which makes the block worse than useless — it launders real
patient data into permanent storage under the name of protecting it.

The same reasoning applies to the API response: the 422 says *that* something
looked like patient data and which category, never which characters matched.

## Why it is deliberately conservative

A false block destroys a learner's typed question and teaches them the tool is
broken; `UX_SPEC` S-10's modal discards the question outright. A miss leaves
synthetic-patient practice contaminated by one real detail, which the P4
disclaimers also speak to. Those costs are not symmetrical, so this errs
towards letting text through:

- **A bare name does not block.** "Did Dr Mehta mention it?" and "Is this like
  Mrs Patel's case?" are things a learner says about teaching, not data they
  are pasting. A name blocks only with a structured identifier beside it.
- **A bare date does not block.** "Did the pain start before Diwali?" and
  "What happened on the 3rd?" are history taking. A date blocks only in
  date-of-birth shape or when labelled as one.
- **Ages do not block.** "A 54-year-old man" is how every case in the bank is
  written, including ours.

What does block is structure that has no innocent reading in a question to a
synthetic patient: a checksummed NHS number, an explicitly labelled hospital
or record number, a full date of birth, an email address, a phone number, a
postcode.

If this turns out to miss real pastes, the way to tighten it is evidence —
`input_blocked` reasons accumulate in the event log — not a guess. Loosening
it after learners have hit false blocks costs trust that is not cheap to
rebuild.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = ["Detection", "detect", "REASONS"]


# ── Reason codes ────────────────────────────────────────────────────
#
# These reach the learner's screen only as the fixed S-10 copy, and reach the
# event log as a bare string. They are deliberately coarse: a reason precise
# enough to reconstruct the input would defeat the point of not storing it.

REASONS: Final[frozenset[str]] = frozenset({
    "identifier",        # NHS-style number, labelled record/hospital number
    "date_of_birth",     # a full DOB, or a date labelled as one
    "contact_details",   # email address, telephone number, postcode
    "named_individual",  # a proper name sitting next to one of the above
})


@dataclass(frozen=True)
class Detection:
    """Why a question was refused. Carries no fragment of the input."""

    reason: str

    def __post_init__(self) -> None:
        if self.reason not in REASONS:
            raise ValueError(
                f"{self.reason!r} is not a guard reason; REASONS holds "
                f"{sorted(REASONS)} and the event log is queried by them")


# ── Patterns ────────────────────────────────────────────────────────
#
# Commonwealth-first, per D-9. Each is commented with what it must NOT catch,
# because that is the half that regressions break.

# An NHS number is 10 digits with a mod-11 check digit, written "943 476 5919"
# or "9434765919". The checksum is what makes this safe to block: a bare
# 10-digit run would also catch a phone number typed without spaces, and the
# arithmetic means a random 10-digit string passes about 1 time in 11.
_TEN_DIGITS = re.compile(r"\b(\d[\d\s-]{8,13}\d)\b")

# "hospital number 12345", "MRN: A4471", "record no. 889-23", "UHID 55021".
# The LABEL is doing the work. An unlabelled short number is a blood pressure,
# a dose, a ward, or a time, and must not block.
_LABELLED_ID = re.compile(
    r"\b(?:nhs(?:\s+number)?|hospital(?:\s+(?:number|no\.?|id))?"
    r"|mrn|uhid|urn|record\s+(?:number|no\.?)|patient\s+(?:number|no\.?|id)"
    r"|chart\s+(?:number|no\.?)|case\s+(?:number|no\.?)|crn)"
    r"\s*(?:[:#-]|\bis\b|\bno\.?\b)?\s*"
    r"([A-Z]{0,3}[\s-]?\d{3,}[\dA-Z/-]*)",
    re.I,
)

# A full date of birth: 03/04/1978, 3-4-78, 1978-04-03, 3 April 1978.
# Requires day AND month AND year, so "the 3rd" and "in April" pass, and
# "started in 2019" passes — a year alone is history, not an identifier.
_MONTHS = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
           r"|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?"
           r"|nov(?:ember)?|dec(?:ember)?")
_NUMERIC_DATE = re.compile(
    r"\b(?:0?[1-9]|[12]\d|3[01])\s*[/.\-]\s*(?:0?[1-9]|1[0-2])\s*[/.\-]\s*"
    r"(?:19|20)?\d{2}\b"
    r"|\b(?:19|20)\d{2}\s*[/.\-]\s*(?:0?[1-9]|1[0-2])\s*[/.\-]\s*"
    r"(?:0?[1-9]|[12]\d|3[01])\b"
)
_WORDED_DATE = re.compile(
    rf"\b(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTHS})"
    rf"\s+(?:19|20)\d{{2}}\b"
    rf"|\b(?:{_MONTHS})\s+(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?,?\s+"
    rf"(?:19|20)\d{{2}}\b",
    re.I,
)
# "DOB 3/4/78", "date of birth: 1978", "born 03.04.1978" — the label lowers the
# bar to a year, because nothing innocent labels a year as a birth date.
_LABELLED_DOB = re.compile(
    r"\b(?:d\.?o\.?b\.?|date\s+of\s+birth|born(?:\s+on)?)\s*"
    r"(?:[:#-]|\bis\b)?\s*\d",
    re.I,
)

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# +44 7700 900123, 07700 900123, (022) 2654 3210, +91 98765 43210.
#
# Three shapes rather than one optional prefix: a country code, parentheses,
# or a trunk zero. Each is a positive signal on its own, and requiring one of
# them is what keeps doses ("500 mg", "2.5 mg"), vitals ("132/84"), times
# ("3pm") and counts ("14 units") out. An earlier version made the country
# code optional in front of a mandatory 0-or-bracket group, which silently
# failed to match "+44 7700 900123" — the most ordinary form there is.
_PHONE = re.compile(
    r"\+\d{1,3}[\s-]?\d[\d\s-]{6,12}\d"        # +44 7700 900123
    r"|\(\d{2,5}\)[\s-]?\d[\d\s-]{5,12}\d"     # (022) 2654 3210
    r"|\b0\d{1,4}[\s-]?\d[\d\s-]{5,12}\d\b"    # 07700 900123
)

# UK postcodes: SW1A 1AA, M1 1AE, CR2 6XH. The format is distinctive enough
# that false positives need a deliberate effort.
_POSTCODE = re.compile(
    r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b"
)

# Two capitalised words, or a title plus a capitalised word. On its own this
# catches "Last Tuesday" and "Is Diwali", so it NEVER blocks alone — it only
# upgrades a hit that already fired.
_PROPER_NAME = re.compile(
    r"\b(?:(?:Mr|Mrs|Ms|Miss|Dr|Prof|Master|Baby)\.?\s+[A-Z][a-z]{1,})"
    r"|\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b"
)


def _nhs_checksum_passes(digits: str) -> bool:
    """
    Mod-11 on 10 digits: weights 10..2 over the first nine, check digit is
    11 - (sum % 11), where 11 means 0 and 10 means the number is invalid.
    """
    if len(digits) != 10:
        return False
    # `strict=True`: nine digits against nine weights. If either side ever
    # changes length the sum would silently be computed over the shorter one,
    # and a checksum that quietly stops checking is the worst outcome here —
    # it would turn the 10-digit rule back into "any ten digits block".
    total = sum(int(d) * w
                for d, w in zip(digits[:9], range(10, 1, -1), strict=True))
    remainder = 11 - (total % 11)
    if remainder == 11:
        remainder = 0
    if remainder == 10:
        return False
    return remainder == int(digits[9])


def _has_nhs_number(text: str) -> bool:
    for match in _TEN_DIGITS.finditer(text):
        digits = re.sub(r"\D", "", match.group(1))
        if len(digits) == 10 and _nhs_checksum_passes(digits):
            return True
    return False


def detect(text: str) -> Detection | None:
    """
    Decide whether `text` looks like real patient data.

    Returns a `Detection` carrying a reason code, or `None` to let it through.
    Never returns any part of `text` — see the module docstring.

    Order matters only for which reason is reported, not for whether the
    question is blocked. Identifiers are checked first because they are the
    least ambiguous thing in the set, and the most useful reason to see in the
    event log.
    """
    if not text or not text.strip():
        return None

    # An identifier is the clearest signal: a checksummed NHS number, or a
    # number a human has labelled as a record.
    if _has_nhs_number(text) or _LABELLED_ID.search(text):
        return Detection("identifier")

    # A date of birth. A full date, or any date explicitly labelled as one.
    if (_LABELLED_DOB.search(text)
            or _NUMERIC_DATE.search(text)
            or _WORDED_DATE.search(text)):
        return Detection("date_of_birth")

    # Contact details have no legitimate place in a question to a synthetic
    # patient, and no innocent reading.
    if (_EMAIL.search(text)
            or _POSTCODE.search(text)
            or _PHONE.search(text)):
        return Detection("contact_details")

    return None


def names_an_individual(text: str) -> bool:
    """
    Whether `text` also carries something name-shaped.

    Exposed for the `named_individual` reason, which is reported when a
    detection coincides with a proper name — the clearest case of a real
    person. It is **never a detection on its own**: `_PROPER_NAME` matches
    "Last Tuesday" and "Is Diwali", and blocking those would cost a learner a
    question for writing ordinary English.
    """
    return bool(_PROPER_NAME.search(text))


def classify(text: str) -> Detection | None:
    """
    `detect()`, but upgrading the reason to `named_individual` when a proper
    name sits beside the identifier.

    This is what the route calls. The distinction matters for admin review:
    a bare identifier may be a learner testing the guard, while an identifier
    next to a name is a real person's record being pasted in.
    """
    found = detect(text)
    if found is None:
        return None
    if names_an_individual(text):
        return Detection("named_individual")
    return found
