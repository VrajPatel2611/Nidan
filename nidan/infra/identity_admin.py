"""
Deleting a Supabase credential (BUILD_PLAN T-038 criterion 2).

`ADR-0002` is why this file exists and why it is HTTP rather than SQL: Supabase
owns `auth.users`, we do not. Migration 001 creates a three-column stub of it
so `profiles.id`'s foreign key resolves on a laptop, and `nidan_service` is not
even granted write on that — a probe during T-038 confirmed `permission denied
for table users`. The real deletion is an admin API call.

**This is the one place the `service_role` key is used.** That key bypasses RLS
completely, which makes every guarantee in `ADR-0016` void for anything holding
it, so three things are true by construction here:

* It is read from `settings.SUPABASE_SERVICE_ROLE_KEY` and never passed as an
  argument, so no caller can supply a different one.
* It is **never logged, never returned and never put in an audit row.** The
  `Deletion` result carries an outcome and a status code; `audit_log` rows for
  an erasure survive the erasure, and a key in one would outlive the account
  it was used to delete.
* An empty key **refuses** rather than succeeding vacuously. A worker that
  recorded `erasure.credential_deleted` because there was no key to try would
  make `UX_SPEC` S-20's "removed within 24 h" permanently and silently false.

`urllib.request`, not `httpx` or `requests`: `infra/auth/jwks.py` already talks
to this same Supabase project over the standard library, and a second HTTP
stack for one `DELETE` is a dependency to keep patched for no gain.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from nidan.config import settings

TIMEOUT_SECONDS: Final = 10.0

# Supabase's own admin endpoint. `/auth/v1/admin/users/{id}` with the
# service_role key as both bearer and apikey, which is what GoTrue expects.
_PATH: Final = "/auth/v1/admin/users/{user_id}"


class CredentialDeletionFailed(RuntimeError):
    """
    Retryable: the call did not establish that the credential is gone.

    Separate from `NotConfigured` because the worker's two responses differ.
    A failed call is attempted again; an absent key cannot succeed on a retry
    and should stop being tried after it has said so.
    """


class NotConfigured(RuntimeError):
    """No `SUPABASE_SERVICE_ROLE_KEY`, or no `SUPABASE_URL`."""


@dataclass(frozen=True)
class Deletion:
    """
    What happened, in terms an audit row can keep.

    `already_absent` is a success and is recorded as one. A 404 from this
    endpoint means there is no such user, which is the state the call was
    trying to reach — and treating it as a failure is what would turn a
    timed-out-but-succeeded call into a job that never completes
    (T-038 criterion 4: "an external call that times out is
    indistinguishable from one that failed").
    """

    status: int
    already_absent: bool


def fetch_email(user_id: UUID) -> str:
    """
    The address Supabase holds for this user.

    **Why this is an HTTP call and not a column.** `profiles` has no email; the
    address lives in `auth.users`, which Supabase owns, and a probe during
    T-038 confirmed that `nidan_service` has no SELECT on it — only the table
    owner does, locally, and on Supabase no grant for our roles exists at all.

    The two alternatives were both worse:

    * **Store it when the request is made.** `DELETE /me` would write the
      address into `audit_log.metadata`, and `audit_log` refuses UPDATE and
      survives the erasure — so the erasure would preserve, for ever, the one
      identifier it was asked to remove, in the record of having removed it.
    * **Grant the service role SELECT on `auth.users`.** A migration doing
      that would work locally against migration 001's stub and do nothing on
      Supabase, where the table is theirs. A local-only permission is a path
      that is tested and never run.

    So the worker asks the admin API, uses the address, and never stores it.
    Fetched immediately before the confirmation email, which is also what
    `UX_SPEC` S-20's "sent to the old address before it is removed" requires:
    the ordering is not incidental, it is the only order in which the address
    still exists.
    """
    body = _admin("GET", user_id)
    email = (body or {}).get("email") or ""
    if not email:
        raise CredentialDeletionFailed(
            "Supabase returned no email for this user, so there is no "
            "address to send the confirmation to.")
    return str(email)


def delete_credential(user_id: UUID) -> Deletion:
    """
    Delete one Supabase auth user. Idempotent.

    Raises `NotConfigured` when there is nothing to call with, and
    `CredentialDeletionFailed` when the call was made and did not settle the
    question. Returns only when the credential is gone.
    """
    deletion = _admin("DELETE", user_id, allow_404=True)
    if deletion is _ALREADY_GONE:
        return Deletion(status=404, already_absent=True)
    return Deletion(status=200, already_absent=False)


# A sentinel rather than None: `_admin` returns a parsed body, and a successful
# DELETE has an empty one, so None is already a legitimate answer.
_ALREADY_GONE: Final = object()


def _admin(method: str, user_id: UUID, *, allow_404: bool = False):
    """
    One admin call, one error policy. Returns the parsed body, or
    `_ALREADY_GONE` when a 404 is being treated as success.
    """
    base = settings.SUPABASE_URL.strip().rstrip("/")
    key = settings.SUPABASE_SERVICE_ROLE_KEY.strip()
    if not base:
        raise NotConfigured(
            "SUPABASE_URL is not set, so there is no project to call.")
    if not key:
        # Deliberately generic about the consequence. An earlier version
        # described the erasure's half-done state here, and because both
        # callers share this helper it then told someone whose *export* had
        # not been emailed that their credential was still live — a true
        # sentence about the wrong thing, in the error they would act on.
        # What is specific to each caller belongs to each caller.
        raise NotConfigured(
            "SUPABASE_SERVICE_ROLE_KEY is not set, so the Supabase admin API "
            "cannot be called — which is where both a user's email address "
            "and their credential live (ADR-0002: we do not own auth.users). "
            "Set it in the JOBS WORKER's environment only: it bypasses RLS "
            "entirely, so never in web/, never NEXT_PUBLIC_*, never in "
            "HANDOFF.md.")

    request = urllib.request.Request(
        url=base + _PATH.format(user_id=user_id),
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "apikey": key,
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        if e.code == 404 and allow_404:
            # Already gone. The goal state, reached by someone else or by a
            # previous run whose completion row did not commit.
            return _ALREADY_GONE
        if e.code in (401, 403):
            # Worth distinguishing, because retrying will not fix it and the
            # fix is a different key. The key itself is not in the message —
            # that is what this module is for.
            raise CredentialDeletionFailed(
                f"Supabase refused the admin call with {e.code}. The "
                f"service_role key is wrong, revoked, or belongs to another "
                f"project. Retrying will not help.") from None
        raise CredentialDeletionFailed(
            f"Supabase answered {e.code} to the admin {method}.") from None
    except urllib.error.URLError as e:
        # Network, DNS, TLS, a paused project. `e.reason` can carry the URL but
        # never the headers, so the key cannot leak through it.
        raise CredentialDeletionFailed(
            f"could not reach the Supabase admin API: {e.reason}") from None
    except TimeoutError:
        raise CredentialDeletionFailed(
            f"the Supabase admin {method} timed out after "
            f"{TIMEOUT_SECONDS:g}s. It may have succeeded; the next run will "
            f"find out, because a 404 counts as done.") from None
    except json.JSONDecodeError as e:
        raise CredentialDeletionFailed(
            f"the Supabase admin API answered with something that is not "
            f"JSON: {e}") from None
