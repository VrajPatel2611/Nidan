"""
Clinical review and its worklist (BUILD_PLAN T-023, `DATA_MODEL` §5.2, §8.4).

Two actors, two halves, and they are not interchangeable.

**An administrator assigns.** `assign` and `unassign` write `review_assignments`
and need an `AdminUser`; migration 024 grants that role INSERT and DELETE there
and grants the reviewer only SELECT. A reviewer who could assign themselves work
could also assign themselves the case they wrote.

**A reviewer judges.** `record` writes `clinical_reviews` and needs a
`ReviewerUser`. The queue reads sit in between and either may call them.

**The rubric rule is enforced here, not only in the form.** `PRD` FR-12.5 and
`UX_SPEC` §12.6 say a dimension below 4 cannot be recorded as approved, and the
database does not check it -- `scores` is JSONB. The screen disables the Approve
button, which is right for the user and is one HTTP request away from being the
only check. Same argument as C-4 in `cases.py`, and the same answer.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository

DECISIONS: tuple[str, ...] = ("approved", "changes_requested", "rejected")

# The four dimensions, and the schema's own shape (`DATA_MODEL` §8.4). Named
# here rather than accepted as whatever the caller sends: a review missing a
# dimension is not a lenient review, it is an unanswered question.
RUBRIC: tuple[str, ...] = (
    "clinical_plausibility", "internal_consistency", "trap_validity",
    "solvability",
)

# Stored on every row so the rubric can change without making past reviews
# unreadable. Bump it when a dimension is added, removed or redefined.
RUBRIC_VERSION = "v1"

# Below this, a case cannot be recorded as approved.
APPROVAL_FLOOR = 4


class RubricViolation(ValueError):
    """A review that would be wrong to record. Names what is wrong."""


class ReviewRepository(Repository):
    """Assignments and recorded judgements."""

    # ── Assignment (admin) ───────────────────────────────────────────────

    def _require_admin(self, what: str) -> None:
        from nidan.infra.db.actor import AdminUser

        if not isinstance(self._actor, AdminUser):
            raise PermissionError(
                f"{what} needs an AdminUser; this scope was opened as "
                f"{type(self._actor).__name__}, which runs as a role the "
                f"database denies this write to")

    def _require_reviewer(self, what: str) -> None:
        from nidan.infra.db.actor import ReviewerUser

        if not isinstance(self._actor, ReviewerUser):
            raise PermissionError(
                f"{what} needs a ReviewerUser (use current_reviewer()); this "
                f"scope was opened as {type(self._actor).__name__}")

    def assign(self, case_version_id: UUID, reviewer_id: UUID) -> None:
        """
        Put a version on a reviewer's list. Assigning twice is a no-op.

        `ON CONFLICT DO NOTHING` rather than an error: the composite primary key
        already makes a duplicate impossible, and an admin clicking Assign twice
        has expressed the same intention twice, not made a mistake.
        """
        self._require_admin("assigning a reviewer")
        self._conn.execute(sa.text("""
            INSERT INTO review_assignments
                (case_version_id, reviewer_id, assigned_by)
            VALUES (:version, :reviewer, :by)
            ON CONFLICT (case_version_id, reviewer_id) DO NOTHING
        """), {"version": case_version_id, "reviewer": reviewer_id,
               "by": self._user_id()})

    def unassign(self, case_version_id: UUID, reviewer_id: UUID) -> None:
        """
        Take it off their list. Does not touch any review already recorded.

        Deleting the assignment and deleting the judgement are different acts,
        and only the first is reversible.
        """
        self._require_admin("unassigning a reviewer")
        self._conn.execute(sa.text("""
            DELETE FROM review_assignments
            WHERE case_version_id = :version AND reviewer_id = :reviewer
        """), {"version": case_version_id, "reviewer": reviewer_id})

    def reviewers(self) -> Sequence[Mapping[str, Any]]:
        """
        Everyone who may be assigned a review: id, name and role, nothing else.

        **No longer bypasses RLS.** It used to need a `ServiceActor`, because
        `own_profile` (migration 016) has no `TO` clause and so reduced even an
        administrator to their own row. Migration 025 adds
        `privileged_profiles_are_mutually_visible`, and the policy now does the
        narrowing the query used to assert: a learner's row is unreadable to
        this scope whatever SQL is written here.

        That matters beyond tidiness. `ADR-0016` confined the bypass to one
        module, and this was a second — one more place where a mistake is
        invisible because nothing is enforcing anything.

        `AdminUser` or `ReviewerUser`: assigning is admin-only, but the queue
        resolves `reviewer_id` to a name for both (`UX_SPEC` §12.6).
        """
        from nidan.infra.db.actor import AdminUser, ReviewerUser

        if not isinstance(self._actor, AdminUser | ReviewerUser):
            raise PermissionError(
                "listing reviewers needs an AdminUser or ReviewerUser (use "
                "current_admin() or current_reviewer()); this scope was opened "
                f"as {type(self._actor).__name__}")
        return self._conn.execute(sa.text("""
            SELECT id, display_name, platform_role
            FROM profiles
            WHERE platform_role IN ('reviewer', 'admin') AND deleted_at IS NULL
            ORDER BY display_name NULLS LAST, id
        """)).mappings().all()

    # ── The queue (`UX_SPEC` §12.6) ──────────────────────────────────────

    def assigned_to_me(self) -> Sequence[Mapping[str, Any]]:
        """
        This reviewer's outstanding work — the "Assigned to me" tab.

        Excludes versions they have already reviewed: a decision is final, so a
        version they have ruled on is not outstanding for them even while it is
        still open for the other reviewer.
        """
        return self._conn.execute(sa.text("""
            SELECT cv.id AS case_version_id, cv.version, cv.title, cv.status,
                   cv.anchor_topic, c.slug, c.specialty, ra.assigned_at
            FROM review_assignments ra
            JOIN case_versions cv ON cv.id = ra.case_version_id
            JOIN cases c ON c.id = cv.case_id
            WHERE ra.reviewer_id = :me
              AND cv.retired_at IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM clinical_reviews r
                WHERE r.case_version_id = cv.id AND r.reviewer_id = :me)
            ORDER BY ra.assigned_at DESC
        """), {"me": self._user_id()}).mappings().all()

    def pending(self) -> Sequence[Mapping[str, Any]]:
        """
        Every version assigned to anybody and not yet approved — "All pending".

        Keyed on the absence of an *approving* review rather than of any review:
        a version with one `changes_requested` against it is still waiting, and
        hiding it is how a case goes quiet for a fortnight.
        """
        return self._conn.execute(sa.text("""
            SELECT DISTINCT cv.id AS case_version_id, cv.version, cv.title,
                   cv.status, cv.anchor_topic, c.slug, c.specialty,
                   min(ra.assigned_at) AS assigned_at,
                   count(DISTINCT ra.reviewer_id) AS reviewers,
                   count(DISTINCT r.id) AS reviews_recorded
            FROM review_assignments ra
            JOIN case_versions cv ON cv.id = ra.case_version_id
            JOIN cases c ON c.id = cv.case_id
            LEFT JOIN clinical_reviews r ON r.case_version_id = cv.id
            WHERE cv.retired_at IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM clinical_reviews a
                WHERE a.case_version_id = cv.id AND a.decision = 'approved')
            GROUP BY cv.id, cv.version, cv.title, cv.status, cv.anchor_topic,
                     c.slug, c.specialty
            ORDER BY min(ra.assigned_at)
        """)).mappings().all()

    def completed(self, limit: int = 50) -> Sequence[Mapping[str, Any]]:
        """Recorded decisions, newest first — the "Completed" tab."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        return self._conn.execute(sa.text("""
            SELECT r.id, r.case_version_id, r.reviewer_id, r.decision,
                   r.scores, r.comments, r.reviewed_at,
                   cv.version, cv.title, c.slug
            FROM clinical_reviews r
            JOIN case_versions cv ON cv.id = r.case_version_id
            JOIN cases c ON c.id = cv.case_id
            ORDER BY r.reviewed_at DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()

    def for_version(self, case_version_id: UUID) -> Sequence[Mapping[str, Any]]:
        """Every review of one version, newest first."""
        return self._conn.execute(sa.text("""
            SELECT id, reviewer_id, decision, scores, comments, reviewed_at
            FROM clinical_reviews
            WHERE case_version_id = :version
            ORDER BY reviewed_at DESC, id DESC
        """), {"version": case_version_id}).mappings().all()

    def has_approval(self, case_version_id: UUID) -> bool:
        """
        Whether publication is permitted (`PRD` FR-12.5).

        The authority is migration 007's `enforce_clinical_approval` trigger,
        which refuses the UPDATE regardless of what any caller believes. This is
        how the console finds out *before* trying, so a clinician sees "no
        approving review yet" rather than a Postgres exception.
        """
        return bool(self._conn.execute(sa.text("""
            SELECT EXISTS (
                SELECT 1 FROM clinical_reviews
                WHERE case_version_id = :version AND decision = 'approved')
        """), {"version": case_version_id}).scalar())

    def is_author(self, case_version_id: UUID, reviewer_id: UUID) -> bool:
        """
        Whether this reviewer created the case they are being asked to judge.

        `UX_SPEC` §12.6 warns rather than blocks: a two-person team sometimes
        has no one else, and a rule that cannot be followed gets worked around
        instead of obeyed. The console shows the warning; this answers it.
        """
        return bool(self._conn.execute(sa.text("""
            SELECT EXISTS (
                SELECT 1 FROM case_versions cv JOIN cases c ON c.id = cv.case_id
                WHERE cv.id = :version AND c.created_by = :reviewer)
        """), {"version": case_version_id, "reviewer": reviewer_id}).scalar())

    # ── Recording a judgement (reviewer) ─────────────────────────────────

    def record(self, case_version_id: UUID, *, decision: str,
               scores: Mapping[str, Any],
               comments: str | None = None) -> UUID:
        """
        Write one review. The reviewer is taken from the scope, never passed in.

        Same reasoning as the audit log: a caller who could name the reviewer
        could attribute a judgement to a clinician who never made it, and a
        review that can be made to lie about who signed it off is worse than no
        review -- it is sign-off that supports the wrong conclusion.
        """
        self._require_reviewer("recording a review")
        self._reject_bad_rubric(decision, scores, comments)

        payload = {k: int(scores[k]) for k in RUBRIC}
        payload["rubric_version"] = RUBRIC_VERSION

        return self._conn.execute(sa.text("""
            INSERT INTO clinical_reviews
                (case_version_id, reviewer_id, decision, scores, comments)
            VALUES (:version, :reviewer, :decision,
                    CAST(:scores AS jsonb), :comments)
            RETURNING id
        """), {"version": case_version_id, "reviewer": self._user_id(),
               "decision": decision, "scores": json.dumps(payload),
               "comments": comments}).scalar_one()

    def _reject_bad_rubric(self, decision: str, scores: Mapping[str, Any],
                           comments: str | None) -> None:
        """
        The three rules from `UX_SPEC` §12.6, checked where the write happens.
        """
        if decision not in DECISIONS:
            raise RubricViolation(
                f"decision must be one of {DECISIONS}, not {decision!r}")

        missing = [d for d in RUBRIC if d not in scores]
        if missing:
            raise RubricViolation(
                f"every rubric dimension must be scored; missing: {missing}")

        out_of_range = {}
        for dimension in RUBRIC:
            try:
                value = int(scores[dimension])
            except (TypeError, ValueError):
                raise RubricViolation(
                    f"{dimension} must be a whole number 1-5, not "
                    f"{scores[dimension]!r}") from None
            if not 1 <= value <= 5:
                out_of_range[dimension] = value
        if out_of_range:
            raise RubricViolation(
                f"rubric scores run 1-5; out of range: {out_of_range}")

        # The rule that matters. A case nobody would call clinically plausible
        # must not be able to carry an approval that unlocks publication.
        if decision == "approved":
            short = {d: int(scores[d]) for d in RUBRIC
                     if int(scores[d]) < APPROVAL_FLOOR}
            if short:
                named = ", ".join(
                    f"{d.replace('_', ' ')} scored {v}"
                    for d, v in sorted(short.items()))
                raise RubricViolation(
                    f"cannot approve: every dimension must be at least "
                    f"{APPROVAL_FLOOR}. {named}. Record this as "
                    f"'changes_requested' or 'rejected' instead.")

        # An empty rejection tells the author nothing, and the author is a
        # colleague who has to act on it.
        if decision in ("changes_requested", "rejected") and not (
                comments or "").strip():
            raise RubricViolation(
                f"'{decision}' needs a comment saying what must change")
