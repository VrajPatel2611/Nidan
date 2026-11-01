"""
The only place a case becomes a response (`API_CONTRACT` §6 · `PRD` FR-3.4).

**This module exists so that there is exactly one of it.** `POST /sessions` and
`GET /sessions/{id}` both return a `case` object, and the contract says it must
carry only presentation fields:

> ⚠️ **Critical constraint (`PRD` FR-3.4).** The `case` object contains **only**
> presentation fields. It must not contain `correct_diagnosis`, `anchor_topic`,
> `anchor_keywords`, `required_topics`, `contradictory_clues`,
> `investigations`, `examination`, or `system_prompt`.

Two serialisers would satisfy CT-1 on the day they were written and diverge
later, and the one that diverged would be the one no test happened to cover.

**Built by naming what goes in, never by removing what must not.** The stored
content (`DATA_MODEL` §8.1) has sixteen top-level keys and eight of them are
forbidden here; a serialiser that copied the dict and deleted the bad keys
would leak the first key anyone adds. `case_versions.content` is JSONB, so a
new key needs no migration and no review — it can arrive in a case editor save.

CT-1 is the test, and `PRD` FR-3.4 is why it is called "the leak that would
invalidate everything": a learner who can read `anchor_keywords` knows which
questions the detector is watching for, and every measurement taken afterwards
is of something else.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

# Named here so the test can assert against the same list the contract gives,
# rather than a transcription of it that could drift the other way.
FORBIDDEN: Final[frozenset[str]] = frozenset({
    "correct_diagnosis", "anchor_topic", "anchor_keywords", "required_topics",
    "contradictory_clues", "investigations", "examination", "system_prompt",
    # Not named by §6, and every bit as disqualifying. `accepted_diagnoses`
    # and `partial_diagnoses` are the answer key; `alternative_topics` is the
    # other half of the anchoring detector's vocabulary; `minimum_questions`
    # is a target, and `PRD` P2 forbids showing one.
    "accepted_diagnoses", "partial_diagnoses", "alternative_topics",
    "minimum_questions",
})

# What a learner is allowed to know about the patient before asking anything.
_PATIENT_FIELDS: Final = ("name", "age", "sex", "presenting_complaint", "intro")


def case_json(content: Mapping[str, Any]) -> dict[str, Any]:
    """
    The `case` object, from a `case_versions.content` row.

    `opening_line` is stored inside `patient` (`DATA_MODEL` §8.1) and returned
    beside it (`API_CONTRACT` §6). The difference is not worth reconciling in
    the schema — the stored shape groups everything the patient "is", and the
    response shape separates what is displayed as a profile from what is
    displayed as their first line of speech.
    """
    patient = content.get("patient") or {}
    return {
        "title": content.get("title"),
        "patient": {field: patient.get(field) for field in _PATIENT_FIELDS},
        "opening_line": patient.get("opening_line"),
    }
