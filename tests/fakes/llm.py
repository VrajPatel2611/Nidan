"""
A fake LLM gateway (BUILD_PLAN T-002).

Tests must never call a real model. It costs money, it is slow, and it is
non-deterministic — the same input can produce a different reply, so a test
built on one fails at random and is then ignored, which is worse than not
having it.

This fake replaces `call_llm`. It returns scripted replies and records every
call, so a test can assert on what the application *asked* the model as well as
on what it did with the answer.

Since T-031 it returns the gateway's own `LLMResult`, not a bare string. That
is deliberately the real dataclass rather than a look-alike: the four call
sites now read `.text` and hand `.call` to `db.llm_calls.record_call()`, and a
fake with its own shape would let a field drift out of agreement with the type
the production code actually receives.
"""

from decimal import Decimal

from nidan.infra.llm.gateway import LLMCall, LLMResult


class FakeLLMError(Exception):
    """Raised by FakeLLM when scripted to fail, standing in for a provider outage."""


class FakeLLM:
    """
    Scriptable stand-in for nidan.infra.llm.gateway.call_llm.

        llm = FakeLLM(["Doctor, my chest hurts."])
        llm("...", "...").text      -> "Doctor, my chest hurts."

    Replies are returned in order. When the script runs out, `default` is
    returned — so a test that only cares about the first reply need not script
    every subsequent one.
    """

    # Plausible, not zero. A zero-token, zero-cost call is the shape a
    # genuinely broken accounting path produces, so a test asserting the row
    # was written would pass against one.
    PROMPT_TOKENS = 120
    OUTPUT_TOKENS = 40
    COST_USD = Decimal("0.000103")
    LATENCY_MS = 350

    def __init__(self, replies=None, default="(fake patient reply)", fail_with=None,
                 model="fake-model", provider="fake"):
        self.replies = list(replies or [])
        self.default = default
        self.fail_with = fail_with
        self.model = model
        self.provider = provider
        self.calls = []          # every call, for assertions

    def __call__(self, messages, system_instruction, *, purpose="patient",
                 max_tokens=200, temperature=0.7, max_retries=3):
        self.calls.append({
            "messages": list(messages),
            "system_instruction": system_instruction,
            "purpose": purpose,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        if self.fail_with is not None:
            raise self.fail_with
        text = self.replies.pop(0) if self.replies else self.default
        return LLMResult(text=text, call=self._call_for(purpose))

    def _call_for(self, purpose):
        """The accounting half of the result, as the gateway would build it."""
        return LLMCall(
            purpose=purpose, provider=self.provider, model=self.model,
            prompt_tokens=self.PROMPT_TOKENS, output_tokens=self.OUTPUT_TOKENS,
            cost_usd=self.COST_USD, latency_ms=self.LATENCY_MS,
            status="ok", attempt=1,
        )

    # ── assertion helpers ────────────────────────────────────────────
    @property
    def call_count(self):
        return len(self.calls)

    @property
    def last_prompt(self):
        """The text of the last user message sent to the model."""
        if not self.calls:
            return None
        msgs = self.calls[-1]["messages"]
        return msgs[-1]["content"] if msgs else None

    def purposes_used(self):
        return [c["purpose"] for c in self.calls]


def as_result(text, purpose="patient"):
    """
    Wrap a reply as the gateway would, for a test that writes its own stub.

    A capture function returning a bare string used to work and now produces an
    AttributeError two frames away in the route, which reads as a 503 and not
    as a stale stub. One helper, so the shape lives in one place.
    """
    return LLMResult(text=text, call=FakeLLM()._call_for(purpose))
