"""
The 16 pilot sessions, as event logs (BUILD_PLAN T-016).

The pilot predates the event log: its sessions were stored as a flat JSON
summary. To assess them with the engine that ships, they have to be expressed
as events — which is exactly the translation `assess` will be asked to survive
for every future change to the detectors.

**Topics come from the stored `topics_covered`, not from re-extracting them.**
That is deliberate. The pilot's record of what the system understood at the time
is the thing under test; re-running `extract_topics` would substitute today's
lexicon and quietly turn a detector test into a lexicon test. It is the same
reasoning `DATA_MODEL` §8.2 gives for putting `matched_topics` on the reply
rather than the question.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
from datetime import datetime
from typing import Any

from nidan.domain.events import Event

REPO = pathlib.Path(__file__).resolve().parent.parent


def pilot_files() -> list[pathlib.Path]:
    """
    The tracked pilot sessions, from git rather than a glob.

    `sessions/` also accumulates files written by the test suite and by local
    runs; only the committed ones are the research record.
    """
    listed = subprocess.run(
        ["git", "ls-files", "sessions/"], cwd=REPO,
        capture_output=True, text=True, check=True).stdout.split()
    files = sorted(REPO / f for f in listed if f.endswith(".json"))

    # Fail here, saying what is wrong, rather than deep inside a JSON parse.
    # git lists what is COMMITTED; a file can be listed and absent from the
    # working tree, and the resulting FileNotFoundError three frames down does
    # not suggest the fix.
    missing = [f.name for f in files if not f.exists()]
    assert not missing, (
        f"{len(missing)} pilot session(s) are committed but missing from the "
        f"working tree: {missing[:3]}. Restore them with "
        f"`git checkout -- sessions/` — they are the research record.")
    assert files, (
        "no pilot sessions found. These tests read the committed files via "
        "`git ls-files`, so they need a git checkout, not a source tarball.")
    return files


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp)
    except ValueError:                                  # pragma: no cover
        return None


def events_from(record: dict[str, Any]) -> list[Event]:
    """
    One pilot session, as the event log it would have produced.

    Ordering follows a real consultation: questions and replies first, then
    examinations and investigations, then the diagnosis. Only the diagnosis's
    position actually matters to the detectors — none of them reads event
    order — but a log that reads like a consultation is a log someone can
    check by eye.
    """
    started = _parse(record.get("start_time"))
    ended = _parse(record.get("end_time"))

    events: list[Event] = []
    seq = 1

    def add(event_type: str, payload: dict[str, Any],
            at: datetime | None = None) -> None:
        nonlocal seq
        events.append(Event(seq, event_type, payload, created_at=at))
        seq += 1

    questions = record.get("questions_asked", [])
    for index, question in enumerate(questions):
        add("question", {"text": question, "char_count": len(question)},
            at=started if index == 0 else None)
        # Every topic the pilot recorded is attached to the first reply. The
        # summary format kept only the aggregate, so per-question attribution
        # is not recoverable — and the detectors read the aggregate anyway.
        add("patient_reply",
            {"text": "",
             "matched_topics": record.get("topics_covered", []) if index == 0 else []})

    for key in record.get("exams_performed", []):
        add("examination", {"key": key, "label": key, "finding": ""})

    for key in record.get("investigations_ordered", []):
        add("investigation", {"key": key, "label": key, "result": ""})

    if record.get("early_diagnosis"):
        add("early_diagnosis", {"text": record["early_diagnosis"]})

    if record.get("diagnosis_submitted"):
        add("diagnosis", {"text": record["diagnosis_submitted"]}, at=ended)

    return events


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
