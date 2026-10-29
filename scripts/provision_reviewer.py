#!/usr/bin/env python3
"""
Give an existing account the reviewer (or admin) role.

    python scripts/provision_reviewer.py --uid <uuid> --name "Dr Asha Nair"
    python scripts/provision_reviewer.py --uid <uuid> --name "..." --dry-run

`docs/process/LOCAL_ADMIN_ACCESS.md` §3 does this with a two-statement `psql`
one-liner. That is fine for granting yourself admin once on a laptop. It is the
wrong instrument for onboarding clinicians, for three reasons this script
exists to fix.

**It writes to `auth.users`.** Locally that is harmless -- migration 001
creates a three-column stub because a plain Postgres container has no such
table. On Supabase, GoTrue owns that table and `DATA_MODEL` §4.1 says we never
write to it. Inserting a row there by hand forges an account: a profile with
full reviewer privilege and no password, no email, no confirmation, invisible
in the dashboard's user list. So this script refuses to touch `auth.users`
unless it can prove it is looking at the local stub, and tells you to create
the account in the dashboard instead.

**`ON CONFLICT DO UPDATE SET platform_role` is a silent privilege change.** Run
it against a uid you mistyped and you have either promoted a learner or demoted
an administrator, with no record and no error. Here a role that differs from
the one on the row stops the run and names both values; `--force` proceeds.

**Nothing is recorded.** `UX_SPEC` §12 requires an `audit_log` row for every
admin action, and granting someone the right to approve clinical content is the
most consequential one there is. Every change this script makes writes one.

Bootstrap runs outside `repo_scope`, as `scripts/backfill_pilot.py` does: the
first privileged profile cannot be created by an actor who needs a privileged
profile to exist. That is also why it is a script rather than a console screen.
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

# The stub from migration 001, exactly. Real Supabase `auth.users` carries
# thirty-odd columns; matching on this set is what distinguishes "a local
# container where forging an auth row is the only way in" from "the real
# identity provider, where it would be forgery".
STUB_COLUMNS = {"id", "email", "created_at"}

ROLES = ("reviewer", "admin")
# Ordered, so the refusal below can say which direction the mistake went.
RANK = {"user": 0, "reviewer": 1, "admin": 2}
PROFESSIONAL_ROLES = ("medical_student", "intern", "resident", "physician", "other")


def is_the_local_stub(columns: set[str]) -> bool:
    """
    Pure, so the guard that matters most can be tested without a Supabase.

    Empty means the table was not found at all, which is not a stub and not
    something to write to either.
    """
    return bool(columns) and columns == STUB_COLUMNS


def auth_users_columns(conn: sa.Connection) -> set[str]:
    return {
        r[0] for r in conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'auth' AND table_name = 'users'"))
    }


def describe_target(engine: sa.Engine) -> str:
    """Host and database, never the password. Printed before anything is written."""
    u = engine.url
    return f"{u.host or 'local socket'}:{u.port or 5432}/{u.database}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--uid", required=True,
                   help="the Supabase User UID (Authentication -> Users -> copy)")
    p.add_argument("--name", required=True, help="display name, e.g. 'Dr Asha Nair'")
    p.add_argument("--role", default="reviewer", choices=ROLES)
    p.add_argument("--professional-role", default="physician", choices=PROFESSIONAL_ROLES)
    p.add_argument("--timezone", default="UTC",
                   help="IANA name, e.g. Asia/Kolkata. Only affects how times are shown")
    p.add_argument("--by", default=None,
                   help="uid of the admin doing this, recorded as audit_log.actor_id")
    p.add_argument("--force", action="store_true",
                   help="proceed when this would change an existing role")
    p.add_argument("--create-auth-user", action="store_true",
                   help="local stub only: also insert the auth.users row")
    p.add_argument("--dry-run", action="store_true", help="report, change nothing")
    args = p.parse_args()

    try:
        uid = uuid.UUID(args.uid)
    except ValueError:
        print(f"--uid is not a UUID: {args.uid!r}\n"
              "Copy the User UID from Supabase -> Authentication -> Users.",
              file=sys.stderr)
        return 2

    actor = None
    if args.by:
        try:
            actor = uuid.UUID(args.by)
        except ValueError:
            print(f"--by is not a UUID: {args.by!r}", file=sys.stderr)
            return 2

    engine = get_engine()
    print(f"target   {describe_target(engine)}")
    print(f"uid      {uid}")
    print(f"role     {args.role}")
    if args.dry_run:
        print("mode     dry run -- nothing will be written")
    print()
    # stderr is unbuffered and stdout is not, so without this the refusals
    # below print above the header that says which database they refer to.
    sys.stdout.flush()

    with engine.begin() as conn:
        exists = conn.execute(
            sa.text("SELECT 1 FROM auth.users WHERE id = :id"), {"id": uid}
        ).scalar()

        if not exists:
            if not args.create_auth_user:
                print(
                    f"No auth.users row for {uid}.\n\n"
                    "The account must exist in the identity provider first; this\n"
                    "script only grants a role to one that does. In Supabase:\n"
                    "  Authentication -> Users -> Add user -> Create new user\n"
                    "  tick 'Auto Confirm User', then copy the User UID.\n\n"
                    "On a local container there is no identity provider, so pass\n"
                    "--create-auth-user to insert the stub row as well.",
                    file=sys.stderr)
                return 1
            if not is_the_local_stub(auth_users_columns(conn)):
                print(
                    "--create-auth-user refused: this auth.users is not the local\n"
                    "stub from migration 001, so it is the real identity provider.\n"
                    "Writing a row there would create an account that has privilege\n"
                    "but no credentials and does not appear in the dashboard.\n"
                    "Create the user in Supabase and run this again without the flag.",
                    file=sys.stderr)
                return 1
            print(f"auth.users  + stub row for {uid}")
            if not args.dry_run:
                conn.execute(sa.text("INSERT INTO auth.users (id) VALUES (:id)"),
                             {"id": uid})

        row = conn.execute(sa.text(
            "SELECT display_name, platform_role::text, deleted_at "
            "FROM profiles WHERE id = :id"), {"id": uid}).one_or_none()

        if row is not None and row.deleted_at is not None:
            print(f"Profile {uid} is soft-deleted (deleted_at = {row.deleted_at}).\n"
                  "Reviving it would restore whatever else the account carries.\n"
                  "Decide that deliberately rather than as a side effect of this.",
                  file=sys.stderr)
            return 1

        was = row.platform_role if row else None
        if was is not None and was != args.role and not args.force:
            print(f"Profile {uid} already exists with platform_role = {was!r}, and\n"
                  f"this would change it to {args.role!r}.\n\n"
                  f"If the uid is right and the change is intended, pass --force.\n"
                  f"If it is a typo, you have just been saved a silent "
                  f"{'promotion' if RANK[args.role] > RANK[was] else 'demotion'}.",
                  file=sys.stderr)
            return 1

        if row is not None and was == args.role and row.display_name == args.name:
            print(f"unchanged   {args.name} is already {args.role}")
            return 0

        action = "profile.created" if row is None else "profile.role_granted"
        print(f"profiles    {'+' if row is None else '~'} {args.name} -> {args.role}"
              + (f"  (was {was})" if was and was != args.role else ""))

        if args.dry_run:
            print("\nnothing written")
            return 0

        conn.execute(sa.text("""
            INSERT INTO profiles (id, display_name, platform_role,
                                  professional_role, timezone)
            VALUES (:id, :name, :role, :prof, :tz)
            ON CONFLICT (id) DO UPDATE
               SET display_name  = EXCLUDED.display_name,
                   platform_role = EXCLUDED.platform_role
        """), {"id": uid, "name": args.name, "role": args.role,
               "prof": args.professional_role, "tz": args.timezone})

        conn.execute(sa.text("""
            INSERT INTO audit_log (actor_id, action, entity_type, entity_id,
                                   reason, metadata)
            VALUES (:actor, :action, 'profile', :id, :reason, CAST(:meta AS jsonb))
        """), {
            "actor": actor,
            "action": action,
            "id": uid,
            "reason": "clinical reviewer onboarding",
            "meta": json.dumps({
                "from": was,
                "to": args.role,
                "display_name": args.name,
                "tool": "scripts/provision_reviewer.py",
                "forced": bool(args.force),
            }),
        })

    print("\ndone. The account can now reach /admin; reviewers see only the "
          "review queue.")
    if actor is None:
        print("note: no --by given, so audit_log.actor_id is NULL -- the row "
              "records what was done but not by whom.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
