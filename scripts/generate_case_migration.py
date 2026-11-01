#!/usr/bin/env python3
"""
Generate a migration that seeds cases from cases.py into `cases` /
`case_versions` (DATA_MODEL §8.1, §9.2).

    # migration 019, the original five (already applied — do not re-run)
    python scripts/generate_case_migration.py \
        --revision 019 --down-revision 018 --cases case_1,case_2,case_3,case_4,case_5

    # migration 026, the two written in October 2026
    python scripts/generate_case_migration.py \
        --revision 026 --down-revision 025 --cases case_6,case_7

Every argument is required and the script refuses to overwrite an existing
file without `--force`. It used to take none and always write 019, which was
right exactly once: the moment a sixth case existed, the convenient thing to
run was the thing that rewrites an applied migration — silently, since the
file would still look generated and still be valid Python.

Cases enter as **draft**, never published, including the ones that already ran
in the pilot. DATA_MODEL §9.2: "Publishing them without review would make the
trigger a formality." The gate from migration 007 refuses to publish any of
them until a clinician records an approving review (T-023).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from nidan.domain.content.cases import (  # noqa: E402
    CASE_SLUGS as SLUG,
)
from nidan.domain.content.cases import (
    CASES,
    get_case,
)

VERSIONS = pathlib.Path(__file__).resolve().parent.parent / "migrations" / "versions"

# ── patient demographics ─────────────────────────────────────────────
# DATA_MODEL §8.1 wants patient.{name, age, sex}; cases.py holds that only in
# prose, and the five intros use five different sentence shapes. Parsing them
# with a regex would be fragile in a way nobody would notice, so they are
# transcribed here — each is stated unambiguously in the case's own intro and
# can be checked by reading it.
#
# NOT authored: every value below appears verbatim in patient_intro. The case
# editor (T-021) is where a clinician can correct or extend them.
PATIENT = {
    "case_1": {"name": "Ramesh Kumar", "age": 48, "sex": "male",
               "presenting_complaint": "Chest pain for 3 days"},
    "case_2": {"name": "Kavya Menon", "age": 29, "sex": "female",
               "presenting_complaint": "Breathlessness for 2 days"},
    "case_3": {"name": "Gopal Mehta", "age": 74, "sex": "male",
               "presenting_complaint": "Confusion, brought in by family"},
    "case_4": {"name": "Meera Patel", "age": 35, "sex": "female",
               "presenting_complaint": "Persistent tiredness"},
    "case_5": {"name": "Aisha Khan", "age": 21, "sex": "female",
               "presenting_complaint": "Vomiting and severe thirst"},
    "case_6": {"name": "Priya Sharma", "age": 28, "sex": "female",
               "presenting_complaint": "Daily headaches for 2 weeks"},
    "case_7": {"name": "Arjun Shah", "age": 10, "sex": "male",
               "presenting_complaint": "Cough and wheeze for several days"},
    "case_8": {"name": "Naveen Reddy", "age": 58, "sex": "male",
               "presenting_complaint": "Rectal bleeding for 4 months"},
    "case_9": {"name": "Tanvir Ahmed", "age": 26, "sex": "male",
               "presenting_complaint": "Low back pain for 10 months"},
    "case_10": {"name": "Harbans Singh", "age": 68, "sex": "male",
                "presenting_complaint": "Two blackouts in six weeks"},
}

# The slugs live in domain/content/cases.py as CASE_SLUGS, imported above as
# SLUG. They moved there in T-013, which needs them at runtime; keeping a second
# copy here would have been two sources free to drift without either failing.


def to_content(case: dict, case_id: str) -> dict:
    """Map a cases.py dict onto the §8.1 JSONB schema."""
    p = PATIENT[case_id]
    return {
        "title": case["title"],
        "patient": {
            "name": p["name"], "age": p["age"], "sex": p["sex"],
            "presenting_complaint": p["presenting_complaint"],
            "intro": case["patient_intro"],
            "opening_line": case["opening_line"],
        },
        "system_prompt": case["system_prompt"],
        "correct_diagnosis": case["correct_diagnosis"],
        "accepted_diagnoses": case["accepted_diagnoses"],
        "partial_diagnoses": case["partial_diagnoses"],
        "anchor_topic": case["anchor_topic"],
        "anchor_keywords": case["anchor_keywords"],
        "alternative_topics": case["alternative_topics"],
        "required_topics": case["required_topics"],
        "minimum_questions": case["minimum_questions"],
        "contradictory_clues": case["contradictory_clues"],
        # Shapes already match §8.1 — examination entries carry key/finding,
        # investigations carry category/result. Copied, not transformed.
        "examination": case["examination"],
        "investigations": case["investigations"],
    }


def build(revision: str, down_revision: str, case_ids: list[str]) -> str:
    rows = []
    for case_id in case_ids:
        case = get_case(case_id)
        content = to_content(case, case_id)
        rows.append({
            "slug": SLUG[case_id],
            "specialty": "general_internal_medicine",
            "content": content,
            # Denormalised from content (DATA_MODEL §5.1). They exist because
            # the admin case bank and case selection filter and sort on them,
            # and extracting from JSONB per query cannot be indexed usefully.
            "title": content["title"],
            "anchor_topic": content["anchor_topic"],
            "minimum_questions": content["minimum_questions"],
            "required_topic_count": len(content["required_topics"]),
            "key_investigation_count": sum(
                1 for v in content["investigations"].values()
                if v.get("category") == "key"),
            # sha256 of the canonical content. Canonical = sorted keys, no
            # incidental whitespace, so the same content always hashes the same
            # regardless of how it was serialised.
            "content_hash": hashlib.sha256(
                json.dumps(content, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
            ).hexdigest(),
        })

    titles = "\n".join(f"  {r['slug']} — {r['title']}" for r in rows)
    return f'''"""seed_cases

Revision ID: {revision}
Revises: {down_revision}

{len(rows)} clinical case(s), from cases.py into `cases` / `case_versions` as
version 1, status **draft** (DATA_MODEL §9.2):

{titles}

Draft, not published. §9.2: "Publishing them without review would make the
trigger a formality." The publication gate from migration 007 refuses to
publish any of them until a clinician records an approving review (T-023).

GENERATED by scripts/generate_case_migration.py. Do not edit by hand — edit
the case in nidan/domain/content/cases.py and regenerate, which is also what
keeps invariants C-1 … C-9 covering it.
"""

from __future__ import annotations

import json

from alembic import op

revision = "{revision}"
down_revision = "{down_revision}"
branch_labels = None
depends_on = None

CASES_SEED = json.loads(r"""{json.dumps(rows, ensure_ascii=False)}""")


def upgrade() -> None:
    bind = op.get_bind()
    for row in CASES_SEED:
        case_id = bind.exec_driver_sql(
            "INSERT INTO cases (slug, specialty, origin) "
            "VALUES (%s, %s, 'hand_authored') RETURNING id",
            (row["slug"], row["specialty"]),
        ).scalar()

        bind.exec_driver_sql(
            """
            INSERT INTO case_versions
                (case_id, version, status, content, title, anchor_topic,
                 minimum_questions, required_topic_count,
                 key_investigation_count, content_hash)
            VALUES (%s, 1, 'draft', %s::jsonb, %s, %s, %s, %s, %s, %s)
            """,
            (case_id, json.dumps(row["content"]), row["title"],
             row["anchor_topic"], row["minimum_questions"],
             row["required_topic_count"], row["key_investigation_count"],
             row["content_hash"]),
        )


def downgrade() -> None:
    bind = op.get_bind()
    # `= ANY(%s)` with a list, not `IN %s` with a tuple: psycopg 3 does not
    # expand tuples into an IN list the way psycopg 2 did.
    slugs = [r["slug"] for r in CASES_SEED]
    # case_versions cascades from cases.
    bind.exec_driver_sql("DELETE FROM cases WHERE slug = ANY(%s)", (slugs,))
'''


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--revision", required=True, help='e.g. "026"')
    ap.add_argument("--down-revision", required=True, help='e.g. "025"')
    ap.add_argument("--cases", required=True,
                    help="comma-separated case ids, e.g. case_6,case_7")
    ap.add_argument("--name", default="seed_cases",
                    help="filename suffix after the revision number")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing migration file")
    args = ap.parse_args()

    case_ids = [c.strip() for c in args.cases.split(",") if c.strip()]
    unknown = [c for c in case_ids if c not in CASES]
    if unknown:
        print(f"unknown case id(s): {unknown}. Known: {sorted(CASES)}",
              file=sys.stderr)
        return 2
    missing_slug = [c for c in case_ids if c not in SLUG]
    if missing_slug:
        print(f"no CASE_SLUGS entry for {missing_slug} — a case without a slug "
              f"cannot be seeded, selected or reached by URL (DATA_MODEL §5.1)",
              file=sys.stderr)
        return 2

    out = VERSIONS / f"{args.revision}_{args.name}.py"
    if out.exists() and not args.force:
        print(f"{out.name} already exists.\n\n"
              f"If it has been applied anywhere, regenerating it is not an "
              f"edit — it is a different migration under an applied revision "
              f"id, and no database will ever run the new version. Write a "
              f"new revision instead. Pass --force if you are certain.",
              file=sys.stderr)
        return 1

    out.write_text(build(args.revision, args.down_revision, case_ids),
                   encoding="utf-8")
    print(f"Wrote {out.name} — {len(case_ids)} case(s) as v1 draft: "
          + ", ".join(SLUG[c] for c in case_ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
