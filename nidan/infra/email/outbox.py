"""
The local outbox: an adapter that writes each message to a file.

**This is the whole email implementation for now, and it is a deliberate
choice rather than a placeholder.** T-038's two messages are both
worker-driven, so the part that needed building was the worker; a real
provider needs an account, a verified sending domain and a key, none of which
exist and none of which the worker's correctness depends on. Writing the
message to disk makes every step of the job real and inspectable, and leaves
`for_name()` as the one place a provider gets added.

What it is NOT: a test double. It runs in production configuration if nobody
changes `EMAIL_ADAPTER`, which is why `jobs/runner.py` reports the adapter in
every completion row and `COMMANDS.md` says in so many words that nothing is
delivered until a provider is configured. An adapter that quietly did nothing
and returned success would be the worst of the options available here — the
24-hour SLA in `PRD` FR-11.3 would be recorded as met, for ever, by a system
that had never sent anything.
"""

from __future__ import annotations

import json
import pathlib
import re
import uuid

from nidan.config import settings
from nidan.infra.clock import utc_now
from nidan.infra.email.port import Email, EmailSendFailed, Sent

# Anything that is not plainly safe in a filename. The address never reaches
# the name — see `_stem` — but the subject does, and a subject is author-
# controlled text that will one day contain a slash.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class OutboxEmail:
    """Writes `<EMAIL_OUTBOX_DIR>/<timestamp>-<subject>-<id>/` per message."""

    name = "outbox"

    def send(self, message: Email) -> Sent:
        root = pathlib.Path(settings.EMAIL_OUTBOX_DIR)
        folder = root / self._stem(message)
        try:
            folder.mkdir(parents=True, exist_ok=False)
            # The envelope as JSON, so a test or a human can assert on fields
            # rather than parse prose. `from` is recorded because a message
            # with no From is the single most common reason real mail is
            # rejected, and the outbox should fail the same way.
            (folder / "message.json").write_text(json.dumps({
                "from": settings.EMAIL_FROM,
                "to": message.to,
                "subject": message.subject,
                "attachments": sorted(message.attachments),
                "written_at": utc_now().isoformat(),
            }, indent=2) + "\n", encoding="utf-8")
            (folder / "body.txt").write_text(message.body, encoding="utf-8")
            for filename, blob in message.attachments.items():
                safe = _UNSAFE.sub("_", filename) or "attachment"
                (folder / safe).write_bytes(blob)
        except OSError as e:
            # `EmailSendFailed`, not the OSError: a full disk and a provider
            # outage are the same thing to the worker — a step to retry — and
            # the runner's retry logic should not have to know which adapter
            # it is talking to to decide that.
            raise EmailSendFailed(f"could not write to the outbox: {e}") from e

        # The folder, not the address. This string goes into an `audit_log`
        # row that survives an erasure, and the address is the thing the
        # erasure removes.
        return Sent(adapter=self.name, reference=str(folder))

    @staticmethod
    def _stem(message: Email) -> str:
        when = utc_now().strftime("%Y%m%dT%H%M%SZ")
        subject = _UNSAFE.sub("-", message.subject.strip())[:48].strip("-")
        # A uuid4 suffix rather than a counter: two messages in the same second
        # with the same subject are exactly what a worker run produces, and
        # `exist_ok=False` above turns a collision into a failed send.
        return f"{when}-{subject or 'message'}-{uuid.uuid4().hex[:8]}"
