"""
`llm_calls` — what every model call cost (`DATA_MODEL` §7.1, T-031).

The row the gateway cannot write itself. `pyproject.toml`'s import-linter
contract forbids `nidan.infra.llm` from reaching `nidan.infra.db.engine`, and
it counts indirect imports, so the gateway returns an `LLMCall` and whoever
holds a transaction writes it here.

**Written on a best-effort basis by design.** A consultation must not fail
because cost accounting did, so `record()` is called inside a scope the caller
already opened for work that matters more. If the row is lost the dashboard is
short one call; if the exception propagated, a learner loses a reply they
already received.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository

# Migration 015's CHECK, mirrored. Not every purpose the gateway can be given
# is billable: Playtest passes `purpose="playtest"`, which is correct for the
# log line and refused by that CHECK, so it is absent here and `record()` says
# so in Python rather than letting a CheckViolation abort a transaction opened
# for work that mattered more.
PURPOSES: Final[frozenset[str]] = frozenset({
    "patient", "feedback", "extraction", "judge", "grounding",
})


class UnaccountablePurpose(ValueError):
    """A purpose migration 015 does not allow in `llm_calls.purpose`."""


class LlmCallRepository(Repository):
    """Append-only in practice: nothing updates a call that already happened."""

    def record(self, *, purpose: str, provider: str, model: str,
               prompt_tokens: int, output_tokens: int, cost_usd: Decimal,
               latency_ms: int, status: str, attempt: int = 1,
               session_id: UUID | None = None) -> None:
        """
        One call, as it happened.

        `session_id` is nullable (`DATA_MODEL` §7.1) and that is deliberate:
        feedback generation belongs to a session, but a Playtest turn belongs
        to a reviewer poking at a draft and an extraction run to no session at
        all. A NOT NULL here would have forced a fake session for the Case
        Factory.

        Takes the gateway's `LLMCall` fields rather than the object, so this
        module does not import `infra.llm` — the dependency runs one way and
        the accounting side stays the one that knows about SQL.
        """
        if purpose not in PURPOSES:
            raise UnaccountablePurpose(
                f"{purpose!r} is not one of {sorted(PURPOSES)}; migration 015's "
                "CHECK would refuse the row")
        self._conn.execute(sa.text("""
            INSERT INTO llm_calls (session_id, purpose, provider, model,
                                   prompt_tokens, output_tokens, cost_usd,
                                   latency_ms, status, attempt)
            VALUES (:sid, :purpose, :provider, :model, :prompt_tokens,
                    :output_tokens, :cost, :latency, :status, :attempt)
        """), {"sid": session_id, "purpose": purpose, "provider": provider,
               "model": model, "prompt_tokens": prompt_tokens,
               "output_tokens": output_tokens, "cost": cost_usd,
               "latency": latency_ms, "status": status, "attempt": attempt})

    def record_call(self, call, *, session_id: UUID | None = None) -> None:
        """
        Convenience for a gateway `LLMCall`, read field by field.

        Duck-typed on purpose. Importing `infra.llm.gateway` here to annotate
        the parameter would make `infra.db` depend on `infra.llm`, which is
        the wrong direction and would put a provider SDK behind every
        repository import.
        """
        self.record(
            purpose=call.purpose, provider=call.provider, model=call.model,
            prompt_tokens=call.prompt_tokens, output_tokens=call.output_tokens,
            cost_usd=call.cost_usd, latency_ms=call.latency_ms,
            status=call.status, attempt=call.attempt, session_id=session_id,
        )
