"""
T-031 · the gateway's accounting and the provider seam.

Three things are pinned here, and only one of them is arithmetic:

1. **A price carries its date.** `pricing.py` is a dated table, not config, and
   an unknown model must cost zero rather than guess — a guessed price in a
   cost dashboard is worse than a visible gap.
2. **The gateway returns metrics it cannot write.** `nidan.infra.llm` may not
   reach the database (`pyproject.toml`'s import-linter contract, enforced by
   `lint-imports`), so `call_llm` hands back an `LLMCall` and the caller
   records it. These tests assert the shape the callers rely on.
3. **An unknown provider raises.** A silent fallback would run the product
   against a provider nobody chose, with the `llm_calls.provider` column as
   the only evidence.

The `llm_calls` row itself is written against a real database in
`tests/db/test_llm_calls.py`; nothing here touches Postgres.
"""

from decimal import Decimal

import pytest

from nidan.infra.llm import gateway, pricing, provider


class FakeProvider:
    """A provider that answers without a network, and counts its attempts."""

    name = "fake"

    def __init__(self, text="I have chest pain.", prompt_tokens=100,
                 output_tokens=20, fail_times=0, error=None):
        self.text = text
        self.prompt_tokens = prompt_tokens
        self.output_tokens = output_tokens
        self.fail_times = fail_times
        # Built here, not in the signature: a mutable default is one instance
        # shared by every FakeProvider in the module.
        self.error = error or RuntimeError("429 rate limit")
        self.attempts = 0

    def complete(self, *, model, messages, max_tokens, temperature):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise self.error
        return provider.Completion(
            text=self.text, prompt_tokens=self.prompt_tokens,
            output_tokens=self.output_tokens)


@pytest.fixture
def fake_provider(monkeypatch):
    """Replace the resolved provider, leaving the gateway's own logic intact."""
    p = FakeProvider()
    monkeypatch.setattr(provider, "for_name", lambda name=None: p)
    return p


# ── pricing ──────────────────────────────────────────────────────────

class TestPricing:

    def test_a_known_model_costs_what_the_table_says(self):
        # llama-3.3-70b-versatile: $0.59 in, $0.79 out, per million tokens.
        # 1M prompt + 1M output = exactly the two figures added.
        cost = pricing.cost_usd("llama-3.3-70b-versatile", 1_000_000, 1_000_000)
        assert cost == Decimal("1.380000")

    def test_cost_is_quantized_to_the_columns_scale(self):
        """`llm_calls.cost_usd` is NUMERIC(10,6); more precision is a lie."""
        cost = pricing.cost_usd("llama-3.3-70b-versatile", 7, 3)
        assert cost.as_tuple().exponent == -6

    def test_an_unknown_model_costs_zero_rather_than_a_guess(self):
        assert pricing.cost_usd("some-model-nobody-priced", 1000, 1000) == Decimal("0")
        assert not pricing.is_priced("some-model-nobody-priced")

    def test_a_zero_token_call_costs_zero(self):
        """A provider that reports no usage must not produce a negative or a crash."""
        assert pricing.cost_usd("llama-3.3-70b-versatile", 0, 0) == Decimal("0")

    def test_the_table_records_when_it_was_checked(self):
        """
        The date is the point. Prices move, and a figure with no date is a
        figure nobody knows whether to trust.
        """
        assert pricing.PRICES_CHECKED
        assert pricing.PRICES_CHECKED.count("-") == 2


# ── the provider seam ────────────────────────────────────────────────

class TestProviderSeam:

    def test_the_default_provider_is_groq(self):
        provider.reset()
        assert provider.for_name().name == "groq"

    def test_an_unknown_provider_raises_rather_than_falling_back(self):
        with pytest.raises(ValueError, match="unknown LLM_PROVIDER"):
            provider.for_name("not-a-provider")

    def test_the_same_instance_is_reused_within_a_process(self):
        provider.reset()
        assert provider.for_name() is provider.for_name()

    def test_importing_the_module_needs_no_api_key(self, monkeypatch):
        """
        The client is built lazily, which is what lets the whole suite, the
        assessment engine and the admin console run with no key at all.
        """
        from nidan.config import settings
        monkeypatch.setattr(settings, "GROQ_API_KEY", "")
        p = provider.GroqProvider()
        assert p._client is None


# ── what the gateway returns ─────────────────────────────────────────

class TestGatewayReturnsMetrics:

    def test_the_text_and_the_accounting_come_back_together(self, fake_provider):
        result = gateway.call_llm([{"role": "user", "content": "Where is the pain?"}],
                                  "You are a patient.")
        assert result.text == "I have chest pain."
        assert result.call.purpose == "patient"
        assert result.call.provider == "fake"
        assert result.call.prompt_tokens == 100
        assert result.call.output_tokens == 20

    def test_latency_is_measured_not_defaulted(self, fake_provider):
        result = gateway.call_llm([{"role": "user", "content": "hi"}], "persona")
        assert result.call.latency_ms >= 0
        assert isinstance(result.call.latency_ms, int)

    def test_the_system_instruction_leads_the_payload(self, fake_provider):
        """
        The persona must arrive as the system message, first. Sent as a user
        turn it becomes something the patient can be argued out of.
        """
        sent = {}

        def complete(*, model, messages, max_tokens, temperature):
            sent["messages"] = messages
            return provider.Completion(text="ok", prompt_tokens=1, output_tokens=1)

        fake_provider.complete = complete
        gateway.call_llm([{"role": "user", "content": "q"}], "You are Mr Shah.")
        assert sent["messages"][0] == {"role": "system", "content": "You are Mr Shah."}

    def test_a_first_attempt_success_is_status_ok(self, fake_provider):
        result = gateway.call_llm([{"role": "user", "content": "q"}], "persona")
        assert result.call.status == "ok"
        assert result.call.attempt == 1

    def test_a_call_that_succeeded_second_time_is_status_retried(self, monkeypatch):
        """
        Migration 015 offers 'retried', and a status column that only ever
        reads 'ok' hides the pattern worth watching: calls that succeed, but
        only on the second try, every time.
        """
        p = FakeProvider(fail_times=1)
        monkeypatch.setattr(provider, "for_name", lambda name=None: p)
        monkeypatch.setattr(gateway, "_backoff_seconds", lambda attempt: 0.0)

        result = gateway.call_llm([{"role": "user", "content": "q"}], "persona")
        assert result.call.status == "retried"
        assert result.call.attempt == 2
        assert p.attempts == 2

    def test_an_empty_reply_is_treated_as_a_failure_not_a_reply(self, monkeypatch):
        """
        An empty string is a provider failure wearing a success's clothes. Left
        alone it reaches the learner as a patient who said nothing, and gets
        logged as a `patient_reply` the engine then scores.
        """
        p = FakeProvider(text="", fail_times=0)
        monkeypatch.setattr(provider, "for_name", lambda name=None: p)
        monkeypatch.setattr(gateway, "_backoff_seconds", lambda attempt: 0.0)

        with pytest.raises(ValueError, match="Empty response"):
            gateway.call_llm([{"role": "user", "content": "q"}], "persona")

    def test_a_permanent_failure_is_not_retried(self, monkeypatch):
        """Only the transient list earns a second attempt; 401 is forever."""
        p = FakeProvider(fail_times=99, error=RuntimeError("401 invalid api key"))
        monkeypatch.setattr(provider, "for_name", lambda name=None: p)

        with pytest.raises(RuntimeError, match="401"):
            gateway.call_llm([{"role": "user", "content": "q"}], "persona")
        assert p.attempts == 1

    def test_an_unpriced_model_still_produces_a_recordable_call(self, fake_provider,
                                                                monkeypatch):
        """
        `cost_usd` is NOT NULL. A model missing from the price table must cost
        zero and still come back — the tokens and latency are true, and a zero
        beside a real token count is visibly wrong in a way a missing row is not.
        """
        monkeypatch.setenv("GROQ_MODEL_PATIENT", "a-model-with-no-price")
        result = gateway.call_llm([{"role": "user", "content": "q"}], "persona")
        assert result.call.model == "a-model-with-no-price"
        assert result.call.cost_usd == Decimal("0")
        assert result.call.prompt_tokens == 100


class TestBackoff:

    def test_the_delay_doubles_per_attempt(self, monkeypatch):
        monkeypatch.setattr(gateway.random, "uniform", lambda a, b: 0.0)
        assert gateway._backoff_seconds(0) == pytest.approx(2.0)
        assert gateway._backoff_seconds(1) == pytest.approx(4.0)
        assert gateway._backoff_seconds(2) == pytest.approx(8.0)

    def test_the_delay_carries_jitter(self, monkeypatch):
        """
        Without jitter every request that failed in the same second retries in
        the same second — one provider blip becomes a self-inflicted second one.
        """
        monkeypatch.setattr(gateway.random, "uniform", lambda a, b: b)
        assert gateway._backoff_seconds(0) == pytest.approx(2.5)
        monkeypatch.setattr(gateway.random, "uniform", lambda a, b: a)
        assert gateway._backoff_seconds(0) == pytest.approx(1.5)

    def test_jitter_never_makes_the_wait_negative(self, monkeypatch):
        for attempt in range(4):
            assert gateway._backoff_seconds(attempt) > 0


class TestNothingSensitiveIsLogged:

    def test_a_provider_error_is_truncated_before_it_is_logged(self, monkeypatch, caplog):
        """
        A provider's error text can echo what was sent, and what was sent is
        the patient's chart — the `system_prompt` CT-1 keeps from learners.
        """
        leak = "400 invalid request: " + "SECRET-CHART-DETAIL " * 50
        p = FakeProvider(fail_times=99, error=RuntimeError(leak))
        monkeypatch.setattr(provider, "for_name", lambda name=None: p)

        with caplog.at_level("ERROR"), pytest.raises(RuntimeError):
            gateway.call_llm([{"role": "user", "content": "q"}], "persona")

        logged = [r for r in caplog.records if r.msg == "llm.call_failed"]
        assert logged, "a failed call must be logged"
        assert len(logged[0].error) <= 120
        assert leak not in logged[0].error
