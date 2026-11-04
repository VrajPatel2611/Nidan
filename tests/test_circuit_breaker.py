"""
T-031 criterion 2, second half · the circuit breaker.

`TECH_SPEC` §5.1: "after N consecutive failures, stop calling for a cool-down
and serve the fallback." The thing being prevented is not the failure — that
is the provider's doing — but the **wait**: a call that exhausts its retries
has already slept through 2 s and 4 s of backoff, so without a breaker every
request during an outage pays six seconds to be told the same thing.

Every test here drives a locally built `CircuitBreaker` with an injected
clock. Nothing sleeps, and nothing touches the process-wide `breaker` that
`gateway.py` uses — conftest resets that one around every test, because three
tests each provoking one gateway failure would otherwise trip it between them
and fail the fourth while it asserted something unrelated.
"""

from __future__ import annotations

import threading

import pytest

from nidan.infra.llm import gateway, provider
from nidan.infra.llm.breaker import CircuitBreaker, CircuitOpen

KEY = "groq:openai/gpt-oss-120b"


class FakeClock:
    """A monotonic clock a test can step."""

    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def cb(clock):
    return CircuitBreaker(threshold=3, cooldown_seconds=30.0, now=clock)


# ── closed ───────────────────────────────────────────────────────────

class TestClosed:

    def test_a_fresh_breaker_permits_calls(self, cb):
        cb.before_call(KEY)                      # must not raise
        assert cb.state_of(KEY) == "closed"

    def test_failures_below_the_threshold_do_not_open_it(self, cb):
        cb.record_failure(KEY)
        cb.record_failure(KEY)
        cb.before_call(KEY)
        assert cb.state_of(KEY) == "closed"

    def test_consecutive_means_consecutive(self, cb):
        """
        A success in the middle resets the count. Without this the breaker
        opens on the third failure of a thousand calls, which describes a
        provider that is working.
        """
        cb.record_failure(KEY)
        cb.record_failure(KEY)
        cb.record_success(KEY)
        cb.record_failure(KEY)
        cb.record_failure(KEY)
        cb.before_call(KEY)
        assert cb.state_of(KEY) == "closed"


# ── open ─────────────────────────────────────────────────────────────

class TestOpen:

    def test_the_threshold_opens_it(self, cb):
        for _ in range(3):
            cb.record_failure(KEY)
        assert cb.state_of(KEY) == "open"
        with pytest.raises(CircuitOpen):
            cb.before_call(KEY)

    def test_it_stays_open_for_the_whole_cooldown(self, cb, clock):
        for _ in range(3):
            cb.record_failure(KEY)

        clock.advance(29.9)
        with pytest.raises(CircuitOpen):
            cb.before_call(KEY)

    def test_the_refusal_says_how_long_is_left(self, cb, clock):
        for _ in range(3):
            cb.record_failure(KEY)
        clock.advance(10)

        with pytest.raises(CircuitOpen, match="20s"):
            cb.before_call(KEY)

    def test_the_refusal_names_the_model_and_nothing_else(self, cb):
        """
        A model name is not sensitive; a prompt is. The message is logged and
        must stay something a provider's error text could not have reached.
        """
        for _ in range(3):
            cb.record_failure(KEY)
        with pytest.raises(CircuitOpen) as excinfo:
            cb.before_call(KEY)

        assert KEY in str(excinfo.value)
        assert "system" not in str(excinfo.value).lower()

    def test_one_key_opening_leaves_another_alone(self, cb):
        """
        `TECH_SPEC` §5.2 routes feedback to a stronger model than the patient
        turn. A global breaker would silence working feedback because the
        patient model was rate-limited.
        """
        other = "groq:openai/gpt-oss-20b"
        for _ in range(3):
            cb.record_failure(KEY)

        assert cb.state_of(other) == "closed"
        cb.before_call(other)


# ── half-open ────────────────────────────────────────────────────────

class TestHalfOpen:

    def test_the_cooldown_elapsing_permits_one_probe(self, cb, clock):
        for _ in range(3):
            cb.record_failure(KEY)
        clock.advance(30.0)

        assert cb.state_of(KEY) == "half_open"
        cb.before_call(KEY)                      # the probe

    def test_a_second_caller_is_refused_while_the_probe_is_in_flight(self, cb, clock):
        """
        Four threads per worker (`--threads 4`). Letting them all probe at
        once is the herd the breaker exists to stop, and it would arrive at
        the exact moment the provider is least able to take it.
        """
        for _ in range(3):
            cb.record_failure(KEY)
        clock.advance(30.0)

        cb.before_call(KEY)
        with pytest.raises(CircuitOpen, match="probe is in flight"):
            cb.before_call(KEY)

    def test_a_successful_probe_closes_it(self, cb, clock):
        for _ in range(3):
            cb.record_failure(KEY)
        clock.advance(30.0)
        cb.before_call(KEY)
        cb.record_success(KEY)

        assert cb.state_of(KEY) == "closed"
        cb.before_call(KEY)
        cb.before_call(KEY)

    def test_a_failed_probe_reopens_for_a_full_cooldown(self, cb, clock):
        for _ in range(3):
            cb.record_failure(KEY)
        clock.advance(30.0)
        cb.before_call(KEY)
        cb.record_failure(KEY)

        assert cb.state_of(KEY) == "open"
        clock.advance(29.9)
        with pytest.raises(CircuitOpen):
            cb.before_call(KEY)
        clock.advance(0.2)
        assert cb.state_of(KEY) == "half_open"

    def test_a_failed_probe_does_not_need_the_threshold_again(self, cb, clock):
        """
        One failed probe reopens it. Counting back up to three would mean a
        down provider taking three more full-retry calls per cool-down,
        forever — which is the cost the breaker was added to remove.
        """
        for _ in range(3):
            cb.record_failure(KEY)
        for _ in range(4):
            clock.advance(30.0)
            cb.before_call(KEY)
            cb.record_failure(KEY)
            assert cb.state_of(KEY) == "open"


# ── reporting ────────────────────────────────────────────────────────

class TestReporting:

    def test_open_keys_lists_what_is_not_closed(self, cb):
        for _ in range(3):
            cb.record_failure(KEY)
        cb.record_failure("groq:other")

        assert cb.open_keys() == [KEY]

    def test_open_keys_does_not_deadlock(self, cb, clock):
        """
        `threading.Lock` is not reentrant and `open_keys` calls `state_of`,
        so the snapshot is taken under the lock and read outside it. A
        regression here hangs the worker rather than failing it, which is why
        this is a test and not a comment.
        """
        for _ in range(3):
            cb.record_failure(KEY)
        clock.advance(30.0)

        done = threading.Event()

        def run():
            cb.open_keys()
            done.set()

        threading.Thread(target=run, daemon=True).start()
        assert done.wait(timeout=5), "open_keys deadlocked"

    def test_readyz_reports_an_open_circuit_without_going_unready(self, monkeypatch):
        """
        Reported, not required. Failing readiness would pull the worker out of
        the load balancer during a provider outage — taking down the
        nine-tenths of the product that needs no model at all.
        """
        from nidan.app import create_app
        from nidan.infra.llm.breaker import breaker

        for _ in range(breaker.threshold):
            breaker.record_failure(KEY)

        body = create_app({"TESTING": True}).test_client().get("/readyz").get_json()
        assert body["status"] == "ready"
        assert body["checks"]["llm_circuits_open"] == [KEY]


# ── through the gateway ──────────────────────────────────────────────

class _Provider:
    name = "groq"

    def __init__(self, fail=True):
        self.fail = fail
        self.calls = 0

    def complete(self, *, model, messages, max_tokens, temperature):
        self.calls += 1
        if self.fail:
            raise RuntimeError("503 over capacity")
        return provider.Completion(text="It hurts here.", prompt_tokens=10,
                                   output_tokens=5)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(gateway, "_backoff_seconds", lambda attempt: 0.0)


class TestThroughTheGateway:

    def test_the_fourth_call_is_refused_without_reaching_the_provider(
            self, monkeypatch, no_sleep):
        """
        The point of the whole thing. Three calls fail the slow way; the
        fourth fails instantly and the provider is not touched.
        """
        p = _Provider(fail=True)
        monkeypatch.setattr(provider, "for_name", lambda name=None: p)

        for _ in range(3):
            with pytest.raises(RuntimeError):
                gateway.call_llm([{"role": "user", "content": "q"}], "persona")

        attempts_before = p.calls
        with pytest.raises(CircuitOpen):
            gateway.call_llm([{"role": "user", "content": "q"}], "persona")
        assert p.calls == attempts_before, "the provider was called anyway"

    def test_a_breaker_rejection_is_raised_before_the_retry_loop(
            self, monkeypatch, no_sleep):
        """
        Raised inside the loop, `CircuitOpen`'s message would be matched
        against `_TRANSIENT` and retried — a breaker that sleeps six seconds
        to refuse three times. `_backoff_seconds` must not be reached at all.
        """
        p = _Provider(fail=True)
        monkeypatch.setattr(provider, "for_name", lambda name=None: p)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                gateway.call_llm([{"role": "user", "content": "q"}], "persona")

        def must_not_run(attempt):
            raise AssertionError("the breaker's refusal was retried")

        monkeypatch.setattr(gateway, "_backoff_seconds", must_not_run)
        with pytest.raises(CircuitOpen):
            gateway.call_llm([{"role": "user", "content": "q"}], "persona")

    def test_a_success_keeps_the_breaker_closed(self, monkeypatch, no_sleep):
        p = _Provider(fail=False)
        monkeypatch.setattr(provider, "for_name", lambda name=None: p)

        for _ in range(5):
            assert gateway.call_llm([{"role": "user", "content": "q"}],
                                    "persona").text == "It hurts here."

    def test_an_open_breaker_still_degrades_rather_than_crashing_feedback(
            self, monkeypatch, no_sleep, case, session_factory):
        """
        `TECH_SPEC` §5.1 asks the breaker to "serve the fallback", and this is
        why `CircuitOpen` is a plain `RuntimeError`: `infra/feedback.py`
        already catches `Exception`, so no caller changed.
        """
        from nidan.domain.assessment.bias import detect_all_biases
        from nidan.domain.assessment.clinical import evaluate_clinical
        from nidan.infra.feedback import generate_feedback_with_source

        p = _Provider(fail=True)
        monkeypatch.setattr(provider, "for_name", lambda name=None: p)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                gateway.call_llm([{"role": "user", "content": "q"}], "persona")

        # Real assessment output, not a hand-made dict: the prompt builder
        # reads keys a stub would have to guess, and guessing produced a
        # KeyError that said nothing about the breaker.
        session = session_factory(questions=["Where is the pain?"],
                                  diagnosis="GERD")
        result = generate_feedback_with_source(
            detect_all_biases(session, case),
            evaluate_clinical(session, case), session, case)

        assert result.generator == "rule_fallback"
        assert result.lines
        assert result.call is None, "nothing was called, so nothing to account"
