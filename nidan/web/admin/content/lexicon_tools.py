"""
The topic lexicon editor's logic, without Flask or a database (T-044,
`UX_SPEC` A-07).

## Why the editor exports instead of saving

The engine scores coverage from `TOPIC_KEYWORDS` in
`nidan/domain/assessment/topics.py`. The `topic_lexicon` and `topic_phrases`
tables are a copy kept in step by migrations, and `tests/db/test_seed.py`
fails if they disagree. A phrase saved straight into the table would
therefore change nothing about scoring, and it would break that agreement.

There is a second reason. Changing the lexicon changes coverage, which
changes stored results when sessions are replayed (`ADR-0003`), and
`CLAUDE.md` says never to change the lexicon without reading the golden diff.
A live editor would let a clinician move every learner's score with one
click and no record of what moved.

So the editor works on a *proposal*. An author adds and removes phrases,
creates topics, and tests questions against the result. Nothing is stored,
and the proposal travels in the form. When it is right, the page generates
two things a developer commits together: the migration that changes the
tables, and the new `TOPIC_KEYWORDS` entries. That turns "every new case
needs two hand-written migrations" into one generated file and one paste,
without making scoring editable from a browser.

## The matcher is the engine's

`matches()` is the rule `extract_topics` applies: a lowercase substring, first
match per topic. `tests/test_lexicon_tools.py` checks that the two agree on
every question in the 16 pilot sessions. If the engine's matcher ever changes
(embeddings, `ADR-0013`), that test is what says the tester has started
telling authors something untrue.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Final

Lexicon = Mapping[str, Sequence[str]]

# Between a topic key and its phrase in a hidden form field. A key cannot
# contain a colon, so the first "::" is always the boundary.
SEP: Final = "::"

TOPIC_KEY: Final = re.compile(r"^[a-z][a-z0-9_]{2,47}$")

# Below this, a phrase matches inside unrelated words: "ear" is in "heart",
# "year" and "early". Refused rather than warned about, because the damage is
# invisible. It credits learners for topics they never asked about.
MIN_PHRASE_CHARS: Final = 3

# Shorter than this is allowed but flagged.
SHORT_PHRASE_CHARS: Final = 5


def normalise(phrase: str) -> str:
    """Lowercase, trimmed, single-spaced, which is the form the matcher compares."""
    return " ".join(phrase.lower().split())


@dataclass(frozen=True)
class Proposal:
    """Changes against the current lexicon. Empty means nothing to export."""

    added: tuple[tuple[str, str], ...] = ()          # (topic_key, phrase)
    removed: tuple[tuple[str, str], ...] = ()        # (topic_key, phrase)
    new_topics: tuple[tuple[str, str], ...] = ()     # (topic_key, display name)

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.new_topics)

    def encode(self) -> list[tuple[str, str]]:
        """Hidden form fields that carry the proposal from one request to the next."""
        return ([("add", f"{t}{SEP}{p}") for t, p in self.added]
                + [("remove", f"{t}{SEP}{p}") for t, p in self.removed]
                + [("new_topic", f"{t}{SEP}{n}") for t, n in self.new_topics])


def decode(form: Mapping[str, Sequence[str]]) -> Proposal:
    """
    The proposal back out of the form, de-duplicated and in order.

    Takes `{name: [values]}` so it works on a Werkzeug `MultiDict` via
    `form.to_dict(flat=False)` without importing Flask here.
    """
    def pairs(name: str) -> tuple[tuple[str, str], ...]:
        out: list[tuple[str, str]] = []
        for raw in form.get(name, ()):
            left, sep, right = raw.partition(SEP)
            item = (left.strip(), right.strip() if name == "new_topic"
                    else normalise(right))
            if sep and item[0] and item[1] and item not in out:
                out.append(item)
        return tuple(out)
    return Proposal(added=pairs("add"), removed=pairs("remove"),
                    new_topics=pairs("new_topic"))


@dataclass
class Check:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def check_phrase(lexicon: Lexicon, proposal: Proposal, topic: str,
                 phrase: str) -> Check:
    """Whether one phrase may be added to one topic, said as a sentence."""
    c = Check()
    phrase = normalise(phrase)
    known = set(lexicon) | {k for k, _ in proposal.new_topics}
    if topic not in known:
        c.errors.append(f"There is no topic called {topic!r}.")
    if len(phrase) < MIN_PHRASE_CHARS:
        c.errors.append(
            f"A phrase needs at least {MIN_PHRASE_CHARS} characters. Shorter "
            f"ones match inside unrelated words.")
    if '"' in phrase or "\\" in phrase:
        c.errors.append("Phrases cannot contain double quotes or backslashes.")
    current = apply(lexicon, proposal)
    if phrase in current.get(topic, ()):
        c.errors.append(f"“{phrase}” is already in {topic}.")
    if c.errors:
        return c
    if len(phrase) < SHORT_PHRASE_CHARS:
        c.warnings.append(
            f"“{phrase}” is short, so check it does not match inside other "
            f"words. Try it in the tester below.")
    elsewhere = [t for t, ps in current.items() if t != topic and phrase in ps]
    if elsewhere:
        c.warnings.append(
            f"“{phrase}” is also in {', '.join(elsewhere)}, so one question "
            f"would cover both topics.")
    return c


def check_topic(lexicon: Lexicon, proposal: Proposal, key: str,
                name: str) -> Check:
    c = Check()
    if not TOPIC_KEY.match(key):
        c.errors.append(
            "A topic key is 3–48 characters: lowercase letters, digits and "
            "underscores, starting with a letter. For example, night_sweats.")
    if key in lexicon or key in {k for k, _ in proposal.new_topics}:
        c.errors.append(f"{key!r} already exists.")
    if not name.strip():
        c.errors.append("Give the topic a display name.")
    return c


def apply(lexicon: Lexicon, proposal: Proposal) -> dict[str, list[str]]:
    """The lexicon as it would be with the proposal committed. Order is kept."""
    out = {k: list(v) for k, v in lexicon.items()}
    for key, _ in proposal.new_topics:
        out.setdefault(key, [])
    for topic, phrase in proposal.removed:
        if phrase in out.get(topic, []):
            out[topic].remove(phrase)
    for topic, phrase in proposal.added:
        if topic in out and phrase not in out[topic]:
            out[topic].append(phrase)
    return out


def blocking(lexicon: Lexicon, proposal: Proposal) -> list[str]:
    """
    What stops this proposal being exported.

    A topic left with no phrases can never be covered, so every case that
    requires it would mark every learner as having missed it. That is a
    silent scoring failure, so it blocks the export rather than warning.
    """
    after = apply(lexicon, proposal)
    return [f"{t} would have no phrases left, so no question could ever "
            f"cover it." for t, ps in after.items() if not ps]


def matches(text: str, lexicon: Lexicon) -> dict[str, list[str]]:
    """
    `{topic: [phrases that matched]}`, using the same rule as `extract_topics`.

    `extract_topics` stops at the first phrase per topic. This returns all of
    them, because "which phrase caught it" is what an author needs to see,
    but the set of topics is identical, and that is what the tests pin.
    """
    lowered = text.lower()
    found: dict[str, list[str]] = {}
    for topic, phrases in lexicon.items():
        hit = [p for p in phrases if p in lowered]
        if hit:
            found[topic] = hit
    return found


# ── export ──────────────────────────────────────────────────────────────

def next_revision(head: str) -> str:
    """'035' → '036'. Revisions in this repository are zero-padded integers."""
    return f"{int(head) + 1:03d}"


def display_name(key: str, proposal: Proposal) -> str:
    return dict(proposal.new_topics).get(key) or key.replace("_", " ").capitalize()


def migration_filename(revision: str) -> str:
    return f"{revision}_lexicon_edit.py"


def migration_source(proposal: Proposal, *, revision: str, down_revision: str,
                     author: str, today: date) -> str:
    """
    A complete Alembic revision that applies the proposal, and reverses it.

    Data as JSON at the top, logic below, which is the shape
    `generate_seed_migration.py` uses (031 is an example), so a reviewer
    reads it the same way.
    """
    new_keys = {k for k, _ in proposal.new_topics}
    topics = [{"topic_key": k, "display_name": n,
               "phrases": [p for t, p in proposal.added if t == k]}
              for k, n in proposal.new_topics]
    added = [{"topic_key": t, "phrase": p}
             for t, p in proposal.added if t not in new_keys]
    removed = [{"topic_key": t, "phrase": p} for t, p in proposal.removed]

    def dump(v: object) -> str:
        return json.dumps(v, ensure_ascii=True)

    summary = []
    if topics:
        summary.append(f"{len(topics)} new topic(s): "
                       + ", ".join(t["topic_key"] for t in topics))
    if added:
        summary.append(f"{len(added)} phrase(s) added to existing topics")
    if removed:
        summary.append(f"{len(removed)} phrase(s) removed")

    return f'''"""lexicon edit

Revision ID: {revision}
Revises: {down_revision}

{"; ".join(summary)}.

GENERATED by the admin console's topic lexicon editor (T-044, `UX_SPEC` A-07)
on {today.isoformat()}, from a proposal by {author}. Commit it in the SAME
commit as the matching `TOPIC_KEYWORDS` change in
`nidan/domain/assessment/topics.py`, which the console showed beside this file.
`tests/db/test_seed.py` fails if one lands without the other.

Before committing, run `python scripts/build_golden.py` and read which pilot
learners' coverage moved. A lexicon change re-scores every replayed session.
"""

from __future__ import annotations

import json

from alembic import op

revision = "{revision}"
down_revision = "{down_revision}"
branch_labels = None
depends_on = None

NEW_TOPICS = json.loads(r"""{dump(topics)}""")
ADDED = json.loads(r"""{dump(added)}""")
REMOVED = json.loads(r"""{dump(removed)}""")


def _add_phrase(bind, topic_key, phrase):
    bind.exec_driver_sql(
        "INSERT INTO topic_phrases (topic_id, phrase) "
        "SELECT id, %s FROM topic_lexicon WHERE topic_key = %s",
        (phrase, topic_key))


def _remove_phrase(bind, topic_key, phrase):
    bind.exec_driver_sql(
        "DELETE FROM topic_phrases p USING topic_lexicon l "
        "WHERE l.id = p.topic_id AND l.topic_key = %s AND p.phrase = %s",
        (topic_key, phrase))


def upgrade() -> None:
    bind = op.get_bind()
    for t in NEW_TOPICS:
        bind.exec_driver_sql(
            "INSERT INTO topic_lexicon (topic_key, display_name) VALUES (%s, %s)",
            (t["topic_key"], t["display_name"]))
        for phrase in t["phrases"]:
            _add_phrase(bind, t["topic_key"], phrase)
    for r in REMOVED:
        _remove_phrase(bind, r["topic_key"], r["phrase"])
    for a in ADDED:
        _add_phrase(bind, a["topic_key"], a["phrase"])


def downgrade() -> None:
    bind = op.get_bind()
    for a in ADDED:
        _remove_phrase(bind, a["topic_key"], a["phrase"])
    for r in REMOVED:
        _add_phrase(bind, r["topic_key"], r["phrase"])
    # Named rows only; topic_phrases cascades from topic_lexicon.
    keys = [t["topic_key"] for t in NEW_TOPICS]
    if keys:
        bind.exec_driver_sql(
            "DELETE FROM topic_lexicon WHERE topic_key = ANY(%s)", (keys,))
'''


def topics_patch(lexicon: Lexicon, proposal: Proposal) -> str:
    """
    The `TOPIC_KEYWORDS` entries to paste, one per changed or new topic.

    Whole entries, not a diff. A changed entry replaces the old one and a new
    one goes at the end of the dict. A whole list is harder to mis-apply than
    a line-level patch against a file that may have moved since.
    """
    after = apply(lexicon, proposal)
    changed = ([k for k, _ in proposal.new_topics]
               + [t for t in lexicon
                  if any(t == k for k, _ in proposal.added + proposal.removed)])
    lines = []
    for key in dict.fromkeys(changed):
        verb = "NEW, add at the end" if key not in lexicon else "REPLACE the existing entry"
        lines.append(f"    # {key}: {verb}")
        lines.append(f"    {key!r}: [")
        lines.extend(f"        {json.dumps(p, ensure_ascii=False)}," for p in after[key])
        lines.append("    ],")
    return "\n".join(lines)
