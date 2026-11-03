"""
Per-model token prices, for `llm_calls.cost_usd` (BUILD_PLAN T-031).

`llm_calls.cost_usd` is `NOT NULL`, so every recorded call needs a price. There
was nowhere to get one, and `ADR-0011`'s own consequences list "requires
per-purpose cost accounting" as the cost of routing — this is that.

**A dated module rather than configuration, and the date is the point.** Prices
move. A figure in `.env` gets copied between machines and is a year stale with
nothing to say so; a figure here carries the date it was checked, so a reader
can see the staleness instead of trusting it. `cost_usd` is for the T-043
dashboard and for deciding whether the feedback model can be upgraded — both
questions where "this number is from last March" is the useful caveat.

**An unknown model costs 0, and the row is still written.** The alternative is
refusing the call or dropping the row, and both lose more than they protect:
the row's tokens and latency are still true, and a zero cost beside a real
token count is visibly wrong in a way a missing row is not. The warning names
the model so the table can be corrected.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

# USD per 1,000,000 tokens. Checked 2026-11-03 against Groq's published
# pricing. Re-check before quoting any figure derived from these.
PRICES_CHECKED = "2026-11-03"

_PER_MILLION: Final[dict[str, tuple[str, str]]] = {
    #  model                            input      output
    "llama-3.3-70b-versatile":         ("0.59",   "0.79"),
    "llama-3.1-8b-instant":            ("0.05",   "0.08"),
    "llama-3.3-70b-specdec":           ("0.59",   "0.99"),
}

_MILLION = Decimal("1000000")


def cost_usd(model: str, prompt_tokens: int, output_tokens: int) -> Decimal:
    """
    What one call cost, to 6 decimal places — `llm_calls.cost_usd` is
    `NUMERIC(10,6)`.

    `Decimal`, not float. These are summed over thousands of rows for the cost
    dashboard, and float addition drifts; the column is NUMERIC for the same
    reason, so handing it a float would throw away the precision the schema
    asked for.
    """
    prices = _PER_MILLION.get(model)
    if prices is None:
        return Decimal("0")
    price_in, price_out = prices
    total = (Decimal(prompt_tokens) * Decimal(price_in)
             + Decimal(output_tokens) * Decimal(price_out)) / _MILLION
    return total.quantize(Decimal("0.000001"))


def is_priced(model: str) -> bool:
    """Whether a cost for this model is real rather than a zero placeholder."""
    return model in _PER_MILLION
