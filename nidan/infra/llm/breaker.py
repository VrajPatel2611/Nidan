"""
The circuit breaker (BUILD_PLAN T-031 criterion 2, `TECH_SPEC` §5.1).

What it is for, in the spec's own words: "after N consecutive failures, stop
calling for a cool-down and serve the fallback. Prevents a provider outage
making every request hang before failing."

**The hang is the problem, not the failure.** A call that exhausts its retries
has slept through 2 s and 4 s of backoff first, so a learner whose provider is
down waits six seconds to be told the patient is unavailable — and the next
learner waits another six, and so does every request after that. With the
breaker open they are told immediately, and `UX_SPEC` S-10 keeps their typed
question for the retry. The fallback that `infra/feedback.py` already serves
arrives at once rather than after a timeout.

**Process-local, and that is a decision rather than a shortcut.** A shared
breaker needs a store, and the two candidates both cost more than they are
worth here: Postgres puts a write on the path that is failing, and Redis is
infrastructure the product does not otherwise have. The cost of keeping it
local is that each of the 2 gunicorn workers trips its own — so the threshold
is reached up to twice before the provider is left alone — and that losing it
on restart reopens the question. Both are cheap; a provider outage lasts
longer than a worker's uptime either way.

**It does not break `ADR-0003`.** "Session state is never held in the process"
is about a learner's consultation: replaying the event log must produce the
same answer on any worker. This holds no session, no learner and no event —
it holds a count of how a dependency is behaving right now, which is the one
kind of state a process is the right place for. Nothing here is replayed and
nothing is lost but a count.

**Keyed by provider and model, not by purpose.** The thing that fails is the
model behind the call. `TECH_SPEC` §5.2 routes feedback to a stronger model
than the patient turn, so a global breaker would silence working feedback
because the patient model was rate-limited.

The lock is not defensive. The Dockerfile runs `--workers 2 --threads 4`, so
four threads per process share this state and read-modify-write on a counter
is exactly the race that loses a failure.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

from nidan.infra.telemetry.logging import get_logger

logger = get_logger(__name__)

# Three consecutive failed CALLS, not attempts: each one has already exhausted
# its retries, so three is nine attempts and about eighteen seconds of
# evidence. Tripping later would mean more learners paying the full retry wait
# to learn the same thing.
FAILURE_THRESHOLD: Final = 3

# Long enough that a provider blip resolves, short enough that a learner who
# waits and retries gets through. The probe below means a recovery is noticed
# within one cool-down rather than at the end of it.
COOLDOWN_SECONDS: Final = 30.0


class CircuitOpen(RuntimeError):
    """
    Raised instead of calling a provider that is being left alone.

    A `RuntimeError`, so the callers that already degrade on `Exception` need
    no change: `POST /questions` answers 503 `patient_unavailable` without
    consuming the question, and `infra/feedback.py` falls back to rule-based
    prose. That is the behaviour `TECH_SPEC` §5.1 asks for — "serve the
    fallback" — reached by the path that already existed.
    """


@dataclass
class _State:
    """One key's view of its provider. Mutated only under the lock."""

    failures: int = 0
    opened_at: float | None = None
    probe_in_flight: bool = False


@dataclass
class CircuitBreaker:
    """
    Closed, open, half-open — the standard three, and the probe matters.

    Without a half-open probe the breaker either reopens blind at the end of
    every cool-down (letting the whole herd through at once) or stays open
    until something external closes it. One call is let through; what happens
    to it decides the next cool-down.
    """

    threshold: int = FAILURE_THRESHOLD
    cooldown_seconds: float = COOLDOWN_SECONDS
    # Injected so tests do not sleep. Monotonic, not wall-clock: a cool-down
    # measured against a clock that can be stepped backwards by NTP would
    # stay open for as long as the correction.
    now: Callable[[], float] = time.monotonic
    _states: dict[str, _State] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # ── the call path ────────────────────────────────────────────────

    def before_call(self, key: str) -> None:
        """
        Permit the call, or refuse it.

        Raises `CircuitOpen` while the breaker is open. Returns normally when
        it is closed, and for exactly one caller per cool-down when it is
        half-open — the probe. A second thread arriving while a probe is in
        flight is refused rather than queued, because four threads all
        probing a down provider is the herd the breaker exists to stop.
        """
        with self._lock:
            state = self._states.setdefault(key, _State())
            if state.opened_at is None:
                return

            elapsed = self.now() - state.opened_at
            if elapsed < self.cooldown_seconds:
                raise CircuitOpen(
                    f"circuit open for {key}; left alone for another "
                    f"{self.cooldown_seconds - elapsed:.0f}s")

            if state.probe_in_flight:
                raise CircuitOpen(f"circuit open for {key}; a probe is in flight")

            state.probe_in_flight = True
            logger.info("llm.circuit_probe", extra={"key": key})

    def record_success(self, key: str) -> None:
        """A call returned. Consecutive means consecutive, so the count resets."""
        with self._lock:
            state = self._states.setdefault(key, _State())
            was_open = state.opened_at is not None
            state.failures = 0
            state.opened_at = None
            state.probe_in_flight = False
        if was_open:
            logger.info("llm.circuit_closed", extra={"key": key})

    def record_failure(self, key: str) -> None:
        """
        A call failed after exhausting its retries.

        A failed probe reopens for a full cool-down rather than adding to the
        count — it is already at the threshold, and a provider that fails its
        probe has told us nothing new except "still down".
        """
        with self._lock:
            state = self._states.setdefault(key, _State())
            if state.probe_in_flight:
                state.probe_in_flight = False
                state.opened_at = self.now()
                reopened = True
            else:
                state.failures += 1
                reopened = False
                if state.failures >= self.threshold and state.opened_at is None:
                    state.opened_at = self.now()
                    # ERROR, not WARNING: `TECH_SPEC` §11 lists "circuit
                    # breaker open" among the five things that page, and
                    # nothing else in this module is that.
                    logger.error("llm.circuit_opened", extra={
                        "key": key, "failures": state.failures,
                        "cooldown_seconds": self.cooldown_seconds})
        if reopened:
            logger.error("llm.circuit_reopened", extra={"key": key})

    # ── introspection, for /readyz and for tests ─────────────────────

    def state_of(self, key: str) -> str:
        """`closed` | `open` | `half_open`. Read-only."""
        with self._lock:
            state = self._states.get(key)
            if state is None or state.opened_at is None:
                return "closed"
            if self.now() - state.opened_at < self.cooldown_seconds:
                return "open"
            return "half_open"

    def open_keys(self) -> list[str]:
        """Every key not currently closed, for a health report."""
        # The snapshot is taken under the lock and read outside it. Not a
        # slip: `threading.Lock` is not reentrant, so calling `state_of` with
        # it held would deadlock the worker rather than report a breaker.
        with self._lock:
            keys = list(self._states)
        return [k for k in keys if self.state_of(k) != "closed"]

    def reset(self) -> None:
        """Forget everything. For tests, and for nothing else."""
        with self._lock:
            self._states.clear()


# One per process, shared by every call. Module-level rather than built per
# request: a breaker that forgets between requests is a counter that never
# reaches two.
breaker = CircuitBreaker()
