"""
Cancelling a subscription at the payment provider (T-038 criterion 2).

**There is no payment provider.** Stripe is `T-041`, Phase 4 — `grep -rln
stripe nidan/` finds `api/v1/contract.py`'s 501 list and a key name in
`telemetry/redaction.py`, and nothing else. T-038's acceptance criterion was
written assuming a provider that arrives one phase later, which only became
visible when the task was picked up.

So this is a seam with one honest implementation. `NoProvider.cancel()`
reports `no_provider_configured`, the worker records **that**, and the step is
marked done — because it is done: there is nothing outside our database
holding a subscription for this user, and `DATA_MODEL` §10.2's transaction has
already set `subscriptions.status = 'cancelled'` in the one place a
subscription exists.

**The alternative was to record `erasure.billing_cancelled` with no detail**,
and it is worth being explicit about why that is wrong rather than merely
imprecise. `audit_log` refuses UPDATE and survives an erasure, so it is the
only lasting record that the deletion happened and what it covered. A row
saying a payment provider was cancelled, written by a system with no payment
provider, is a false statement in the one place that must not contain one — and
it would read as true for ever, including to whoever eventually asks whether
an erased user was still being billed.

When T-041 lands, it adds a `StripeBilling` class and an entry in
`_PROVIDERS`. The worker does not change: it already records whichever
provider answered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from nidan.config import settings


class CancellationFailed(RuntimeError):
    """Retryable. The provider was reachable-ish and did not confirm."""


@dataclass(frozen=True)
class Cancellation:
    """
    What the provider did, for the audit row.

    `outcome` is one of:

    * `cancelled` — the provider cancelled an active subscription
    * `nothing_to_cancel` — the provider had no active subscription for them
    * `no_provider_configured` — there is no provider; see the module docstring
    """

    provider: str
    outcome: str
    reference: str | None = None


class BillingPort(Protocol):
    name: str

    def cancel(self, user_id: UUID) -> Cancellation:
        ...


class NoProvider:
    """
    The only implementation, until T-041.

    Takes the `user_id` it will not use, because the signature is the contract
    and a narrower one here would have to widen when Stripe arrives.
    """

    name = "none"

    def cancel(self, user_id: UUID) -> Cancellation:  # noqa: ARG002
        return Cancellation(provider=self.name,
                            outcome="no_provider_configured")


_PROVIDERS: dict[str, type[BillingPort]] = {
    "none": NoProvider,
}


def for_name(name: str) -> BillingPort:
    """The configured provider. Raises on an unknown name — see email's."""
    try:
        provider = _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"BILLING_PROVIDER={name!r} is not built. Available: "
            f"{sorted(_PROVIDERS)}. Stripe is T-041."
        ) from None
    return provider()


def configured() -> BillingPort:
    return for_name(settings.BILLING_PROVIDER)
