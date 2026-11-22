#!/usr/bin/env python3
"""
Publish draft cases on a LOCAL database, so a demo can actually start one.

    python scripts/publish_for_demo.py --all
    python scripts/publish_for_demo.py --case chest-pain-gerd --dry-run
    python scripts/publish_for_demo.py --all --undo

## Why this exists

Every case in the bank is a `draft`, and `SelectionRepository.candidates()`
returns only **published** versions — so `POST /v1/sessions` answers
`no_cases_available` (503) and the web app cannot start a consultation. The
test suite does not notice, because its fixtures publish a case themselves.

The real route to publishing is a clinician approving the case in
`/admin/reviews`. That is the product, it is what `REVIEWER_ONBOARDING.md`
describes, and **ten clinician-reviewed cases is the launch gate**. This
script is not that and does not pretend to be: it is the local equivalent of
the fixture, so a laptop demo has something to serve.

## It goes through the gate, not around it

Migration 007's `require_clinical_approval` trigger refuses any flip to
`published` without an approving `clinical_reviews` row, and this script does
not disable it — nothing here touches a trigger, unlike the tempting
`ALTER TABLE ... DISABLE TRIGGER`. It inserts a review the way the console
would, with the full four-dimension rubric at `APPROVAL_FLOOR`, attributed to
a profile whose name says exactly what it is, and then publishes. The gate
still has to say yes.

That means the data afterwards is *honest about itself*: a
`clinical_reviews` row signed "Demo Fixture (not a clinician)" is
distinguishable from a real review by looking, and by
`platform_role = 'reviewer'` on a profile with a reserved UUID.

## The guard that matters

**It refuses to run against anything but a local database.** Publishing a case
on the Supabase project would mark it clinically approved on the database the
real reviewers will use, with a fake review behind it — exactly the record
`REVIEWER_ONBOARDING.md` warns about when it says never to reuse one account
between two reviewers. `--i-know-this-is-not-local` exists only so the refusal
can be tested; using it on the real project is the one thing this file asks
you not to do.

Runs outside `repo_scope`, like `provision_reviewer.py` and
`backfill_pilot.py`: it has to create the fixture reviewer profile, and that
profile is the thing a privileged actor would need to already exist.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import sqlalchemy as sa  # noqa: E402

from nidan.infra.db.engine import get_engine  # noqa: E402
from nidan.infra.db.repositories.reviews import (  # noqa: E402
    APPROVAL_FLOOR,
    RUBRIC,
    RUBRIC_VERSION,
)

# A fixed UUID, so re-running finds the same reviewer instead of accumulating
# one profile per invocation. v5 off a fixed namespace: deterministic, and
# recognisably not a Supabase-issued id.
FIXTURE_REVIEWER = uuid.uuid5(uuid.NAMESPACE_DNS, "demo-fixture.nidan.local")

# The name is the audit trail. Anyone reading `clinical_reviews` later should
# be able to tell this was not a clinician without having to ask.
FIXTURE_NAME = "Demo Fixture (not a clinician)"

REVIEW_COMMENT = (
    "Published by scripts/publish_for_demo.py for a local demo. "
    "NOT a clinical review. Does not count towards the launch gate."
)

# Hosts that are this machine. A socket connection (no host) is local too.
LOCAL_HOSTS = {None, "", "localhost", "127.0.0.1", "::1", "db"}


def is_local(url: sa.engine.URL) -> bool:
    """
    Pure, so the guard that matters most is testable without a Supabase.

    `db` is in the local set because that is the service name inside
    `docker-compose.yml`, where the app reaches Postgres as `db:5432`.
    """
    host = (url.host or "").lower() or None
    return host in LOCAL_HOSTS


def describe(url: sa.engine.URL) -> str:
    """Host and database, never the password."""
    return f"{url.host or 'local socket'}:{url.port or 5432}/{url.database}"


def ensure_fixture_reviewer(conn: sa.Connection) -> None:
    """
    The profile the review is attributed to.

    `clinical_reviews.reviewer_id` references `profiles(id)`, and `profiles.id`
    references `auth.users(id)`, so both rows are needed. The `auth.users`
    insert is guarded the same way `provision_reviewer.py` guards it: only
    against migration 001's three-column local stub, never against the real
    GoTrue table, where writing a row would be forging an account.
    """
    columns = {
        r[0] for r in conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'auth' AND table_name = 'users'"))
    }
    if columns != {"id", "email", "created_at"}:
        raise SystemExit(
            "auth.users is not migration 001's local stub, so this script will "
            "not insert into it.\n"
            f"  found columns: {sorted(columns) or 'table not found'}\n"
            "This is the Supabase-owned table (DATA_MODEL §4.1). Stop.")

    conn.execute(sa.text(
        "INSERT INTO auth.users (id, email) VALUES (:id, :email) "
        "ON CONFLICT (id) DO NOTHING"
    ), {"id": FIXTURE_REVIEWER, "email": "demo-fixture@nidan.local"})

    conn.execute(sa.text("""
        INSERT INTO profiles (id, display_name, platform_role, professional_role,
                              timezone)
        VALUES (:id, :name, 'reviewer', 'physician', 'UTC')
        ON CONFLICT (id) DO UPDATE SET platform_role = 'reviewer'
    """), {"id": FIXTURE_REVIEWER, "name": FIXTURE_NAME})


def targets(conn: sa.Connection, case: str | None, *, published: bool):
    """Draft versions to publish, or fixture-published ones to undo."""
    if published:
        return conn.execute(sa.text("""
            SELECT DISTINCT cv.id, c.slug, cv.version
              FROM case_versions cv
              JOIN cases c             ON c.id = cv.case_id
              JOIN clinical_reviews r  ON r.case_version_id = cv.id
             WHERE cv.status = 'published'
               AND r.reviewer_id = :fixture
               AND (CAST(:case AS text) IS NULL OR c.slug = CAST(:case AS text))
             ORDER BY c.slug
        """), {"fixture": FIXTURE_REVIEWER, "case": case}).mappings().all()

    return conn.execute(sa.text("""
        SELECT cv.id, c.slug, cv.version
          FROM case_versions cv
          JOIN cases c ON c.id = cv.case_id
         WHERE cv.status = 'draft'
           AND (CAST(:case AS text) IS NULL OR c.slug = CAST(:case AS text))
         ORDER BY c.slug
    """), {"case": case}).mappings().all()


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true",
                       help="every draft version")
    group.add_argument("--case", help="one case slug from `cases.slug`, e.g. chest-pain-gerd")
    p.add_argument("--undo", action="store_true",
                   help="put the fixture-published versions back to draft and "
                        "delete the fixture reviews")
    p.add_argument("--dry-run", action="store_true",
                   help="report, change nothing")
    p.add_argument("--i-know-this-is-not-local", action="store_true",
                   help=argparse.SUPPRESS)
    args = p.parse_args()

    engine = get_engine()
    if not is_local(engine.url) and not args.i_know_this_is_not_local:
        print(
            f"REFUSED: {describe(engine.url)} is not a local database.\n\n"
            "This script fabricates a clinical approval. On the Supabase\n"
            "project that would mark a case clinically approved, with a fake\n"
            "review behind it, on the database the real reviewers use.\n\n"
            "A case reaches 'published' there by a clinician approving it in\n"
            "/admin/reviews — see docs/process/REVIEWER_ONBOARDING.md.",
            file=sys.stderr)
        return 2

    print(f"Database: {describe(engine.url)}")
    print(f"Mode:     {'undo' if args.undo else 'publish'}"
          f"{' (dry run)' if args.dry_run else ''}\n")

    scores = {dimension: APPROVAL_FLOOR for dimension in RUBRIC}
    scores["rubric_version"] = RUBRIC_VERSION

    with engine.begin() as conn:
        rows = targets(conn, args.case, published=args.undo)
        if not rows:
            print("Nothing to do."
                  + ("" if args.undo else
                     " No draft versions matched — already published?"))
            return 0

        for row in rows:
            print(f"  {row['slug']}  v{row['version']}")
        print()

        if args.dry_run:
            print(f"{len(rows)} version(s) would be "
                  f"{'returned to draft' if args.undo else 'published'}.")
            return 0

        if args.undo:
            for row in rows:
                # Draft first: deleting the review while the version is still
                # published would leave a published case with no approving
                # review, which is the state migration 007 exists to prevent.
                conn.execute(sa.text(
                    "UPDATE case_versions SET status = 'draft', "
                    "published_at = NULL WHERE id = :id"), {"id": row["id"]})
                conn.execute(sa.text(
                    "DELETE FROM clinical_reviews "
                    "WHERE case_version_id = :id AND reviewer_id = :fixture"),
                    {"id": row["id"], "fixture": FIXTURE_REVIEWER})
            print(f"{len(rows)} version(s) returned to draft.")
            return 0

        ensure_fixture_reviewer(conn)
        for row in rows:
            conn.execute(sa.text("""
                INSERT INTO clinical_reviews (case_version_id, reviewer_id,
                                              decision, scores, comments)
                VALUES (:vid, :rid, 'approved', CAST(:scores AS jsonb), :comment)
            """), {"vid": row["id"], "rid": FIXTURE_REVIEWER,
                   "scores": json.dumps(scores), "comment": REVIEW_COMMENT})
            # The trigger reads the row above. If it were missing this raises
            # "has no approving clinical review" and the whole run rolls back.
            conn.execute(sa.text(
                "UPDATE case_versions SET status = 'published', "
                "published_at = now() WHERE id = :id"), {"id": row["id"]})

        print(f"{len(rows)} version(s) published, each through migration 007's "
              f"gate.\n"
              f"Attributed to {FIXTURE_NAME!r} — these do NOT count towards "
              f"the launch gate.\n\n"
              f"Undo with:  python scripts/publish_for_demo.py "
              f"{'--all' if args.all else f'--case {args.case}'} --undo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
