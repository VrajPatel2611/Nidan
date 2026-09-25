"""
Clinical content (BUILD_PLAN T-012).

**Two halves, and the split is the point.** The read methods above serve
learners and run under any scope. The authoring methods below require an
`AdminUser`, which runs as `nidan_admin` -- the only role migration 023 grants
INSERT or UPDATE on `cases` and `case_versions`. A learner's request runs as
`nidan_app`, which has SELECT and nothing more on both tables, so content cannot
change through a learner's request whatever a bug in a request handler asks for.

Until T-021 there were no write methods here at all, and migration 020's comment
said content would change "through a service connection". That plan did not
survive the audit requirement: `UX_SPEC` §12 wants every admin action attributed
to a person, and a `ServiceActor` has no person. Migration 023's docstring has
the full argument.

**Every query filters `status = 'published'` explicitly, and the
`read_published_cases` policy filters it again.** The duplication is deliberate:
the policy is the stronger guarantee but it is not always in force -- a
`ServiceActor` runs as `nidan_service`, which bypasses RLS, and the
anonymous-trial path reuses this repository through exactly such a connection.
Relying on the policy alone would mean unreviewed draft cases became visible to
trial visitors, which is the one audience with no account and no way to report
it. The policy still earns its place: it is what catches a query written later
that forgets the filter.

The five cases seeded by migration 019 are drafts on purpose (DATA_MODEL §9.2),
so these methods correctly return nothing until a clinician approves them -- the
tests publish a fixture case rather than reaching for the seeded five.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.domain.assessment.bias import clue_keywords
from nidan.infra.db.repositories.base import Repository

_SUMMARY = """
    cv.id, cv.case_id, cv.version, cv.title, cv.anchor_topic,
    cv.minimum_questions, cv.required_topic_count, cv.key_investigation_count,
    cv.content_hash, cv.published_at, c.slug, c.specialty
"""


class CaseRepository(Repository):

    def published(self) -> Sequence[Mapping[str, Any]]:
        """Every published case version, without the content payload."""
        return self._conn.execute(sa.text(f"""
            SELECT {_SUMMARY}
            FROM case_versions cv JOIN cases c ON c.id = cv.case_id
            WHERE cv.status = 'published' AND cv.retired_at IS NULL
            ORDER BY c.slug
        """)).mappings().all()

    def by_slug(self, slug: str) -> Mapping[str, Any] | None:
        """
        The current published version of a case.

        Highest version rather than the only one: a case may be republished,
        and both versions stay published so that sessions already referencing
        the old one keep resolving (DATA_MODEL §5.2).
        """
        return self._conn.execute(sa.text(f"""
            SELECT {_SUMMARY}
            FROM case_versions cv JOIN cases c ON c.id = cv.case_id
            WHERE c.slug = :slug AND cv.status = 'published'
              AND cv.retired_at IS NULL
            ORDER BY cv.version DESC LIMIT 1
        """), {"slug": slug}).mappings().first()

    def content(self, case_version_id: UUID) -> Mapping[str, Any] | None:
        """
        The full case payload (DATA_MODEL §8.1).

        Separate from the summary because it is large and most callers -- case
        lists, progress screens, a session's header -- do not want it.
        """
        return self._conn.execute(sa.text(
            "SELECT id, case_id, version, title, content "
            "FROM case_versions WHERE id = :id AND status = 'published'"),
            {"id": case_version_id},
        ).mappings().first()

    def prototype_version_id(self, slug: str) -> UUID | None:
        """
        Resolve a case version by slug **regardless of publication status**.

        Transitional, and deliberately awkward to reach.

        The Jinja prototype runs its consultations from
        `domain/content/cases.py`, but a row in `sessions` needs a real
        `case_version_id` — and migration 019 seeded all five cases as
        **drafts**, on purpose: `DATA_MODEL` §9.2 says publishing them without
        review would make the publication gate a formality. They stay drafts
        until a clinician approves them (T-023).

        So between T-013 and T-023 there is no published version to point at,
        and this is the one method allowed to say so. It returns an id and
        nothing else — no content, no title — so it cannot become a way to read
        unreviewed clinical material.

        Restricted to a `ServiceActor` so that every caller has to name a
        reason, and so a learner's scope cannot reach it even by mistake.
        Delete this when T-023 publishes the cases.
        """
        from nidan.infra.db.actor import ServiceActor

        if not isinstance(self._actor, ServiceActor):
            raise PermissionError(
                "prototype_version_id resolves unpublished cases and needs a "
                "ServiceActor with a stated reason")

        return self._conn.execute(sa.text("""
            SELECT cv.id FROM case_versions cv JOIN cases c ON c.id = cv.case_id
            WHERE c.slug = :slug AND cv.retired_at IS NULL
            ORDER BY cv.version DESC LIMIT 1
        """), {"slug": slug}).scalar()
    # ── Authoring (BUILD_PLAN T-021) ─────────────────────────────────────

    def _require_admin(self, what: str) -> None:
        """
        Refuse anything but an `AdminUser`.

        Not the security boundary — migration 023 is, and it grants INSERT and
        UPDATE on these tables to `nidan_admin` alone. This exists so a wrong
        scope fails as a sentence naming the requirement instead of as
        `permission denied for table case_versions` from three layers down,
        where it reads like a broken deployment rather than a call in the wrong
        context.
        """
        from nidan.infra.db.actor import AdminUser

        if not isinstance(self._actor, AdminUser):
            raise PermissionError(
                f"{what} writes clinical content and needs an AdminUser; this "
                f"scope was opened as {type(self._actor).__name__}, which runs "
                f"as a role the database denies these writes to")

    def bank(self) -> Sequence[Mapping[str, Any]]:
        """
        Every case with its latest version, drafts included — the case bank.

        `published()` cannot serve this screen: the five seeded cases are
        drafts on purpose (`DATA_MODEL` §9.2) and would be invisible on the one
        screen whose job is to show an author what there is to work on.
        """
        self._require_admin("the case bank")
        return self._conn.execute(sa.text(f"""
            SELECT DISTINCT ON (c.id) {_SUMMARY}, cv.status, cv.updated_at
            FROM cases c JOIN case_versions cv ON cv.case_id = c.id
            WHERE cv.retired_at IS NULL
            ORDER BY c.id, cv.version DESC
        """)).mappings().all()

    def versions(self, case_id: UUID) -> Sequence[Mapping[str, Any]]:
        """Every version of one case, newest first."""
        self._require_admin("the version history")
        return self._conn.execute(sa.text("""
            SELECT id, version, status, title, content_hash,
                   published_at, retired_at, created_at, updated_at
            FROM case_versions WHERE case_id = :case_id
            ORDER BY version DESC
        """), {"case_id": case_id}).mappings().all()

    def for_editing(self, case_version_id: UUID) -> Mapping[str, Any] | None:
        """
        One version with its full content, **whatever its status**.

        Deliberately separate from `content()`, which filters
        `status = 'published'` and is reachable by a learner's scope. An editor
        must open drafts — that is the whole job — so the method that returns
        unreviewed clinical material is a different method, behind the admin
        check, and says so in its name.

        `updated_at` comes back because `update_draft` requires it: it is the
        token that makes a concurrent overwrite impossible rather than unlikely.
        """
        self._require_admin("opening a version for editing")
        return self._conn.execute(sa.text("""
            SELECT cv.id, cv.case_id, cv.version, cv.status, cv.title,
                   cv.content, cv.content_hash, cv.published_at, cv.updated_at,
                   c.slug, c.specialty
            FROM case_versions cv JOIN cases c ON c.id = cv.case_id
            WHERE cv.id = :id
        """), {"id": case_version_id}).mappings().first()

    def create_case(self, *, slug: str, specialty: str | None = None) -> UUID:
        """
        A new case with no versions yet.

        `slug` ends up in URLs and in the admin console, so it is checked here
        rather than left to a UNIQUE violation to describe.
        """
        self._require_admin("creating a case")
        slug = (slug or "").strip().lower()
        if not slug or not all(ch.isalnum() or ch == "-" for ch in slug):
            raise ValueError(
                f"slug must be lower-case alphanumerics and hyphens, not "
                f"{slug!r} — it appears in URLs")
        return self._conn.execute(sa.text("""
            INSERT INTO cases (slug, specialty, created_by)
            VALUES (:slug, :specialty, :created_by)
            RETURNING id
        """), {"slug": slug, "specialty": specialty,
               "created_by": self._user_id()}).scalar_one()

    def create_draft(self, case_id: UUID,
                     content: Mapping[str, Any]) -> UUID:
        """
        A new draft version, numbered one past the highest that exists.

        This is also how editing a published version works (`UX_SPEC` §12.4,
        "Saving creates draft v3"): the caller passes the edited content and
        gets a new draft. Published rows are never updated, so the version a
        learner is part-way through keeps resolving to the content they started
        with.
        """
        self._require_admin("creating a draft")
        self._reject_c4(content)
        columns = _denormalised(content)
        return self._conn.execute(sa.text("""
            INSERT INTO case_versions
                (case_id, version, status, content, title, anchor_topic,
                 minimum_questions, required_topic_count,
                 key_investigation_count, content_hash)
            VALUES (
                :case_id,
                (SELECT COALESCE(MAX(version), 0) + 1
                   FROM case_versions WHERE case_id = :case_id),
                'draft', CAST(:content AS jsonb), :title, :anchor_topic,
                :minimum_questions, :required_topic_count,
                :key_investigation_count, :content_hash)
            RETURNING id
        """), {"case_id": case_id,
               "content": json.dumps(dict(content), ensure_ascii=False),
               **columns}).scalar_one()

    def update_draft(self, case_version_id: UUID, content: Mapping[str, Any],
                     *, expected_updated_at: datetime) -> datetime:
        """
        Overwrite a draft, and return its new `updated_at`.

        `expected_updated_at` is the value `for_editing` handed out when the
        form was opened. The UPDATE carries it in its WHERE clause, so two
        authors who opened the same draft cannot both save: the second one
        matches no row and is told, rather than silently discarding the first
        one's work. The caller sends the returned value back on the next save.

        Refuses a published version outright. The database would not stop this
        one — `published_requires_timestamp` constrains the status, not the
        content — so the immutability `UX_SPEC` §12.4 promises is this check.
        """
        self._require_admin("saving a draft")
        self._reject_c4(content)

        status = self._conn.execute(sa.text(
            "SELECT status FROM case_versions WHERE id = :id"),
            {"id": case_version_id}).scalar()
        if status is None:
            raise ValueError(f"no such case version: {case_version_id}")
        if status != "draft":
            raise ValueError(
                f"case version {case_version_id} is {status}, not a draft. "
                f"Published content is immutable — use create_draft() to start "
                f"the next version from it")

        columns = _denormalised(content)
        new_updated_at = self._conn.execute(sa.text("""
            UPDATE case_versions SET
                content = CAST(:content AS jsonb),
                title = :title,
                anchor_topic = :anchor_topic,
                minimum_questions = :minimum_questions,
                required_topic_count = :required_topic_count,
                key_investigation_count = :key_investigation_count,
                content_hash = :content_hash
            WHERE id = :id AND updated_at = :expected
            RETURNING updated_at
        """), {"id": case_version_id, "expected": expected_updated_at,
               "content": json.dumps(dict(content), ensure_ascii=False),
               **columns}).scalar()

        if new_updated_at is None:
            raise ConcurrentEdit(
                f"case version {case_version_id} was changed by someone else "
                f"after this form was opened; reload before saving")
        return new_updated_at

    def _reject_c4(self, content: Mapping[str, Any]) -> None:
        """
        C-4, enforced where the write happens and not only in the form.

        `UX_SPEC` §12.4 disables Save in the browser, which is the right place
        for the user experience and the wrong place for the guarantee — it is
        one HTTP request away from being bypassed, and the editor is not the
        only thing that will ever write a case. Checking it here means no code
        path stores a case whose anchor keywords overlap its contradictory
        clues, which is the whole point of the invariant (`DATA_MODEL` §8.1).
        """
        collisions = c4_collisions(content)
        if collisions:
            raise ContentInvariantViolation(
                "C-4 · anchor keywords overlap contradictory clues. A question "
                "matching one would be counted as matching both, inflating the "
                "anchoring score and citing the wrong evidence.\n  "
                + "\n  ".join(collisions))




# ── Authoring (BUILD_PLAN T-021) ─────────────────────────────────────────
#
# Everything below needs an `AdminUser`, which runs as `nidan_admin` -- the only
# role migration 023 grants INSERT or UPDATE on these two tables. The Python
# check is not the security boundary; the grant is. It exists so the failure
# arrives as a sentence naming the requirement rather than as
# `permission denied for table case_versions` three layers down.


class ConcurrentEdit(RuntimeError):
    """
    Someone else saved this version while it was open in the editor.

    A distinct type rather than a `ValueError` because the case editor has a
    specific response to it -- `UX_SPEC` §12.4's "changed by {name} 2 minutes
    ago [Reload]" -- and telling it apart from a validation failure by matching
    on a message string is how that banner eventually shows up in the wrong
    place.
    """


class ContentInvariantViolation(ValueError):
    """A case that would be wrong to store. Carries the offending terms."""


def canonical_hash(content: Mapping[str, Any]) -> str:
    """
    `case_versions.content_hash` -- sha256 of the canonical serialisation.

    Canonical means sorted keys and no incidental whitespace, so the same case
    hashes the same however it was serialised on the way in. The exact form is
    pinned by `tests/db/test_seed.py::test_content_hash_is_a_sha256_of_the_
    canonical_content` against the five seeded cases, so it is a contract with
    rows that already exist, not a free choice.
    """
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def c4_collisions(content: Mapping[str, Any]) -> list[str]:
    """
    Invariant C-4's offending pairs, or an empty list.

    Substring containment in both directions, not set intersection, because
    that is how the detectors match (`if kw in q_lower`). An intersection passes
    "heart" against "heartburn" and misses the entire bug class -- which is
    exactly what happened, and cost 14% sensitivity.

    Shares `clue_keywords` with the detector and with
    `tests/test_case_invariants.py` for the same reason that file gives: if the
    three ever disagree about what a clue's keywords are, C-4 stops protecting
    anything.
    """
    anchors = [a.lower() for a in content.get("anchor_keywords", ())]
    collisions = []
    for i, clue in enumerate(content.get("contradictory_clues", ())):
        for kw in clue_keywords(clue):
            for anchor in anchors:
                if anchor in kw or kw in anchor:
                    collisions.append(f'anchor "{anchor}" <-> clue[{i}] "{kw}"')
    return collisions


def _denormalised(content: Mapping[str, Any]) -> dict[str, Any]:
    """
    The columns `case_versions` keeps beside the JSON, derived from it.

    They exist so the case bank can sort and filter without extracting from
    JSONB on every row (`DATA_MODEL` §5.2). Deriving them here rather than
    accepting them as arguments is what stops the copy drifting from the
    original -- a caller that could pass its own `title` could pass a different
    one.
    """
    missing = sorted({"title", "anchor_topic", "minimum_questions",
                      "required_topics", "investigations"} - set(content))
    if missing:
        raise ContentInvariantViolation(
            f"case content is missing required fields: {missing}")
    return {
        "title": content["title"],
        "anchor_topic": content["anchor_topic"],
        "minimum_questions": content["minimum_questions"],
        "required_topic_count": len(content["required_topics"]),
        "key_investigation_count": sum(
            1 for v in content["investigations"].values()
            if v.get("category") == "key"),
        "content_hash": canonical_hash(content),
    }
