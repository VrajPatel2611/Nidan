"""
test_api.py
-----------
Quick connectivity check for the LLM key — **through the application's own
gateway**.

Run this BEFORE a testing session, a demo, or handing the console to a
clinical reviewer, so you do not discover a dead model halfway through
someone's consultation.

**It builds nothing of its own, and that is the whole point.** Until
2026-11-04 this script constructed its own Groq client with its own
`max_tokens`, which made it a test of a path the application does not take.
On a reasoning model that difference was the entire answer: the script
reported "empty response" while the real gateway, which sets
`reasoning_effort`, worked perfectly. A preflight that exercises a different
code path can fail green as easily as it fails red.

Nothing in the test suite can replace this. T-002 criterion 1 is that no test
makes a network call, so the suite never asks a provider whether the
configured model still exists — which is why Groq's retirement of
`llama-3.3-70b-versatile` on 2026-08-16 went unnoticed here for eleven weeks.

Usage:  python test_api.py
"""

import sys

from nidan.config import settings
from nidan.infra.llm import pricing
from nidan.infra.llm.gateway import call_llm

if not settings.llm_configured:
    print("FAIL: GROQ_API_KEY is not set in .env")
    print("      Get a free key at https://console.groq.com/keys")
    sys.exit(1)

print(f"Provider: {settings.LLM_PROVIDER}")
print(f"Model:    {settings.GROQ_MODEL}")

try:
    # max_retries=1: a diagnostic should report the failure, not spend six
    # seconds of backoff hiding it.
    result = call_llm(
        messages=[{"role": "user", "content": "Hello, what brings you in today?"}],
        system_instruction="You are a patient in a clinical simulation. "
                           "Reply in one short sentence.",
        purpose="patient",
        max_retries=1,
    )
except Exception as e:
    text = str(e)
    print(f"FAIL: {text}")
    if "401" in text or "invalid api key" in text.lower():
        print("      The key appears to be invalid — check .env")
    elif "429" in text or "rate limit" in text.lower():
        print("      Rate limited — wait a moment and retry")
    elif "404" in text or "does not exist" in text.lower():
        print(f"      '{settings.GROQ_MODEL}' is not available to this key.")
        print("      Groq retires models: https://console.groq.com/docs/deprecations")
        print("      Check what the key CAN reach, then set GROQ_MODEL in .env:")
        print("        python -c \"from nidan.infra.llm.provider import GroqProvider; "
              "print(sorted(m.id for m in GroqProvider()._get_client()"
              ".models.list().data))\"")
    elif "empty response" in text.lower():
        print("      The model answered with no content. On a reasoning model "
              "this means")
        print("      the whole token budget went to deliberation — raise "
              "max_tokens, or lower")
        print("      GroqProvider.REASONING_EFFORT.")
    sys.exit(1)

call = result.call
print(f"\nOK: the patient replied.\n    {result.text}")
print(f"\n    tokens   {call.prompt_tokens} in / {call.output_tokens} out")
print(f"    latency  {call.latency_ms} ms")
if pricing.is_priced(call.model):
    print(f"    cost     ${call.cost_usd} (prices checked {pricing.PRICES_CHECKED})")
else:
    print(f"    cost     UNPRICED — add '{call.model}' to nidan/infra/llm/pricing.py")
    print("             or every llm_calls row records a zero cost")
