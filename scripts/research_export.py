#!/usr/bin/env python3
"""
Write the de-identified research export (`DATA_MODEL` §11.7, T-040).

    python scripts/research_export.py                 # to stdout, as CSV
    python scripts/research_export.py -o data.csv     # to a file
    python scripts/research_export.py --json

Three filters are applied by the query and not by this script: research
consent, completion, and the absence of a **confirmed** leakage flag. It
reports how many sessions the third one removed, because `TECH_SPEC` §5.3's
third defence against persona leakage is disclosing the rate.

`research_pid` is the only identifier in the output. There is no email column
and no `user_id`; see the repository's docstring for why that is a property of
the query rather than of this file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nidan.infra.db.repositories import ServiceActor, repo_scope
from nidan.infra.db.repositories.research import to_csv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path,
                        help="write here instead of stdout")
    parser.add_argument("--json", action="store_true",
                        help="JSON instead of CSV")
    args = parser.parse_args()

    actor = ServiceActor(reason="research export (DATA_MODEL 11.7)")
    with repo_scope(actor) as db:
        rows = db.research.rows()
        excluded = db.research.excluded_session_count()

    if args.json:
        payload = json.dumps([dict(r) for r in rows], indent=2, default=str)
    else:
        payload = to_csv(rows)

    if args.out:
        args.out.write_text(payload)
        where = str(args.out)
    else:
        sys.stdout.write(payload)
        where = "stdout"

    # To stderr, so that `> data.csv` still produces a clean file.
    print(f"\n{len(rows)} session(s) exported to {where}.", file=sys.stderr)
    if excluded:
        print(f"{excluded} consented, completed session(s) were EXCLUDED by a "
              f"confirmed persona-leakage flag. Report this figure as a "
              f"limitation (TECH_SPEC 5.3).", file=sys.stderr)
    else:
        print("No session was excluded by a confirmed leakage flag.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
