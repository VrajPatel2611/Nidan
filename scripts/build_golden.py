#!/usr/bin/env python3
"""
Regenerate the golden assessment record (BUILD_PLAN T-016).

    python scripts/build_golden.py

Writes `tests/golden/pilot_assessments.json`: the engine's output for all 16
pilot sessions, as it stands today.

**Run this only when a result is MEANT to change**, and read the diff before
committing it. That diff is the point of the file — it is the only place a
change to a detector, a threshold or the lexicon becomes visible as a list of
which learners' results moved and by how much. Regenerating it to make a red
build green throws away the one artefact that would have said what broke.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from nidan.domain.assessment.engine import assess  # noqa: E402
from nidan.domain.content.cases import get_case  # noqa: E402
from tests.pilot import events_from, load, pilot_files  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "tests" / "golden" / "pilot_assessments.json"


def assessment_of(path: pathlib.Path) -> dict:
    record = load(path)
    result = assess(events_from(record), get_case(record["case_id"]))
    return {
        "case_id": record["case_id"],
        "question_count": result.question_count,
        "examination_count": result.examination_count,
        "investigation_count": result.investigation_count,
        "coverage_pct": result.coverage_pct,
        "topics_hit": result.topics_hit,
        "topics_missed": result.topics_missed,
        "diagnosis_verdict": result.diagnosis_verdict,
        "key_investigations_done": result.key_investigations_done,
        "key_investigations_total": result.key_investigations_total,
        "scalars": result.scalars,
        "detail": {
            name: {
                "rule_fired": detail["rule_fired"],
                "counters": detail["counters"],
            }
            for name, detail in result.bias_detail.items()
        },
    }


def main() -> None:
    golden = {path.name: assessment_of(path) for path in pilot_files()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"Wrote {OUT.relative_to(OUT.parent.parent.parent)} — "
          f"{len(golden)} pilot sessions")


if __name__ == "__main__":
    main()
