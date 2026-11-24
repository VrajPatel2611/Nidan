"""
The account jobs worker (BUILD_PLAN T-038).

Both 202s in `/v1` are honest about the database and silent about everything
outside it. This is the outside part: `POST /me/export` builds nothing and
mails nothing, and `DELETE /me` leaves the Supabase credential alive, the
payment provider uncontacted and S-20's confirmation email unsent.

## One worker, not two

`ADR-0018` and API-10 left the same shape twice — a 202 with outbound calls
behind it — so the retry logic lives once. Two workers would be two places
for it to be subtly different, and the difference would show up as one of
them losing a request.

## The queue is a difference between two sets

`audit_log` refuses UPDATE, including to the table owner, and `ADR-0018` kept
it that way deliberately: the record of an erasure must not be editable by the
thing performing one. So **a job cannot be marked done.** It is done when a
second row says so, and `AuditRepository.pending()` is the difference. Three
properties follow, and they are what criteria 3 and 4 ask for:

* **A crash loses nothing.** The request row is already committed; re-running
  re-derives the same work from the same rows.
* **Each step is separately skippable.** A step whose completion row exists is
  not attempted again, so a run that sent the email and then died does not
  send it twice.
* **A timeout is survivable.** `delete_credential` treats Supabase's 404 as
  success, so a call that timed out after succeeding completes on the next run
  rather than failing for ever.

## Order is not incidental

`UX_SPEC` S-20 requires the confirmation to go "to the old address before it
is removed", and the address lives in `auth.users` — so the email must be sent
before the credential is deleted, because afterwards there is no address to
fetch. The step list in `repositories/audit.py` is in that order and this
module walks it in order, stopping at the first failure so a later step cannot
run on the assumption that an earlier one worked.

## It runs as a ServiceActor, and says why

RLS is off for `nidan_service`. It has to be: the worker acts for a user who
may already be soft-deleted, reads across `sessions` for the export, and
writes `audit_log` rows with no actor. Every query it issues is scoped by an
explicit `user_id` instead — `ExportRepository.gather` asserts the actor type
for that reason.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from nidan.config import settings
from nidan.infra import billing, identity_admin
from nidan.infra.clock import utc_now
from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.audit import MAX_ATTEMPTS, STEPS
from nidan.infra.email import for_name as email_for_name
from nidan.infra.email.port import EmailSendFailed
from nidan.jobs import messages

log = logging.getLogger("nidan.jobs")

ACTOR = ServiceActor(
    reason="the account jobs worker acts for users who may already be "
           "soft-deleted, and writes audit rows with no human actor")


class StepFailed(RuntimeError):
    """Retryable. Recorded, and the job is left pending."""


class StepImpossible(RuntimeError):
    """
    Not retryable: nothing about a later run would change the outcome.

    Separated from `StepFailed` because retrying an impossible step five times
    and then giving up looks identical in the log to a flaky network, and the
    two need different responses from whoever reads it. A missing
    `SUPABASE_SERVICE_ROLE_KEY` is impossible; a timeout is not.
    """


@dataclass
class Report:
    """What one run did, for the exit summary and the tests."""

    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed

    def summary(self) -> str:
        return (f"{len(self.completed)} step(s) completed, "
                f"{len(self.failed)} failed, {len(self.skipped)} skipped")


def run(limit: int = 100) -> Report:
    """
    Process every pending step once, and report.

    Opens a **scope per step**, not one per run. A single transaction would
    mean a failure on user B rolling back the completion row for user A's
    already-sent email — and then sending it again on the next run. The unit of
    work is the step, because the step is what has an irreversible effect
    outside the database.
    """
    report = Report()
    with repo_scope(ACTOR) as db:
        jobs = db.audit.pending(limit=limit)

    for job in jobs:
        action = job["action"]
        user_id = job["entity_id"]
        done = set(job["steps_done"])
        attempts = dict(job["attempts"] or {})

        for step in STEPS[action]:
            label = f"{step} for {user_id}"
            if step in done:
                continue
            if attempts.get(step, 0) >= MAX_ATTEMPTS:
                report.skipped.append(label)
                log.warning("giving up on %s after %d attempts — an admin "
                            "needs to look at this (T-038 criterion 5)",
                            label, attempts[step])
                continue
            try:
                detail = _perform(step, user_id)
            except StepImpossible as e:
                _record_failure(step, user_id, e, retryable=False)
                report.failed.append(label)
                log.error("%s cannot succeed as configured: %s", label, e)
                break
            except (StepFailed, EmailSendFailed,
                    identity_admin.CredentialDeletionFailed,
                    billing.CancellationFailed) as e:
                _record_failure(step, user_id, e, retryable=True)
                report.failed.append(label)
                log.warning("%s failed, will retry: %s", label, e)
                # Stop this job here. A later step must not run on the
                # assumption that an earlier one worked — deleting the
                # credential after a failed confirmation email would leave the
                # user with no account and no notice.
                break
            else:
                with repo_scope(ACTOR) as db:
                    db.audit.record_system_step(
                        step, entity_id=user_id,
                        reason=f"account jobs worker ({step})",
                        metadata=detail)
                report.completed.append(label)
                log.info("%s done", label)

    return report


# ── the steps ───────────────────────────────────────────────────────────

def _perform(step: str, user_id: UUID) -> dict:
    if step == "export.built":
        return _build_export(user_id)
    if step == "export.emailed":
        return _email_export(user_id)
    if step == "erasure.email_sent":
        return _email_erasure(user_id)
    if step == "erasure.billing_cancelled":
        return _cancel_billing(user_id)
    if step == "erasure.credential_deleted":
        return _delete_credential(user_id)
    raise StepImpossible(f"no implementation for step {step!r}")


def _build_export(user_id: UUID) -> dict:
    """
    Assemble the payload and record its size.

    Built and emailed are separate steps even though nothing is stored between
    them, because they fail for different reasons and the split is what makes
    the retry proportionate: a provider outage should not rebuild the export,
    and a malformed row should not be diagnosed as a mail problem. The rebuild
    on the emailing step is cheap — four indexed queries.
    """
    with repo_scope(ACTOR) as db:
        try:
            payload = db.export.gather(user_id)
        except LookupError as e:
            raise StepImpossible(str(e)) from None
    return {"sessions": len(payload["sessions"]),
            "export_version": payload["export_version"]}


def _email_export(user_id: UUID) -> dict:
    with repo_scope(ACTOR) as db:
        payload = db.export.gather(user_id)
    message = messages.export_email(_address(user_id), payload)
    return _send(message)


def _email_erasure(user_id: UUID) -> dict:
    """
    The confirmation, with the counts from the erasure's own audit row.

    Read back rather than recomputed: the row is what the transaction actually
    did, and recomputing would give zero — the redaction has already happened,
    so there is nothing left to count.
    """
    with repo_scope(ACTOR) as db:
        rows = db.audit.for_entity("profile", user_id, limit=50)
    erased = next((r for r in rows if r["action"] == "profile.erased"), None)
    if erased is None:                           # pragma: no cover
        raise StepImpossible(
            "no profile.erased row, so there is nothing to confirm")
    meta = erased["metadata"] or {}
    message = messages.erasure_email(
        _address(user_id),
        events_redacted=meta.get("events_redacted", 0),
        feedback_redacted=meta.get("feedback_redacted", 0))
    return _send(message)


def _cancel_billing(user_id: UUID) -> dict:
    result = billing.configured().cancel(user_id)
    # Recorded verbatim, including `no_provider_configured`. See
    # `infra/billing.py`: a row claiming a payment provider was cancelled, in
    # a system with no payment provider, is a false statement in the one place
    # that must not contain one.
    return {"provider": result.provider, "outcome": result.outcome,
            "reference": result.reference}


def _delete_credential(user_id: UUID) -> dict:
    try:
        result = identity_admin.delete_credential(user_id)
    except identity_admin.NotConfigured as e:
        # The consequence stated where it is true. `DATA_MODEL` §10.2's
        # transaction has already committed, so the data is erased and only
        # the credential survives — which `ProfileRepository.get()`'s
        # `deleted_at IS NULL` filter makes harmless for our own routes, but
        # leaves S-20's "within 24 h" unmet for the credential itself.
        raise StepImpossible(
            f"{e} Until it is set, the account's data is erased but its "
            f"sign-in credential is not, so UX_SPEC S-20's 24 hours is not "
            f"met for the credential.") from None
    return {"status": result.status, "already_absent": result.already_absent}


# ── shared ──────────────────────────────────────────────────────────────

def _address(user_id: UUID) -> str:
    """
    The user's email, from Supabase, never stored.

    `fetch_email` explains why it is an HTTP call: `profiles` has no email and
    `nidan_service` has no SELECT on `auth.users`.
    """
    try:
        return identity_admin.fetch_email(user_id)
    except identity_admin.NotConfigured as e:
        raise StepImpossible(str(e)) from None


def _send(message) -> dict:
    adapter = email_for_name(settings.EMAIL_ADAPTER)
    sent = adapter.send(message)
    log.info("sent %s via %s", message.redacted(), sent.adapter)
    # The adapter and its reference; never the address. This goes into an
    # `audit_log` row that outlives the account.
    return {"adapter": sent.adapter, "reference": sent.reference,
            "subject": message.subject}


def _record_failure(step: str, user_id: UUID, error: Exception, *,
                    retryable: bool) -> None:
    """
    One `job.step_failed` row. `pending()` counts them as `attempts`.

    A row rather than a counter column, because there is no column to
    increment — and the rows are better: each failure keeps its own reason and
    its own timestamp, so "it has been failing the same way since Tuesday" is
    answerable.
    """
    with repo_scope(ACTOR) as db:
        db.audit.record_system_step(
            "job.step_failed", entity_id=user_id,
            reason=f"{type(error).__name__}: {error}"[:500],
            metadata={"step": step, "retryable": retryable,
                      "at": utc_now().isoformat()})
