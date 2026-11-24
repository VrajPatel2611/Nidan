"""
The de-identified research export (`DATA_MODEL` §11.7, T-040 criterion 3).

**This is what the leakage queue protects.** Criterion 3 reads "confirmed
leaks excluded from the research export", and until this module existed there
was no export to exclude anything from — §11.7 was a query in a document.
Confirming a flag would have had no effect anyone could point at, which makes
a criterion that reads as met and is not.

§11.7's query is reproduced **verbatim**, and that is deliberate:

* **consent is required** — `p.consent_research = true`, so the default is
  out, not in;
* **confirmed leaks are excluded** — `NOT EXISTS (… lf.confirmed = true)`,
  which is the whole of T-040 criterion 3. Not `reviewed`, not
  `severity = 'high'`: only a human's confirmation removes a session, because
  a detector that could discard its own inconvenient sessions is marking
  (`ADR-0005`);
* **`research_pid` is selected, never an identifier** — and `DATA_MODEL` is
  explicit that "no email column appears… that is deliberate and should be
  preserved in any variation". So no name, no email, no `user_id`, and the
  columns are listed one by one rather than with a `*` that a future
  migration could widen.

`cv.case_id` is kept as the spec writes it, in preference to the friendlier
`cases.slug`: it is a primary key and cannot be edited, and a dataset wants
the identifier that cannot drift.

**Backfilled sessions are included, and timings are not exported.** The 16
pilot sessions carry synthetic timestamps (`DATA_MODEL` §9.3), so
`duration_seconds` is absent from the column list rather than exported with a
warning attached — §9.3's rule is that any query computing think-time must
exclude them, and the simplest way to honour it is to export nothing that
invites the calculation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

import sqlalchemy as sa

from nidan.infra.db.actor import ServiceActor
from nidan.infra.db.repositories.base import Repository

# §11.7, as written. Changing this changes what a published result rests on,
# so it is one constant rather than an f-string assembled per call.
EXPORT_SQL: Final[str] = """
    SELECT p.research_pid, s.sequence_index, cv.case_id,
           r.coverage_pct, r.question_count, r.diagnosis_verdict,
           r.anchoring_detected, r.premature_closure_detected,
           r.confirmation_bias_detected,
           r.key_investigations_done, r.key_investigations_total,
           ev.version AS engine_version
    FROM session_results r
    JOIN sessions s        ON s.id  = r.session_id
    JOIN profiles p        ON p.id  = s.user_id
    JOIN case_versions cv  ON cv.id = s.case_version_id
    JOIN engine_versions ev ON ev.id = r.engine_version_id
    WHERE p.consent_research = true
      AND s.status = 'completed'
      AND NOT EXISTS (
          SELECT 1 FROM leakage_flags lf
          WHERE lf.session_id = s.id AND lf.confirmed = true)
    ORDER BY p.research_pid, s.sequence_index
"""

COLUMNS: Final[tuple[str, ...]] = (
    "research_pid", "sequence_index", "case_id", "coverage_pct",
    "question_count", "diagnosis_verdict", "anchoring_detected",
    "premature_closure_detected", "confirmation_bias_detected",
    "key_investigations_done", "key_investigations_total", "engine_version",
)


class ResearchRepository(Repository):
    """
    One method, and it reads. There is deliberately no write here.

    `ServiceActor` only. Not because RLS would leak — `profiles` and
    `sessions` are policied and an ordinary learner would simply see their own
    row — but because a *partial* research export is the dangerous one: it
    looks like the dataset and is a single learner's slice of it, and nothing
    about the file would say so.
    """

    def rows(self) -> list[Mapping[str, Any]]:
        if not isinstance(self._actor, ServiceActor):
            raise PermissionError(
                f"the research export needs a ServiceActor, not "
                f"{type(self._actor).__name__} — a scoped actor would return "
                f"a subset that looks like the whole dataset")
        return list(self._conn.execute(sa.text(EXPORT_SQL)).mappings().all())

    def excluded_session_count(self) -> int:
        """
        How many completed, consented sessions a confirmed leak removed.

        Reported beside the export rather than left implicit: a dataset that
        silently shrank is one whose size nobody can reconcile against the
        session count, and `TECH_SPEC` §5.3's third defence is *disclosure* —
        "leakage rate reported as a limitation in any publication". This is
        the number that disclosure needs.
        """
        if not isinstance(self._actor, ServiceActor):
            raise PermissionError("the research export needs a ServiceActor")
        return self._conn.execute(sa.text("""
            SELECT count(*)
              FROM session_results r
              JOIN sessions s ON s.id = r.session_id
              JOIN profiles p ON p.id = s.user_id
             WHERE p.consent_research = true
               AND s.status = 'completed'
               AND EXISTS (SELECT 1 FROM leakage_flags lf
                           WHERE lf.session_id = s.id AND lf.confirmed = true)
        """)).scalar_one()


def to_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    """
    The export as CSV, with §11.7's column order.

    Its own function so the header cannot drift from `COLUMNS`, and so the
    order is the spec's rather than whatever a dict iterated as.
    """
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(COLUMNS),
                            extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row[key] for key in COLUMNS})
    return buffer.getvalue()
