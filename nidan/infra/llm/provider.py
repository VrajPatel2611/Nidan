"""
The provider seam (BUILD_PLAN T-031 criterion 4, `ADR-0011`).

`ADR-0011`'s consequences claim "provider switching is a configuration
change". It was not: `gateway.py` imported `Groq` and constructed it inline, so
switching meant editing the module that every call goes through.

**One protocol, one implementation, and no second provider.** Building a second
adapter now would be designing against an imagined API. What this does is make
the seam real — the gateway depends on a protocol and `for_name()` resolves
`settings.LLM_PROVIDER` — so adding one later is a new file and a dict entry
rather than surgery on the call path.

The protocol returns tokens as well as text, because T-031 criterion 3 needs
them and only the provider's own response knows them. A provider that cannot
report usage returns zeros rather than guessing: a token count estimated from
character length would look authoritative in a cost dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Protocol

from nidan.config import settings


@dataclass(frozen=True)
class Completion:
    """One provider response: the text, and what it cost in tokens."""

    text: str
    prompt_tokens: int
    output_tokens: int


class Provider(Protocol):
    """What the gateway needs from a model provider, and nothing more."""

    name: str

    def complete(self, *, model: str, messages: list[dict[str, str]],
                 max_tokens: int, temperature: float) -> Completion:
        ...


class GroqProvider:
    """Groq, via the official SDK (`TECH_SPEC` §5.2)."""

    name = "groq"

    # Models that deliberate before answering, and spend the token budget
    # doing it. Prefix-matched because Groq versions within a family.
    _REASONING_PREFIXES: Final = ("openai/gpt-oss",)

    # "low", measured on 2026-11-04: a one-sentence patient reply cost 34
    # completion tokens at low and 73 at medium, for the same answer. The
    # patient turn is the high-volume path and `max_tokens` has to cover
    # reasoning AND content on these models -- at the default effort a 60-token
    # budget went entirely to deliberation and came back with a sentence cut
    # off mid-word, which is worse than a failure: a truncated reply is logged
    # as a `patient_reply` and the engine scores it.
    REASONING_EFFORT: Final = "low"

    def __init__(self) -> None:
        self._client: Any = None

    def _get_client(self) -> Any:
        """
        Built on first use, so importing this module needs no API key.

        `config.py` lets `GROQ_API_KEY` be empty on purpose — the suite, the
        assessment engine and the whole admin console work without one, and
        only the consultation needs it.
        """
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=settings.GROQ_API_KEY)
        return self._client

    def complete(self, *, model: str, messages: list[dict[str, str]],
                 max_tokens: int, temperature: float) -> Completion:
        extra: dict[str, Any] = {}
        if model.startswith(self._REASONING_PREFIXES):
            # Only for models that accept it; the others reject the parameter.
            extra["reasoning_effort"] = self.REASONING_EFFORT

        response = self._get_client().chat.completions.create(
            model=model, messages=messages,
            max_tokens=max_tokens, temperature=temperature, **extra,
        )
        message = response.choices[0].message

        # `.content` ONLY, and never `.reasoning`.
        #
        # A reasoning model returns its deliberation in a separate field, and
        # on these models that field discusses the system prompt it was given.
        # The patient's system prompt is the whole case — the correct
        # diagnosis, the trap, the contradictory clues. Observed verbatim on
        # 2026-11-04: "We are to respond as a patient in a clinical
        # simulation... So answer like ...".
        #
        # So the obvious-looking repair for an empty `content` — fall back to
        # `.reasoning` — would put the model's working, and with it the hidden
        # answer, into the patient's mouth. That is the CT-1 leak by a route no
        # serialiser guards, because it never passes through `case_view.py`.
        # An empty reply raises in the gateway and the learner keeps their
        # question. `test_the_models_reasoning_never_becomes_the_patients_words`
        # fails if this changes.
        text = (message.content or "").strip()
        # Usage is read defensively: it is the provider's field, not ours, and
        # a missing one should cost a zero in the cost table rather than a
        # 500 in the middle of a consultation.
        usage = getattr(response, "usage", None)
        return Completion(
            text=text,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )


_PROVIDERS: Final[dict[str, type]] = {"groq": GroqProvider}

_instances: dict[str, Provider] = {}


def for_name(name: str | None = None) -> Provider:
    """
    The configured provider, built once per process.

    An unknown name raises at the first call rather than falling back to a
    default. A silent fallback would mean a typo in `LLM_PROVIDER` ran the
    whole product against a provider nobody chose, and the only evidence would
    be the `provider` column in `llm_calls`.
    """
    name = (name or settings.LLM_PROVIDER).strip().lower()
    if name not in _PROVIDERS:
        raise ValueError(
            f"unknown LLM_PROVIDER {name!r}; known providers are "
            f"{sorted(_PROVIDERS)}")
    if name not in _instances:
        _instances[name] = _PROVIDERS[name]()
    return _instances[name]


def reset() -> None:
    """Drop cached instances. For tests that change configuration."""
    _instances.clear()
