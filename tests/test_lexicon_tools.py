"""
T-044 · the lexicon editor's pure logic (`nidan/web/admin/content/lexicon_tools.py`).

The one that matters most is the first: the tester tells a clinician whether
the engine would credit a question. If its matcher and `extract_topics` ever
disagree, the screen starts saying something untrue with a confident face, so
that is checked against every real question on disk rather than a handful of
made-up ones.
"""

from __future__ import annotations

import glob
import json
from datetime import date
from pathlib import Path

import pytest

from nidan.domain.assessment.topics import TOPIC_KEYWORDS, extract_topics
from nidan.web.admin.content import lexicon_tools as lt

ROOT = Path(__file__).resolve().parent.parent


def _pilot_questions() -> list[str]:
    out = []
    for f in sorted(glob.glob(str(ROOT / "sessions" / "*.json"))):
        out += json.loads(Path(f).read_text(encoding="utf-8")).get("questions_asked", [])
    return out


class TestTheTesterIsTheEngine:

    def test_it_agrees_with_extract_topics_on_every_pilot_question(self):
        questions = _pilot_questions()
        assert len(questions) > 100, "the pilot sessions should be on disk"
        for q in questions:
            assert set(lt.matches(q, TOPIC_KEYWORDS)) == set(extract_topics(q)), q

    def test_it_names_every_phrase_that_matched_not_only_the_first(self):
        hits = lt.matches("worse after eating or after food?", TOPIC_KEYWORDS)
        assert {"after eating", "after food"} <= set(hits["meal_relationship"])


class TestProposals:

    def test_round_trips_through_the_form(self):
        p = lt.Proposal(added=(("meal_relationship", "evening meal"),),
                        removed=(("meal_relationship", "spicy"),),
                        new_topics=(("night_sweats", "Night sweats"),))
        form: dict[str, list[str]] = {}
        for name, value in p.encode():
            form.setdefault(name, []).append(value)
        assert lt.decode(form) == p

    def test_decoding_normalises_and_drops_junk(self):
        p = lt.decode({"add": ["meal_relationship::  Evening   MEAL ",
                               "meal_relationship::evening meal", "no-separator", "::x"]})
        assert p.added == (("meal_relationship", "evening meal"),)

    def test_apply_keeps_order_and_ignores_unknown_topics(self):
        after = lt.apply(TOPIC_KEYWORDS, lt.Proposal(
            added=(("meal_relationship", "evening meal"), ("nope", "x")),
            removed=(("meal_relationship", TOPIC_KEYWORDS["meal_relationship"][0]),)))
        assert after["meal_relationship"][-1] == "evening meal"
        assert TOPIC_KEYWORDS["meal_relationship"][0] not in after["meal_relationship"]
        assert "nope" not in after
        assert TOPIC_KEYWORDS["meal_relationship"][0] in TOPIC_KEYWORDS["meal_relationship"], \
            "apply must not mutate the engine's lexicon"

    @pytest.mark.parametrize("phrase, error", [
        ("ea", "at least 3"),
        ('say "x"', "double quotes"),
        ("after eating", "already in meal_relationship"),
    ])
    def test_phrase_refusals_are_sentences(self, phrase, error):
        c = lt.check_phrase(TOPIC_KEYWORDS, lt.Proposal(), "meal_relationship", phrase)
        assert not c.ok and any(error in e for e in c.errors)

    def test_a_phrase_in_another_topic_is_a_warning_not_an_error(self):
        other_topic, phrases = next((t, ps) for t, ps in TOPIC_KEYWORDS.items()
                                    if t != "meal_relationship")
        c = lt.check_phrase(TOPIC_KEYWORDS, lt.Proposal(), "meal_relationship", phrases[0])
        assert c.ok and any(other_topic in w for w in c.warnings)

    def test_topic_keys_are_checked(self):
        assert not lt.check_topic(TOPIC_KEYWORDS, lt.Proposal(), "Night Sweats", "x").ok
        assert not lt.check_topic(TOPIC_KEYWORDS, lt.Proposal(), "meal_relationship", "x").ok
        assert lt.check_topic(TOPIC_KEYWORDS, lt.Proposal(), "night_sweats", "Night sweats").ok

    def test_emptying_a_topic_blocks_export(self):
        removed = tuple(("radiation", p) for p in TOPIC_KEYWORDS["radiation"])
        assert lt.blocking(TOPIC_KEYWORDS, lt.Proposal(removed=removed))
        assert lt.blocking(TOPIC_KEYWORDS, lt.Proposal(new_topics=(("night_sweats", "N"),)))
        assert not lt.blocking(TOPIC_KEYWORDS, lt.Proposal(
            new_topics=(("night_sweats", "N"),), added=(("night_sweats", "sweats"),)))


class TestExport:

    P = lt.Proposal(added=(("meal_relationship", "evening meal"),
                           ("night_sweats", "sweats at night")),
                    removed=(("meal_relationship", "spicy"),),
                    new_topics=(("night_sweats", "Night sweats"),))

    def test_the_migration_compiles_and_names_its_parent(self):
        src = lt.migration_source(self.P, revision="037", down_revision="036",
                                  author="A. Admin", today=date(2026, 11, 25))
        compile(src, "037_lexicon_edit.py", "exec")
        assert 'revision = "037"' in src and 'down_revision = "036"' in src
        assert "build_golden.py" in src, "the reviewer must be told scoring moves"

    def test_the_topics_patch_is_valid_python_with_the_whole_new_lists(self):
        patch = lt.topics_patch(TOPIC_KEYWORDS, self.P)
        entries = eval("{" + patch + "}")  # noqa: S307 — our own generated literal
        assert entries["night_sweats"] == ["sweats at night"]
        assert entries["meal_relationship"] == lt.apply(TOPIC_KEYWORDS, self.P)["meal_relationship"]
        assert "spicy" not in entries["meal_relationship"]
        assert set(entries) == {"night_sweats", "meal_relationship"}, "only what changed"

    def test_next_revision_is_zero_padded(self):
        assert lt.next_revision("036") == "037"
        assert lt.next_revision("099") == "100"
