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

from datetime import datetime
from decimal import Decimal
from typing import Any, Final
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

    def spend(self) -> dict[str, object]:
        """
        What the models have cost — today and in total.

        `llm_calls` carries no RLS policy and `nidan_admin` holds SELECT, so
        unlike `sessions` this really is readable from an admin scope. That
        asymmetry is deliberate and is why the dashboard can show a true cost
        and cannot show a true session count: a cost is an aggregate over
        something the platform spent, and a session belongs to a learner.

        `status` is counted separately because a `failed` or `fallback` call
        still cost tokens on some providers but tells a different story from
        an `ok` one, and a single "LLM cost" figure that hid a run of
        failures would be the kind of number that looks healthy while
        something is wrong.
        """
        row = self._conn.execute(sa.text("""
            SELECT count(*)                                   AS calls,
                   COALESCE(sum(cost_usd), 0)                 AS cost,
                   count(*) FILTER (
                     WHERE created_at >= date_trunc('day', now()))
                                                              AS calls_today,
                   COALESCE(sum(cost_usd) FILTER (
                     WHERE created_at >= date_trunc('day', now())), 0)
                                                              AS cost_today,
                   count(*) FILTER (WHERE status <> 'ok')     AS not_ok
            FROM llm_calls
        """)).mappings().one()
        return {
            "calls": row["calls"],
            "cost": Decimal(row["cost"]),
            "calls_today": row["calls_today"],
            "cost_today": Decimal(row["cost_today"]),
            "not_ok": row["not_ok"],
        }

    # ── the AI Ops page (T-043, `UX_SPEC` A-08) ─────────────────────────
    #
    # Everything below reads `llm_calls` and nothing else, which is what lets
    # it run under `current_admin()` with no new policy: the table has no RLS.
    # `sessions` does, and an admin scope sees almost none of it, so "cost
    # per completed session" is computed from the feedback rows rather than
    # from `sessions.status`. Every completed `/v1` session writes exactly one
    # feedback row (`ok`, `retried` or, since T-043, `fallback`).

    # A latency is only a latency of an answer. `failed` rows carry the time
    # spent failing, and `fallback` rows built without a call carry 0. Either
    # would drag a percentile towards a number no learner waited for.
    _ANSWERED = "status IN ('ok', 'retried')"

    def month_spend(self) -> Decimal:
        """This UTC calendar month's spend: the budget's numerator."""
        return Decimal(self._conn.execute(sa.text("""
            SELECT COALESCE(sum(cost_usd), 0) FROM llm_calls
             WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'UTC')
                                 AT TIME ZONE 'UTC'
        """)).scalar_one())

    def usage(self, since: datetime) -> list[dict[str, Any]]:
        """One row per purpose and model since `since`, most expensive first."""
        rows = self._conn.execute(sa.text(f"""
            SELECT purpose, model,
                   count(*)                                    AS calls,
                   COALESCE(sum(prompt_tokens), 0)             AS prompt_tokens,
                   COALESCE(sum(output_tokens), 0)             AS output_tokens,
                   COALESCE(sum(cost_usd), 0)                  AS cost,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)
                     FILTER (WHERE {self._ANSWERED})           AS p50_ms,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
                     FILTER (WHERE {self._ANSWERED})           AS p95_ms,
                   count(*) FILTER (WHERE status = 'retried')  AS retried,
                   count(*) FILTER (WHERE status = 'failed')   AS failed,
                   count(*) FILTER (WHERE status = 'fallback') AS fallback
              FROM llm_calls
             WHERE created_at >= :since
          GROUP BY purpose, model
          ORDER BY cost DESC, calls DESC
        """), {"since": since}).mappings().all()
        return [{**r, "cost": Decimal(r["cost"])} for r in rows]

    def overview(self, since: datetime) -> dict[str, Any]:
        """
        The four headline figures since `since` (`UX_SPEC` A-08).

        `cost_per_completed` sums **every** call of each session whose
        feedback row falls in the window, patient turns included, because
        the unit economic is what a whole consultation cost. A session whose
        patient turns started before the window still counts in full. It is
        None when nothing completed, rather than $0, which would read as free.
        """
        row = self._conn.execute(sa.text(f"""
            WITH w AS (SELECT * FROM llm_calls WHERE created_at >= :since),
                 done AS (SELECT DISTINCT session_id FROM w
                           WHERE purpose = 'feedback' AND session_id IS NOT NULL)
            SELECT
              (SELECT COALESCE(sum(cost_usd), 0) FROM w)                 AS cost,
              (SELECT count(*) FROM w)                                   AS calls,
              (SELECT count(*) FROM w WHERE status = 'failed')           AS failed,
              (SELECT count(*) FROM w WHERE purpose = 'feedback')        AS feedback,
              (SELECT count(*) FROM w WHERE purpose = 'feedback'
                                        AND status = 'fallback')         AS fallback,
              (SELECT count(*) FROM w WHERE purpose = 'patient'
                                        AND {self._ANSWERED})            AS replies,
              (SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
                 FROM w WHERE purpose = 'patient' AND {self._ANSWERED})  AS patient_p95_ms,
              (SELECT count(*) FROM done)                                AS completed,
              (SELECT COALESCE(sum(c.cost_usd), 0) FROM llm_calls c
                 JOIN done d ON d.session_id = c.session_id)             AS completed_cost
        """), {"since": since}).mappings().one()
        completed = row["completed"]
        return {
            "cost": Decimal(row["cost"]),
            "calls": row["calls"],
            "failed": row["failed"],
            "feedback": row["feedback"],
            "fallback": row["fallback"],
            "replies": row["replies"],
            "patient_p95_ms": row["patient_p95_ms"],
            "completed": completed,
            "cost_per_completed": (Decimal(row["completed_cost"]) / completed
                                   if completed else None),
        }

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
