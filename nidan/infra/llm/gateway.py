"""
LLM gateway.

The single place the application talks to a language model. Every call goes
through here so that retry, provider selection and cost accounting have one
home.

Design rule (PR-1, `ADR-0005`): the model generates text only. It never
produces a flag, a score or a verdict. Those are computed by
`nidan.domain.assessment` from the learner's own actions, which is what makes
results reproducible.

**The gateway cannot write its own `llm_calls` row, and that is enforced.**
T-031 criterion 3 wants every call recorded with tokens, cost and latency —
but the import-linter contract in `pyproject.toml` forbids `nidan.infra.llm`
from importing `nidan.infra.db.engine`, and it counts indirect imports, so a
repository is out of reach too (every repository reaches `base`, which reaches
`engine`). `lint-imports` fails the build on it.

So `call_llm` returns the metrics and the **caller** writes the row, inside a
scope it already has. `infra/feedback.py` is under the same restriction and
passes them further up through `FeedbackResult`. The places that actually
record are `api/v1/consultation.py`, `api/v1/conclusion.py` and
`api/routes.py` — each already holding a transaction. The admin Playtest
route deliberately does not; its own comment says why.
"""

from __future__ import annotations

import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Final

from nidan.infra.llm import pricing, provider
from nidan.infra.llm.breaker import CircuitOpen, breaker
from nidan.infra.telemetry.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class LLMCall:
    """
    What one completed call cost, for a `llm_calls` row (`DATA_MODEL` §7.1).

    Returned rather than written here because this module may not reach the
    database — see the module docstring. Frozen because it describes something
    that has already happened.
    """

    purpose: str
    provider: str
    model: str
    prompt_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_ms: int
    status: str
    attempt: int


@dataclass(frozen=True)
class LLMResult:
    """The model's text, and what the call cost."""

    text: str
    call: LLMCall


def _model_for(purpose: str) -> str:
    """
    Per-purpose model selection (`ADR-0011`).

    `TECH_SPEC` §5.2 routes the high-volume patient turn to something cheap
    and fast and wants feedback on a stronger model before launch; today both
    resolve to the default, and the override is how that changes without a
    deploy.

    The override stays an `os.getenv`: the variable name is built from
    `purpose` at call time, so it cannot be a declared Settings field.
    """
    from nidan.config import settings
    return os.getenv(f"GROQ_MODEL_{purpose.upper()}", settings.GROQ_MODEL)


# Substrings that mean "try again", as the providers phrase them. Matched
# against the exception text because the SDKs raise their own classes and
# catching them by type would couple this module to one provider — which is
# what the provider seam exists to avoid.
_TRANSIENT: Final = ("429", "500", "502", "503", "over capacity",
                     "rate limit", "Empty response", "timeout", "timed out")

# T-031 criterion 2. Base delay doubles per attempt and carries jitter.
_BACKOFF_BASE_SECONDS: Final = 2.0
_JITTER_FRACTION: Final = 0.25


def _backoff_seconds(attempt: int) -> float:
    """
    Exponential, with jitter (T-031 criterion 2).

    **The jitter is the point, not a flourish.** Without it, every request
    that failed in the same second retries in the same second — the
    thundering herd that turns one provider blip into a self-inflicted second
    one. ±25% spreads them.

    `attempt` is 0-based: 2 s, 4 s, 8 s.
    """
    base = _BACKOFF_BASE_SECONDS * (2 ** attempt)
    return base * (1 + random.uniform(-_JITTER_FRACTION, _JITTER_FRACTION))


# ── the monthly budget (T-043, `TECH_SPEC` §5.1) ────────────────────────
#
# The gateway cannot read `llm_calls` to know what the month has cost: the
# import-linter contract keeps `nidan.infra.llm` away from the database. So
# the knowledge is injected. `create_app` registers `infra/budget.py`'s
# check here, and the gateway only asks a yes/no question of it. Unset (unit
# tests, scripts, `test_api.py`), nothing ever degrades.
_budget_exhausted: Callable[[], bool] | None = None


def set_budget_guard(check: Callable[[], bool] | None) -> None:
    """Register the "is this month's budget spent?" check, or clear it."""
    global _budget_exhausted
    _budget_exhausted = check


def _over_budget() -> bool:
    """
    Whether to degrade. **Fails open**: if the check itself raises (the
    database is down, say) the call goes ahead on the configured model.
    Refusing to answer a learner because cost accounting is unavailable
    would turn a reporting outage into a teaching outage.
    """
    if _budget_exhausted is None:
        return False
    try:
        return bool(_budget_exhausted())
    except Exception as e:                       # pragma: no cover — logged
        logger.warning("llm.budget_check_failed", extra={"error": str(e)[:120]})
        return False


def failed_call(exc: BaseException) -> LLMCall | None:
    """
    The `LLMCall` describing a call that failed, if the gateway made one.

    Attached to the raised exception by `call_llm` after its retries are
    exhausted, so a caller that already catches `Exception` to degrade can
    still record the failure (T-043 criterion 2's error rate). None for
    `CircuitOpen`, because no call was made and there is nothing to count.
    """
    return getattr(exc, "llm_call", None)


def fallback_call(purpose: str, failed: LLMCall | None = None) -> LLMCall:
    """
    The row for "the model gave nothing usable, so a rule-based fallback
    answered" (`status='fallback'`, which migration 015 always allowed and
    nothing wrote until T-043).

    Built from the failed call when there was one, so its model, latency and
    any tokens it was billed for are kept. Built from configuration when the
    breaker refused before calling: then no tokens were spent, but a fallback
    was still served, and leaving it out would understate the fallback rate
    on exactly the days the provider was down.
    """
    if failed is not None:
        return replace(failed, status="fallback")
    from nidan.config import settings
    return LLMCall(purpose=purpose, provider=settings.LLM_PROVIDER,
                   model=_model_for(purpose), prompt_tokens=0, output_tokens=0,
                   cost_usd=Decimal("0"), latency_ms=0, status="fallback",
                   attempt=0)


def call_llm(messages, system_instruction, *, purpose="patient",
             max_tokens=200, temperature=0.7, max_retries=3) -> LLMResult:
    """
    Call the model, retrying transient failures.

    Args:
        messages: `[{"role": "user"|"assistant", "content": str}, ...]`,
                  oldest first.
        system_instruction: the patient persona, or the tutor instruction.
        purpose: 'patient' | 'feedback' | 'extraction' | 'judge'. Selects the
                  model and the cost bucket.

    Returns:
        LLMResult: the text, and an `LLMCall` for the caller to record.

    Raises:
        The last exception if every attempt fails, or `CircuitOpen` without
        calling at all while the breaker is open. Callers degrade rather than
        propagate — `POST /questions` answers 503 `patient_unavailable`
        without consuming the question, and `infra/feedback.py` falls back to
        rule-based prose. Both already catch `Exception`, which is why the
        breaker needed no change to either.
    """
    payload = [{"role": "system", "content": system_instruction}] + list(messages)
    model = _model_for(purpose)
    if _over_budget():
        cheapest = pricing.cheapest_model()
        if cheapest != model:
            # Logged on every call, not once: a degraded month should be loud
            # in the logs as well as on the AI Ops page (`UX_SPEC` A-08).
            logger.warning("llm.budget_degraded", extra={
                "purpose": purpose, "configured": model, "using": cheapest})
            model = cheapest
    client = provider.for_name()

    # Before the loop, deliberately. Raised inside it, `CircuitOpen` would be
    # measured against `_TRANSIENT` and its message retried — and a breaker
    # whose refusal is retried is a breaker that sleeps for six seconds to
    # refuse three times.
    key = f"{client.name}:{model}"
    try:
        breaker.before_call(key)
    except CircuitOpen as e:
        logger.warning("llm.circuit_rejected", extra={
            "purpose": purpose, "model": model, "reason": str(e)})
        raise

    last_err: Exception | None = None
    for attempt in range(max_retries):
        started = time.monotonic()
        try:
            completion = client.complete(
                model=model, messages=payload,
                max_tokens=max_tokens, temperature=temperature,
            )
            if not completion.text:
                raise ValueError("Empty response from model")

            latency_ms = int((time.monotonic() - started) * 1000)
            cost = pricing.cost_usd(model, completion.prompt_tokens,
                                    completion.output_tokens)
            if not pricing.is_priced(model):
                # Named, so the price table can be corrected. The row is still
                # written: its tokens and latency are true, and a zero cost
                # beside a real token count is visibly wrong in a way a
                # missing row is not.
                logger.warning("llm.model_not_priced",
                               extra={"model": model, "purpose": purpose})

            breaker.record_success(key)
            return LLMResult(
                text=completion.text,
                call=LLMCall(
                    purpose=purpose, provider=client.name, model=model,
                    prompt_tokens=completion.prompt_tokens,
                    output_tokens=completion.output_tokens,
                    cost_usd=cost, latency_ms=latency_ms,
                    # "retried" rather than "ok" when an earlier attempt
                    # failed: migration 015 offers the value, and a column
                    # that only ever reads 'ok' hides exactly the pattern
                    # worth watching — calls that succeed, but only second
                    # time, every time.
                    status="ok" if attempt == 0 else "retried",
                    attempt=attempt + 1,
                ),
            )
        except Exception as e:
            last_err = e
            transient = any(s in str(e) for s in _TRANSIENT)
            if transient and attempt < max_retries - 1:
                wait = _backoff_seconds(attempt)
                # Structured, not `print`. The retry path used to print, so
                # the one signal that the provider was struggling went to a
                # stream nothing collects (`T-007`).
                logger.warning("llm.transient_retry", extra={
                    "purpose": purpose, "model": model,
                    "attempt": attempt + 1, "wait_seconds": round(wait, 2),
                    # Truncated, and never the prompt: a provider's error text
                    # can echo what was sent, and what was sent is the
                    # patient's chart (`system_prompt`, the field CT-1 keeps
                    # from learners).
                    "error": str(e)[:120]})
                time.sleep(wait)
            else:
                # The breaker counts CALLS, not attempts: this one has
                # exhausted its retries, so it is one piece of evidence about
                # the provider rather than three. A permanent failure counts
                # too — an invalid key will fail every call, and stopping is
                # exactly right.
                breaker.record_failure(key)
                # So the caller can record it (`failed_call`). Zero tokens and
                # zero cost: the provider returned no usage, and an invented
                # figure would be worse than an admitted zero beside
                # status='failed'.
                try:
                    e.llm_call = LLMCall(  # type: ignore[attr-defined]
                        purpose=purpose, provider=client.name, model=model,
                        prompt_tokens=0, output_tokens=0, cost_usd=Decimal("0"),
                        latency_ms=int((time.monotonic() - started) * 1000),
                        status="failed", attempt=attempt + 1)
                except AttributeError:            # pragma: no cover — slotted
                    pass
                logger.error("llm.call_failed", extra={
                    "purpose": purpose, "model": model,
                    "attempt": attempt + 1, "transient": transient,
                    "error": str(e)[:120]})
                raise

    raise last_err                                  # pragma: no cover
