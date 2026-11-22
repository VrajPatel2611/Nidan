"""
The two emails the account jobs worker sends (T-038).

Pure functions, so these run without a database, a provider or a network. The
copy matters more than most strings in this project: the deletion confirmation
is the only notice a user gets that their account is gone, and `UX_SPEC` S-20
promises specific things in it.
"""

from __future__ import annotations

import json

import pytest

from nidan.api.v1.reasoning import BANNED_VOCABULARY
from nidan.infra.email.port import Email
from nidan.jobs import messages

ADDRESS = "learner@example.test"


def _text(message: Email) -> str:
    """Everything a recipient can read, including attachment bytes."""
    parts = [message.subject, message.body]
    parts += [blob.decode("utf-8") for blob in message.attachments.values()]
    return "\n".join(parts).lower()


# ── CT-5: the vocabulary ban applies to email too ───────────────────────

@pytest.mark.parametrize("build", [
    lambda: messages.export_email(ADDRESS, _payload()),
    lambda: messages.erasure_email(ADDRESS, events_redacted=51,
                                   feedback_redacted=2),
])
def test_no_bias_vocabulary_reaches_an_inbox(build):
    """
    `PRD` P1 bans the words from user-facing text, and an email is user-facing.

    CT-5 is enforced on API responses, and nothing watched this path: the
    worker could have written "we detected anchoring in your consultations"
    and every contract test would still pass. The export is the real risk —
    it is assembled from database rows, and `session_results` has eight
    columns whose names contain the banned terms.
    """
    body = _text(build())
    found = [word for word in BANNED_VOCABULARY if word in body]
    assert not found, f"banned vocabulary in an email: {found}"


def test_the_export_attachment_is_valid_json():
    """
    The attachment is parsed, not just non-empty.

    `json.dumps` of a payload containing a `Decimal` or a `datetime` raises,
    and it would raise inside the emailing step — after the export had been
    built, so the failure would be recorded against the wrong step.
    """
    message = messages.export_email(ADDRESS, _payload())
    blob = message.attachments["nidan-export.json"]
    parsed = json.loads(blob)
    assert parsed["sessions"][0]["case_slug"] == "chest-pain-gerd"


def test_the_export_says_what_is_not_in_it():
    """
    `DATA_MODEL` §10.2 and S-20 both require the retained data to be named.

    The file is what gets kept, so the covering note carries it as well as the
    screen — a user reading the export a year later has no screen.
    """
    body = messages.export_email(ADDRESS, _payload()).body.lower()
    assert "research pseudonym" in body
    assert "not your data" in body or "not in it" in body


def test_the_export_pluralises_one_consultation_correctly():
    """A trivial check, and the one thing a reader notices immediately."""
    one = messages.export_email(ADDRESS, {"sessions": [{}]}).body
    two = messages.export_email(ADDRESS, {"sessions": [{}, {}]}).body
    assert "1 consultation," in one and "1 consultations" not in one
    assert "2 consultations," in two


# ── S-20's promises, in the confirmation ────────────────────────────────

def test_the_confirmation_names_everything_s20_promises():
    body = messages.erasure_email(ADDRESS, events_redacted=51,
                                  feedback_redacted=2).body.lower()
    for promise in ("cannot be undone", "credential", "anonymised results",
                    "random code", "reproducible"):
        assert promise in body, f"S-20 promises {promise!r} and it is missing"


def test_the_confirmation_carries_the_counts_it_was_given():
    """
    Not recomputed. By the time this is sent the redaction has happened, so
    recomputing would give zero — the counts come from the erasure's own
    `audit_log` row, which is what the transaction actually did.
    """
    body = messages.erasure_email(ADDRESS, events_redacted=51,
                                  feedback_redacted=2).body
    assert "51 entries redacted" in body
    assert "2 consultation(s)" in body


def test_zero_counts_are_still_stated():
    """
    A learner who deleted an account before using it gets zeros, not a
    sentence about having had nothing. The copy must not become a different
    message at the boundary.
    """
    body = messages.erasure_email(ADDRESS, events_redacted=0,
                                  feedback_redacted=0).body
    assert "0 entries redacted" in body


def test_the_confirmation_has_no_attachment():
    """
    Deliberate: there is nothing to attach, and attaching the export here
    would send a copy of the data to the address being deleted, which is the
    opposite of what was asked for.
    """
    assert messages.erasure_email(ADDRESS, events_redacted=1,
                                  feedback_redacted=1).attachments == {}


# ── the address never ends up in a log line ─────────────────────────────

def test_redacted_hides_the_address_but_distinguishes_two_sends():
    """
    `SECURITY_SPEC` L7: an address is personal data, and a worker log is the
    easiest place for one to be persisted somewhere nobody is thinking about.
    `redacted()` is what `runner._send` logs.
    """
    message = messages.export_email("vraj.patel@example.test", _payload())
    line = message.redacted()
    assert "vraj.patel" not in line
    assert "v***@example.test" in line
    # Still useful: two different messages must not render identically.
    other = messages.erasure_email("vraj.patel@example.test",
                                   events_redacted=1, feedback_redacted=1)
    assert line != other.redacted()


def _payload() -> dict:
    return {
        "export_version": "1",
        "profile": {"display_name": "A Learner", "country": "IN"},
        "sessions": [{
            "session_id": "11111111-1111-1111-1111-111111111111",
            "case_slug": "chest-pain-gerd",
            "case_title": "The Chest Pain Trap",
            "coverage_pct": 79.7,
            "diagnosis_verdict": "anchored",
            "transcript": [
                {"seq": 1, "type": "question", "payload": {"text": "Any chest pain?"}},
            ],
            "feedback": {"lines": ["You asked 6 of 8 questions about one cause."]},
        }],
        "notes": ["x"],
    }
