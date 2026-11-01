"""
Cursor pagination (`API_CONTRACT` §2.5).

§2.5 is explicit about why offsets are not offered: "it produces duplicates and
gaps when rows are inserted mid-scroll." A learner finishing a consultation
while paging back through their history would see one session twice and another
not at all, and neither would look like a bug to them.

The cursor is an opaque base64 string by contract. It is **not** encryption and
nothing here pretends otherwise — a caller who decodes it finds the sort key of
the last row they were given, which they already had. Opaque means "do not
build on its shape", so that this can change to a composite key later without
breaking a client that was parsing it.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from typing import Any, Final

DEFAULT_LIMIT: Final = 20
MAX_LIMIT: Final = 100


class InvalidCursor(ValueError):
    """
    A cursor that did not come from us, or came from an older encoding.

    Surfaced as `validation_failed` rather than ignored. Silently returning
    page one for a corrupt cursor makes an infinite scroll restart with no
    error, which reads as data loss.
    """


def encode_cursor(payload: dict[str, Any]) -> str:
    """
    Opaque, URL-safe, unpadded. Unpadded because a cursor travels in a query
    string and `=` there survives most clients but not all of them.
    """
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True,
                     default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise InvalidCursor("not a cursor we issued") from exc
    if not isinstance(payload, dict):
        raise InvalidCursor("not a cursor we issued")
    return payload


def read_limit(raw: str | None) -> int:
    """
    §2.5: "`limit` defaults to 20, maximum 100."

    A limit above the maximum is clamped rather than refused. The alternative
    is a 422 on a request that is merely optimistic, and the contract states a
    maximum rather than a validation rule.
    """
    if raw is None or raw == "":
        return DEFAULT_LIMIT
    try:
        value = int(raw)
    except ValueError:
        raise InvalidCursor(f"limit must be a whole number, not {raw!r}") from None
    if value < 1:
        raise InvalidCursor("limit must be at least 1")
    return min(value, MAX_LIMIT)


def page(rows: list[Any], limit: int, *, cursor_for) -> dict[str, Any]:
    """
    The §2.5 envelope, given one row MORE than the caller asked for.

    Fetching `limit + 1` is how `has_more` is answered without a second
    COUNT query — and a COUNT would be answering a different question anyway,
    since rows can appear between the two statements.

    `cursor_for` turns the last returned row into the cursor that resumes
    after it. Passed in rather than assumed, because the sort key differs by
    collection and a shared helper that guessed would be wrong somewhere.
    """
    has_more = len(rows) > limit
    visible = rows[:limit]
    return {
        "pagination": {
            "next_cursor": cursor_for(visible[-1]) if (has_more and visible) else None,
            "has_more": has_more,
        }
    }


def iso(value: datetime | None) -> str | None:
    """Timestamps are ISO-8601 UTC throughout (`API_CONTRACT` §2.4)."""
    return value.isoformat() if value is not None else None
