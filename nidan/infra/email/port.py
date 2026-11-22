"""
The email seam: what the worker needs from a sender, and nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class EmailSendFailed(RuntimeError):
    """
    The message was not sent, and the worker should retry.

    A distinct type because the worker's retry decision turns on it: a send
    that failed is a step to attempt again, while a `ValueError` from building
    the message is a bug that retrying cannot fix. Conflating them gives you a
    job that retries a programming error five times and then gives up on a
    user's data request.
    """


@dataclass(frozen=True)
class Email:
    """
    One message, built before anything is sent.

    `attachments` maps a filename to bytes. The export is the only user of it
    and it is a single JSON file, so there is no streaming here and no
    multipart assembly; an adapter that needs MIME builds it from this.

    **`to` is kept out of every log line this project writes.** An address is
    personal data under `SECURITY_SPEC` L7, and a worker log is the easiest
    place in a system for one to end up persisted somewhere nobody is thinking
    about. `redacted()` is what the worker logs instead.
    """

    to: str
    subject: str
    body: str
    attachments: dict[str, bytes] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if "@" not in self.to or self.to.startswith("@") or self.to.endswith("@"):
            raise ValueError(f"not a sendable address: {self.to!r}")
        if not self.subject.strip():
            raise ValueError("an email with no subject is a bug, not a message")
        if not self.body.strip():
            raise ValueError("an email with no body is a bug, not a message")

    def redacted(self) -> str:
        """
        The message, described without naming the recipient.

        `v***@example.com` — enough to tell two sends apart when reading a log,
        not enough to be a disclosure if the log is shipped somewhere.
        """
        local, _, domain = self.to.partition("@")
        masked = f"{local[:1]}***@{domain}" if local else f"***@{domain}"
        return (f"{masked} · {self.subject!r}"
                + (f" · {len(self.attachments)} attachment(s)"
                   if self.attachments else ""))


@dataclass(frozen=True)
class Sent:
    """
    Proof that an adapter did something, recorded in the audit row.

    `reference` is whatever the adapter can be held to afterwards — a provider
    message id, or the path of the file the outbox wrote. Never the address:
    the audit row for an erasure must not keep the address the erasure removed.
    """

    adapter: str
    reference: str


class EmailPort(Protocol):
    """One method. A sender either sends or raises `EmailSendFailed`."""

    name: str

    def send(self, message: Email) -> Sent:
        ...
