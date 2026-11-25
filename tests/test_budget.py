"""
T-043 criterion 3 · alert at 80 %, degrade to the cheapest model at 100 %.

No database: the gateway's side of it is a yes/no check injected by
`create_app`, so it can be driven directly. `tests/db/test_admin_ai_ops.py`
drives the same thing through a real `llm_calls` table.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from nidan.infra.budget import BudgetState
from nidan.infra.llm import gateway, pricing, provider


class _Recorder:
    name = "groq"

    def __init__(self, fail: bool = False):
        self.models: list[str] = []
        self.fail = fail

    def complete(self, *, model, **kwargs):
        self.models.append(model)
        if self.fail:
            raise RuntimeError("401 invalid api key")
        return provider.Completion(text="It burns.", prompt_tokens=10, output_tokens=4)


@pytest.fixture
def recorder(monkeypatch):
    r = _Recorder()
    monkeypatch.setattr(provider, "for_name", lambda name=None: r)
    yield r
    gateway.set_budget_guard(None)


class TestThresholds:

    @pytest.mark.parametrize("spent, alert, exhausted", [
        ("79.99", False, False), ("80", True, False),
        ("99.99", True, False), ("100", True, True), ("140", True, True),
    ])
    def test_eighty_alerts_and_one_hundred_degrades(self, spent, alert, exhausted):
        s = BudgetState(budget=Decimal("100"), spent=Decimal(spent))
        assert (s.alert, s.exhausted) == (alert, exhausted)

    def test_no_budget_never_alerts(self):
        s = BudgetState(budget=None, spent=Decimal("9999"))
        assert s.pct is None and not s.alert and not s.exhausted


class TestTheGatewayDegrades:

    def test_the_cheapest_priced_model_is_the_small_one(self):
        assert pricing.cheapest_model() == "openai/gpt-oss-20b"
        assert pricing.is_priced(pricing.cheapest_model()), \
            "degrading to an unpriced model would record $0 and undo the budget"

    def test_within_budget_it_uses_the_configured_model(self, recorder):
        gateway.set_budget_guard(lambda: False)
        result = gateway.call_llm([{"role": "user", "content": "q"}], "persona")
        assert recorder.models == ["openai/gpt-oss-120b"]
        assert result.call.model == "openai/gpt-oss-120b"

    def test_over_budget_every_purpose_uses_the_cheapest(self, recorder):
        gateway.set_budget_guard(lambda: True)
        for purpose in ("patient", "feedback"):
            result = gateway.call_llm([{"role": "user", "content": "q"}], "x",
                                      purpose=purpose)
            assert result.call.model == pricing.cheapest_model()
        assert set(recorder.models) == {pricing.cheapest_model()}

    def test_a_broken_budget_check_fails_open(self, recorder):
        def broken():
            raise RuntimeError("database down")
        gateway.set_budget_guard(broken)
        gateway.call_llm([{"role": "user", "content": "q"}], "persona")
        assert recorder.models == ["openai/gpt-oss-120b"], \
            "a cost-accounting outage must not change or stop the patient"


class TestFailuresAreRecordable:

    def test_a_failed_call_carries_a_free_failed_row(self, recorder):
        recorder.fail = True
        with pytest.raises(RuntimeError) as e:
            gateway.call_llm([{"role": "user", "content": "q"}], "persona")
        call = gateway.failed_call(e.value)
        assert call.status == "failed" and call.cost_usd == 0
        assert call.model == "openai/gpt-oss-120b" and call.attempt == 1

    def test_a_fallback_keeps_the_failed_calls_model(self, recorder):
        recorder.fail = True
        with pytest.raises(RuntimeError) as e:
            gateway.call_llm([{"role": "user", "content": "q"}], "x", purpose="feedback")
        row = gateway.fallback_call("feedback", gateway.failed_call(e.value))
        assert row.status == "fallback" and row.purpose == "feedback"
