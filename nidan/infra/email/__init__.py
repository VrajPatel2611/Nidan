"""
Outbound email (BUILD_PLAN T-038).

Two messages exist in the whole product: the data export (`PRD` FR-11.3) and
the deletion confirmation (`UX_SPEC` S-20, "sent to the old address before it
is removed"). Both are sent by the account jobs worker, never from a request.

**Nothing here delivers to an inbox yet, and the port is why that is safe to
say.** `for_name()` resolves `settings.EMAIL_ADAPTER`; the only adapter built
is `outbox`, which writes each message to a file. The worker is therefore
complete, testable and honest: `export.emailed` is recorded because a message
really was produced and stored, and swapping in a provider is a new class and
a dict entry rather than a change to the worker.

**Why a file and not a stub that returns success.** A stub would make the
worker's tests pass while proving nothing about the message — and the message
is the part a human has to be able to check before any of this is pointed at a
real address. The file is the artefact: you can open it, read the subject, and
see that the export is attached and that the confirmation went to the address
that was about to be deleted.

`EMAIL_FROM` has no default. A From address is a claim about an identity, and
guessing one for a project with no verified sending domain is how mail gets
classified as spam at the first real send.
"""

from __future__ import annotations

from nidan.infra.email.outbox import OutboxEmail
from nidan.infra.email.port import Email, EmailPort, EmailSendFailed, Sent

__all__ = ["Email", "EmailPort", "EmailSendFailed", "OutboxEmail", "Sent",
           "for_name"]

_ADAPTERS: dict[str, type[EmailPort]] = {
    "outbox": OutboxEmail,
}


def for_name(name: str) -> EmailPort:
    """
    The configured adapter.

    Raises on an unknown name rather than falling back to the outbox. A
    deployment that asked for a real provider and silently got a directory of
    files would believe it had sent mail it had not sent — and the only
    evidence would be the absence of complaints.
    """
    try:
        adapter = _ADAPTERS[name]
    except KeyError:
        raise ValueError(
            f"EMAIL_ADAPTER={name!r} is not built. Available: "
            f"{sorted(_ADAPTERS)}. Adding one means a class implementing "
            f"EmailPort and an entry in nidan/infra/email/__init__.py."
        ) from None
    return adapter()
