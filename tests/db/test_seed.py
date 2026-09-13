"""
T-011 · the seeded content is correct, and stays correct.

Counts alone would be a weak test — 523 rows of the wrong phrases would pass.
These check provenance: that what is in the database is what is in `cases.py`,
and that the engine thresholds still match the constants the detectors use.

That last one matters most. `engine_versions.thresholds` is the record of what
a stored result *means*. If `bias.py` changes and the row does not, every
historical score becomes uninterpretable — silently.
"""

from __future__ import annotations

import json

import sqlalchemy as sa

from nidan.domain.assessment.topics import TOPIC_KEYWORDS
from nidan.domain.content.cases import (
    CASES,
    MASTER_EXAMINATIONS,
    MASTER_INVESTIGATIONS,
    get_case,
)


class TestMasterListsMatchSource:
    def test_every_examination_is_seeded(self, db):
        rows = {r[0] for r in db.execute(sa.text("SELECT key FROM examinations"))}
        assert rows == set(MASTER_EXAMINATIONS)

    def test_every_investigation_is_seeded(self, db):
        rows = {r[0] for r in db.execute(sa.text("SELECT key FROM investigations"))}
        assert rows == set(MASTER_INVESTIGATIONS)

    def test_labels_match_the_source_not_just_the_keys(self, db):
        """A key with the wrong label renders a menu nobody can use."""
        rows = dict(db.execute(sa.text("SELECT key, label FROM examinations")).all())
        for key, spec in MASTER_EXAMINATIONS.items():
            assert rows[key] == spec["label"]

    def test_display_order_is_unique_and_dense(self, db):
        """The menu order learners see depends on it having no gaps or ties."""
        orders = [r[0] for r in db.execute(sa.text(
            "SELECT display_order FROM examinations ORDER BY display_order"))]
        assert orders == list(range(len(MASTER_EXAMINATIONS)))


class TestTopicLexicon:
    def test_every_topic_is_seeded(self, db):
        rows = {r[0] for r in db.execute(sa.text("SELECT topic_key FROM topic_lexicon"))}
        assert rows == set(TOPIC_KEYWORDS)

    def test_every_phrase_is_seeded_under_the_right_topic(self, db):
        """
        Coverage scoring is only as good as this mapping. A phrase filed under
        the wrong topic credits the learner for something they never asked.
        """
        rows = db.execute(sa.text("""
            SELECT l.topic_key, p.phrase
            FROM topic_phrases p JOIN topic_lexicon l ON l.id = p.topic_id
        """)).all()
        seeded: dict[str, set[str]] = {}
        for topic_key, phrase in rows:
            seeded.setdefault(topic_key, set()).add(phrase)
        for topic_key, phrases in TOPIC_KEYWORDS.items():
            assert seeded[topic_key] == set(phrases), f"mismatch in {topic_key}"

    def test_the_phrase_count_matches(self, db):
        n = db.execute(sa.text("SELECT count(*) FROM topic_phrases")).scalar()
        assert n == sum(len(v) for v in TOPIC_KEYWORDS.values())


class TestEngineVersion:
    def test_exactly_one_version_is_current(self, db):
        n = db.execute(sa.text(
            "SELECT count(*) FROM engine_versions WHERE is_current")).scalar()
        assert n == 1

    def test_the_seeded_version_is_1_0_0(self, db):
        v = db.execute(sa.text(
            "SELECT version FROM engine_versions WHERE is_current")).scalar()
        assert v == "1.0.0"

    def test_the_seeded_thresholds_are_exactly_the_pilot_values(self, db):
        """
        The drift guard, rewritten in T-016.

        It used to read `bias.py` as text and assert the source still contained
        `"concentration > 0.60"` — because until T-016 the detectors used
        constants and nothing linked them to this row. The comment said so:
        *"Until T-016 makes the engine read these values, this test is the only
        thing holding the two together."*

        The engine reads them now, so the comparison can be what it always
        wanted to be: the stored document against the object the code falls
        back to, **by value**. A grep could only tell you a string was still
        present; this fails if any number changes, including one the source
        formats differently.

        `Thresholds.PILOT` is the fallback used where no database exists — the
        detector tests, the validation harness, the prototype. Anything that
        writes a `session_results` row passes a version loaded from this table.
        Those two must describe the same engine or a stored score means
        something other than what it says.
        """
        from nidan.domain.assessment.thresholds import PILOT, Thresholds

        stored = db.execute(sa.text(
            "SELECT thresholds FROM engine_versions WHERE is_current")).scalar()
        if isinstance(stored, str):
            stored = json.loads(stored)

        assert Thresholds.from_row(stored) == PILOT, (
            "engine_versions and Thresholds.PILOT disagree. Do not edit the "
            "row: insert a NEW engine version, or every historical result "
            "silently starts meaning something else."
        )

    def test_the_current_engine_can_assess_a_session(self, db):
        """
        The stored document must be a usable engine, not merely well-formed
        JSON. A row that parses but cannot drive the detectors would be found
        at the end of somebody's consultation.
        """
        from nidan.domain.assessment.engine import assess
        from nidan.domain.assessment.thresholds import Thresholds
        from nidan.domain.content.cases import get_case
        from nidan.domain.events import Event

        row = db.execute(sa.text(
            "SELECT id, version, detector_version, lexicon_version, "
            "encoder_model, thresholds FROM engine_versions WHERE is_current"
        )).mappings().one()
        stored = row["thresholds"]
        if isinstance(stored, str):
            stored = json.loads(stored)

        from nidan.domain.assessment.engine import EngineVersion

        engine = EngineVersion(
            id=row["id"], version=row["version"],
            detector_version=row["detector_version"],
            lexicon_version=row["lexicon_version"],
            encoder_model=row["encoder_model"],
            thresholds=Thresholds.from_row(stored))

        result = assess([Event(1, "diagnosis", {"text": "GERD"})],
                        get_case("case_1"), engine)
        assert result.engine_version.id == row["id"]


class TestSeededCases:
    def test_all_five_cases_are_seeded(self, db):
        n = db.execute(sa.text("SELECT count(*) FROM cases")).scalar()
        assert n == len(CASES)

    def test_every_case_is_a_draft(self, db):
        """
        DATA_MODEL §9.2 — including the cases that already ran in the pilot.
        Publishing without review would make the gate a formality.
        """
        assert db.execute(sa.text(
            "SELECT bool_and(status::text = 'draft') FROM case_versions")).scalar()

    def test_denormalised_counts_match_the_content(self, db):
        """
        These columns exist so the admin case bank can filter without touching
        JSONB. If they disagree with `content`, every query built on them lies.
        """
        rows = db.execute(sa.text("""
            SELECT title, required_topic_count, key_investigation_count, content
            FROM case_versions
        """)).all()
        for title, topic_count, key_inv_count, content in rows:
            if isinstance(content, str):
                content = json.loads(content)
            assert topic_count == len(content["required_topics"]), title
            assert key_inv_count == sum(
                1 for v in content["investigations"].values()
                if v.get("category") == "key"), title

    def test_content_survives_the_json_round_trip(self, db):
        """
        The detectors read anchor_keywords and contradictory_clues. If JSONB
        storage altered them — a tuple becoming a list is fine, a nested list
        flattening is not — every detector would behave differently against the
        database than against cases.py.
        """
        rows = db.execute(sa.text("SELECT title, content FROM case_versions")).all()
        by_title = {}
        for title, content in rows:
            by_title[title] = json.loads(content) if isinstance(content, str) else content

        for case_id in CASES:
            source = get_case(case_id)
            stored = by_title[source["title"]]
            assert stored["anchor_keywords"] == source["anchor_keywords"]
            assert stored["required_topics"] == source["required_topics"]
            assert stored["minimum_questions"] == source["minimum_questions"]
            # Clues are lists of lists; JSON preserves that, tuples would not.
            assert [list(c) for c in stored["contradictory_clues"]] == \
                   [list(c) for c in source["contradictory_clues"]]

    def test_content_hash_is_a_sha256_of_the_canonical_content(self, db):
        import hashlib
        rows = db.execute(sa.text(
            "SELECT content, content_hash FROM case_versions")).all()
        for content, stored_hash in rows:
            if isinstance(content, str):
                content = json.loads(content)
            expected = hashlib.sha256(json.dumps(
                content, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False).encode("utf-8")).hexdigest()
            assert stored_hash == expected

    def test_slugs_are_human_readable_not_case_1(self, db):
        """`cases.slug` ends up in URLs and the admin console."""
        slugs = [r[0] for r in db.execute(sa.text("SELECT slug FROM cases"))]
        assert all("-" in s and not s.startswith("case_") for s in slugs)

    def test_the_publication_gate_still_refuses_these_cases(self, db):
        """
        The seeded cases are real drafts, not exceptions. Migration 007's
        trigger must refuse to publish them exactly as it would any other.
        """
        import pytest
        from sqlalchemy.exc import DBAPIError, IntegrityError

        version_id = db.execute(sa.text(
            "SELECT id FROM case_versions LIMIT 1")).scalar()
        with pytest.raises((IntegrityError, DBAPIError), match="approving clinical review"):
            db.execute(sa.text("""
                UPDATE case_versions SET status = 'published', published_at = now()
                WHERE id = :id
            """), {"id": version_id})


def test_the_seeded_slugs_are_exactly_the_ones_cases_py_declares(db):
    """
    `CASE_SLUGS` moved from scripts/generate_case_migration.py into
    domain/content/cases.py in T-013, because the application needs it at
    runtime to resolve a consultation to its `case_versions` row.

    Moving it rather than copying it is the point, and this is the test that
    keeps it a move. Two copies of a slug map would drift the first time a case
    was renamed, and the symptom would be a consultation that cannot find its
    case — reported as "the app is broken", nowhere near the cause.
    """
    from nidan.domain.content.cases import CASE_SLUGS

    seeded = set(db.execute(sa.text("SELECT slug FROM cases")).scalars())
    assert seeded == set(CASE_SLUGS.values())
