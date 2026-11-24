"""persona_rule_6

Revision ID: 035
Revises: 034

Adds rule 6 to the ten seeded personas' `system_prompt`, and recomputes each
`content_hash`.

WHY THIS IS A MIGRATION AND NOT A REGENERATION
==============================================
`scripts/generate_case_migration.py` writes `system_prompt` into
`case_versions.content`, so the brief is *content* and lives in the database.
`CLAUDE.md`'s rule applies in full: **new content is a new migration, never a
regenerated one.** Re-running the generator would rewrite 019/026/028/030/032,
which no database will ever apply again.

WHY IT IS NOT OPTIONAL
======================
`api/v1/consultation.py` takes `system_prompt` from the stored `content`;
`api/routes.py` takes it from `cases.py`. So editing `_RULES` alone fixes the
prototype — the anonymous trial — and leaves **every signed-in learner** on
the old five-rule brief. T-040's persona suite imports `cases.py`, so it would
have reported a pass over a product that still leaked. That is the drift
`tests/db/test_seed.py::test_the_brief_in_the_database_is_the_brief_in_the_code`
now fails on.

WHAT RULE 6 IS FOR
==================
`validate_personas.py`'s `what_to_order` probe asks the patient what tests the
doctor should order. Two personas answered by naming the condition the test
was for — "to see if it's reflux" (`case_1`), "to check for a urinary
infection" (`case_3`) — both strings in their own `accepted_diagnoses`. Rule 4
invites it by telling the patient to defer to the doctor, and rule 5 forbids
only stating a *diagnosis*. Rule 6 closes the route. `TECH_SPEC` §5.3.

This migration is data-driven rather than embedding ten 20 KB literals: it
reads each row, replaces the rules block, and recomputes the hash with the
same canonicalisation the generator uses. It asserts the old block is present
exactly once per row, so it cannot half-apply.
"""

from __future__ import annotations

import hashlib
import json

from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None

_RULE_5 = "5. Never state or guess your own diagnosis, even if asked directly.\n"

_RULE_6 = (
    "6. If asked what tests, scans or treatment you need, or what the doctor "
    "will do next, say you do not know and that it is for the doctor to "
    "decide. NEVER name a disease or say what a test would be 'for' — not as "
    "a possibility, not as something to rule out, and not in passing.\n"
)

OLD_BLOCK = _RULE_5 + "\n"
NEW_BLOCK = _RULE_5 + _RULE_6 + "\n"


def _hash(content: dict) -> str:
    """The generator's canonicalisation, byte for byte."""
    return hashlib.sha256(json.dumps(
        content, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def _rewrite(frm: str, to: str) -> None:
    bind = op.get_bind()
    rows = bind.exec_driver_sql(
        "SELECT id, content FROM case_versions ORDER BY id").all()

    for version_id, content in rows:
        if isinstance(content, str):
            content = json.loads(content)
        prompt = content.get("system_prompt")
        if not isinstance(prompt, str):
            continue
        count = prompt.count(frm)
        if count != 1:
            raise RuntimeError(
                f"case_versions {version_id}: expected the rules block exactly "
                f"once, found {count}. Refusing to half-apply.")
        content["system_prompt"] = prompt.replace(frm, to, 1)
        bind.exec_driver_sql(
            "UPDATE case_versions SET content = %s, content_hash = %s "
            "WHERE id = %s",
            (json.dumps(content, ensure_ascii=False), _hash(content),
             version_id),
        )


def upgrade() -> None:
    _rewrite(OLD_BLOCK, NEW_BLOCK)


def downgrade() -> None:
    _rewrite(NEW_BLOCK, OLD_BLOCK)
