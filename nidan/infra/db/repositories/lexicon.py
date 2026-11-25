"""
The topic lexicon, as the console and the match-count job see it (T-044,
`UX_SPEC` A-07).

**Nothing here writes a phrase.** The engine scores from
`nidan/domain/assessment/topics.py`, and `topic_lexicon` / `topic_phrases`
are a copy of it kept in step by migrations, which `tests/db/test_seed.py`
asserts. A phrase written straight into this table would change nothing about
how a learner is scored, and it would make the database disagree with the code
the engine reads. The editor therefore generates a migration and the
`topics.py` change for a developer to commit
(`nidan/web/admin/content/lexicon_export.py`), and this repository only
reads, apart from the two counters below.

The counters are the exception, and migration 036 grants `nidan_service`
UPDATE on those two columns and nothing else in the table.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import datetime
from typing import Any, Final

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository

# `UX_SPEC` A-07: "no match in 90 days".
DEAD_AFTER_DAYS: Final = 90

# The audit action the job writes after a successful count. The console reads
# the latest one, so the dead-phrase report can say when its figures are from
# and say plainly that it has none when the job has never run. Otherwise every
# phrase would read as dead on a fresh database.
COUNTED_ACTION: Final = "lexicon.matches_counted"


class LexiconRepository(Repository):

    def topics(self) -> Sequence[Mapping[str, Any]]:
        """Every topic with its phrase count and its dead-phrase count."""
        return self._conn.execute(sa.text("""
            SELECT l.topic_key, l.display_name, l.is_active,
                   count(p.id) AS phrases,
                   count(p.id) FILTER (
                     WHERE p.last_matched_at IS NULL
                        OR p.last_matched_at < now() - make_interval(days => :d)
                   ) AS dead
              FROM topic_lexicon l
         LEFT JOIN topic_phrases p ON p.topic_id = l.id
          GROUP BY l.id
          ORDER BY l.topic_key
        """), {"d": DEAD_AFTER_DAYS}).mappings().all()

    def phrases(self, topic_key: str) -> Sequence[Mapping[str, Any]]:
        """One topic's phrases, with when each last matched a question."""
        return self._conn.execute(sa.text("""
            SELECT p.phrase, p.match_count, p.last_matched_at,
                   (p.last_matched_at IS NULL
                    OR p.last_matched_at < now() - make_interval(days => :d))
                     AS dead
              FROM topic_phrases p
              JOIN topic_lexicon l ON l.id = p.topic_id
             WHERE l.topic_key = :k
          ORDER BY p.phrase
        """), {"k": topic_key, "d": DEAD_AFTER_DAYS}).mappings().all()

    def last_counted(self) -> datetime | None:
        """When the match-count job last finished, or None if it never has."""
        return self._conn.execute(sa.text(
            "SELECT max(created_at) FROM audit_log WHERE action = :a"
        ), {"a": COUNTED_ACTION}).scalar()

    def schema_head(self) -> str:
        """
        The database's Alembic revision. The exported migration revises it.

        Read from the database, not from the migrations folder, because the
        export has to follow what this database has actually applied. If
        someone has a newer migration locally, they will find out when
        `alembic upgrade` reports two heads, which is better than a file that
        silently claims a parent it was not written against.
        """
        return str(self._conn.execute(sa.text(
            "SELECT version_num FROM alembic_version")).scalar_one())

    # ── the match-count job (`python -m nidan.jobs lexicon`) ────────────

    def question_texts(self) -> Iterator[tuple[str, datetime, bool]]:
        """
        Every learner question still readable: `(text, created_at, backfilled)`.

        **Service actor only.** It reads across every learner's session, which
        is what `nidan_service` and its RLS bypass are for, and nothing the
        console may do. The text is matched in memory by the job and never
        stored. Only the two counters leave this process.

        Redacted questions (`ADR-0018`) are skipped: "[redacted]" matches
        nothing, and counting it as a question would mean nothing.

        `backfilled` is returned so the job can keep the 16 pilot sessions out
        of `last_matched_at`. Their timestamps are synthetic (`DATA_MODEL`
        §9.3), and recency is exactly what a synthetic timestamp gets wrong.
        """
        self._require_service("reading every learner's questions")
        rows = self._conn.execute(sa.text("""
            SELECT payload->>'text' AS text, created_at,
                   COALESCE(payload->>'provenance' = 'backfilled', false)
                     AS backfilled
              FROM session_events
             WHERE type = 'question'
               AND payload ? 'text'
               AND payload->>'text' <> '[redacted]'
        """))
        yield from ((r.text, r.created_at, r.backfilled) for r in rows)

    def phrase_list(self) -> Sequence[tuple[str, str]]:
        """`(topic_key, phrase)` for every phrase, the job's matching set."""
        return [tuple(r) for r in self._conn.execute(sa.text("""
            SELECT l.topic_key, p.phrase
              FROM topic_phrases p JOIN topic_lexicon l ON l.id = p.topic_id
        """)).all()]

    def store_counts(
        self,
        counts: Iterable[tuple[str, str, int, datetime | None]],
    ) -> int:
        """
        Overwrite `match_count` and `last_matched_at` for each phrase.

        Recomputed from scratch on every run rather than incremented, so a run
        that crashes halfway and a run made twice both leave the right answer,
        and an erasure that redacts a question stops counting on the next run.
        """
        self._require_service("updating phrase match counts")
        n = 0
        for topic_key, phrase, count, last in counts:
            n += self._conn.execute(sa.text("""
                UPDATE topic_phrases p
                   SET match_count = :c, last_matched_at = :last
                  FROM topic_lexicon l
                 WHERE l.id = p.topic_id AND l.topic_key = :k
                   AND p.phrase = :phrase
            """), {"c": count, "last": last, "k": topic_key,
                   "phrase": phrase}).rowcount
        return n

    def record_counted(self, metadata: Mapping[str, int]) -> None:
        """
        The job's audit row, which `last_counted()` reads back.

        `actor_id` is NULL, written out in the query, as
        `AuditRepository.record_system_step` does for the account jobs: the
        job is not a person, and `record()` refuses a service actor rather
        than guess an owner. Counts only, never a question.
        """
        self._require_service("recording a lexicon count")
        self._conn.execute(sa.text("""
            INSERT INTO audit_log (actor_id, action, entity_type, reason, metadata)
            VALUES (NULL, :a, 'topic_lexicon', 'phrase match counts recomputed',
                    CAST(:m AS jsonb))
        """), {"a": COUNTED_ACTION, "m": json.dumps(dict(metadata))})

    def _require_service(self, what: str) -> None:
        from nidan.infra.db.actor import ServiceActor
        if not isinstance(self._actor, ServiceActor):
            raise PermissionError(
                f"{what} needs a ServiceActor; this scope was opened as "
                f"{type(self._actor).__name__}")
