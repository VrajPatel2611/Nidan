"""
T-044 · the migration the lexicon editor exports does what the screen said.

Applies the generated source to a real database and compares the tables with
`apply(TOPIC_KEYWORDS, proposal)`, which is the exact assertion
`tests/db/test_seed.py` will make once the `topics.py` patch lands beside it.
Then downgrades and checks the lexicon is back to the seed.
"""

from __future__ import annotations

from datetime import date

import alembic.op
import sqlalchemy as sa

from nidan.domain.assessment.topics import TOPIC_KEYWORDS
from nidan.web.admin.content import lexicon_tools as lt

PROPOSAL = lt.Proposal(
    added=(("meal_relationship", "evening meal"), ("zz_night_sweats", "sweats at night"),
           ("zz_night_sweats", "drenched")),
    removed=(("meal_relationship", TOPIC_KEYWORDS["meal_relationship"][0]),),
    new_topics=(("zz_night_sweats", "Night sweats"),))


def _lexicon(conn) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for key, phrase in conn.execute(sa.text(
            "SELECT l.topic_key, p.phrase FROM topic_lexicon l "
            "LEFT JOIN topic_phrases p ON p.topic_id = l.id")):
        out.setdefault(key, set())
        if phrase is not None:
            out[key].add(phrase)
    return out


def test_upgrade_matches_the_proposal_and_downgrade_restores_the_seed(db, monkeypatch):
    src = lt.migration_source(PROPOSAL, revision="999", down_revision="036",
                              author="test", today=date(2026, 11, 25))
    module: dict = {}
    exec(compile(src, "999_lexicon_edit.py", "exec"), module)  # noqa: S102
    monkeypatch.setattr(alembic.op, "get_bind", lambda: db, raising=False)

    module["upgrade"]()
    expected = {k: set(v) for k, v in lt.apply(TOPIC_KEYWORDS, PROPOSAL).items()}
    assert _lexicon(db) == expected

    module["downgrade"]()
    assert _lexicon(db) == {k: set(v) for k, v in TOPIC_KEYWORDS.items()}
