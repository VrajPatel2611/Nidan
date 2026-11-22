"""
The two messages the account jobs worker sends (T-038).

Pure functions: data in, an `Email` out. No I/O, so the wording is testable
without a database, a provider or a network — which matters more than usual
here, because the copy makes promises (`UX_SPEC` S-20) and one of them is the
only notice a user gets that their account is gone.

**British English** (`CLAUDE.md` conventions) and **no bias vocabulary**
(`PRD` P1): the export's covering note describes what is in the file, and a
sentence about "anchoring" in an email would be the CT-5 leak by a route no
contract test watches.
"""

from __future__ import annotations

import json
from typing import Any

from nidan.infra.email.port import Email

EXPORT_SUBJECT = "Your Nidan data export"
ERASURE_SUBJECT = "Your Nidan account has been deleted"


def export_email(to: str, payload: dict[str, Any]) -> Email:
    """
    The export, as an attached JSON file.

    Attached rather than linked. A link needs a signed URL, somewhere to host
    the file and an expiry policy, and it means the export sits on a server
    after the user has it — three decisions and a retention question, to avoid
    an attachment. `PRD` 1.9 asks for JSON, not for a download page.
    """
    sessions = payload.get("sessions", [])
    blob = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    body = (
        "You asked for a copy of your Nidan data.\n"
        "\n"
        f"It is attached as JSON: {len(sessions)} consultation"
        f"{'' if len(sessions) == 1 else 's'}, with the questions you asked, "
        "the patient's replies, your diagnoses and the feedback you were "
        "shown.\n"
        "\n"
        "What is not in it: the clinical cases themselves, and the research "
        "pseudonym that links anonymised results to your account. The first "
        "is not your data; the second is the key that keeps those results "
        "anonymous, and a copy of it in a file would undo that.\n"
        "\n"
        "If anything looks wrong, reply to this message.\n"
    )
    return Email(to=to, subject=EXPORT_SUBJECT, body=body,
                 attachments={"nidan-export.json": blob})


def erasure_email(to: str, *, events_redacted: int,
                  feedback_redacted: int) -> Email:
    """
    The confirmation S-20 promises, sent before the address is removed.

    It repeats "what we keep, and why" from the screen rather than linking to
    it, because the account is gone and the user cannot sign in to read the
    screen again. The counts are included because they are the only concrete
    evidence the user gets that anything happened — and they come from the
    erasure's own `audit_log` row, so the email cannot claim more than the
    transaction did.
    """
    body = (
        "Your Nidan account has been deleted. This cannot be undone.\n"
        "\n"
        "What has been removed:\n"
        "  · Your name, professional details and country\n"
        f"  · Everything you and the patient typed — {events_redacted} entries "
        "redacted\n"
        f"  · The feedback written about it — {feedback_redacted} "
        "consultation(s)\n"
        "  · Your sign-in credential, so no device remains signed in\n"
        "\n"
        "What we keep, and why:\n"
        "  Anonymised results — coverage scores and outcomes — linked only to "
        "a random code and never to you. This keeps published research "
        "reproducible. They cannot be traced back to you, and they are not "
        "used for anything else.\n"
        "\n"
        "This is the last message you will receive from us.\n"
    )
    return Email(to=to, subject=ERASURE_SUBJECT, body=body)
