"""
The monthly model budget (T-043 criterion 3, `TECH_SPEC` §5.1 and §10.1).

Alert at 80 %, degrade to the cheapest priced model at 100 %. The gateway
does the degrading but cannot read the database, so `create_app` hands it
`exhausted` from here (`gateway.set_budget_guard`).

## Process state, like the circuit breaker, and for the same reason

The month's spend is cached for `CACHE_SECONDS` per process. Without that,
every patient turn would run an aggregate over `llm_calls` before calling the
model. This holds no learner and no session, only a number about the
platform, so it does not touch `ADR-0003`'s rule that session state is never
held in the process. The cost of the cache is that a worker may make up to a
minute of calls on the full model after the budget is crossed. That is a few
cents, against a query on every request.

## Which actor reads it

`llm_calls` has no RLS and every application role holds SELECT on it, so no
scope sees more of it than another. The check needs one anyway, and it runs
from both the signed-in path and the anonymous trial, where there is no user
to open one as. A `ServiceActor` with its reason stated, as
`api/v1/catalog.py` does for the universal menus: the bypass is real but
reaches nothing here that the other roles could not already read.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from nidan.config import settings
from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories import repo_scope

ALERT_AT: Final = 80        # percent; TECH_SPEC §5.1
DEGRADE_AT: Final = 100
CACHE_SECONDS: Final = 60.0

_ACTOR = ServiceActor(
    reason="the budget check sums this month's llm_calls, a table with no RLS, "
           "from routes that may have no signed-in user")

_lock = threading.Lock()
_cached: tuple[float, Decimal] | None = None     # (monotonic expiry, spend)


@dataclass(frozen=True)
class BudgetState:
    budget: Decimal | None
    spent: Decimal

    @property
    def pct(self) -> float | None:
        if not self.budget:
            return None
        return float(self.spent / self.budget * 100)

    @property
    def alert(self) -> bool:
        return self.pct is not None and self.pct >= ALERT_AT

    @property
    def exhausted(self) -> bool:
        return self.pct is not None and self.pct >= DEGRADE_AT


def _budget() -> Decimal | None:
    value = settings.LLM_MONTHLY_BUDGET_USD
    return Decimal(str(value)) if value else None


def month_spend(*, fresh: bool = False) -> Decimal:
    """This UTC calendar month's spend, cached unless `fresh`."""
    global _cached
    now = time.monotonic()
    with _lock:
        if not fresh and _cached is not None and _cached[0] > now:
            return _cached[1]
    with repo_scope(_ACTOR) as db:
        spent = db.llm_calls.month_spend()
    with _lock:
        _cached = (now + CACHE_SECONDS, spent)
    return spent


def current(*, fresh: bool = False) -> BudgetState:
    """The state the AI Ops page shows. `fresh` because an admin looking at
    the page should see the real figure, not one a minute old."""
    return BudgetState(budget=_budget(), spent=month_spend(fresh=fresh))


def exhausted() -> bool:
    """
    The gateway's question. With no budget configured it answers without
    touching the database, so an unconfigured deployment pays nothing for
    the feature.
    """
    if _budget() is None:
        return False
    return current().exhausted


def reset_cache() -> None:
    """For tests."""
    global _cached
    with _lock:
        _cached = None
