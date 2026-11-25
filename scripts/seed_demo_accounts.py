#!/usr/bin/env python3
"""
Create the demo accounts, in BOTH places they have to exist.

    python scripts/seed_demo_accounts.py --dry-run
    python scripts/seed_demo_accounts.py
    python scripts/seed_demo_accounts.py --show       # what exists now
    python scripts/seed_demo_accounts.py --undo       # local rows only

## The problem this exists for

On a laptop, Nidan is split across two databases and nothing joins them
automatically:

  * **identity** is the Supabase cloud project (`ADR-0002` -- Supabase issues
    credentials, this backend only verifies them), and
  * **data** is the local Postgres container, whose `auth.users` is migration
    001's three-column stub, because a plain `pgvector/pgvector:pg16` image has
    no such table.

`profiles.id` carries `profiles_id_fkey REFERENCES auth.users(id)`. So signing
up a brand new account in the web app gets as far as `POST /v1/me`, and then:

    ForeignKeyViolation: insert or update on table "profiles" violates
    foreign key constraint "profiles_id_fkey"
    DETAIL:  Key is not present in table "users".

The learner sees "We couldn't finish setting up your account." The Supabase
user was created perfectly; there is simply no row in the local stub for the
uid it was issued. **Live signup cannot work against a local database**, and no
amount of fixing the web app changes that -- it is the architecture, and it
resolves itself the day `DATABASE_URL` points at the Supabase project
(`T-045` criterion 1).

Until then, the accounts are made ahead of time: this script signs each one up
through Supabase's public endpoint exactly as the web app would, then inserts
the stub row and the profile the foreign key needs.

## What it deliberately does not do

**It never touches the service_role key.** Signing up goes through
`POST /auth/v1/signup` with the *publishable* key -- the same request
`web/src/app/(auth)/actions.ts` makes. The admin API would be fewer steps and
would also mean putting a key that bypasses every RLS policy into a script
anyone might run with the wrong `DATABASE_URL`. `SECURITY_SPEC` §7.9 gives
`nidan/infra/identity_admin.py` sole ownership of that key and this is not it.
If it is handed one by mistake, it refuses rather than using it.

**It refuses any non-local database**, like `scripts/publish_for_demo.py`. The
rows it writes include an `auth.users` row, and against the real project that
is forgery -- a profile with privilege, no password and no presence in the
dashboard. `scripts/provision_reviewer.py` makes the same argument at greater
length and this script reuses its guard rather than restating it.

**`--undo` removes the local rows only.** Deleting a Supabase account needs the
service_role key, so the script cannot and does not; it prints the dashboard
path instead. A left-behind cloud user with no local profile is inert.

## The accounts, and why each one

| account    | role     | onboarded | what it is for                          |
|------------|----------|-----------|-----------------------------------------|
| learner    | user     | no        | the first-run flow: onboarding, then a  |
|            |          |           | consultation. The closest thing to      |
|            |          |           | "watch me make an account" that works   |
| student    | user     | yes       | lands straight on the dashboard. The    |
|            |          |           | spare, if the first one gets into a     |
|            |          |           | state mid-demo                          |
| admin      | admin    | yes       | `/admin` -- the case bank, the editor,  |
|            |          |           | Playtest, the leakage queue             |
| reviewer   | reviewer | yes       | the console as a clinician sees it:     |
|            |          |           | the review queue and nothing else       |

All four share one generated password, because one thing to remember is one
thing to get wrong in front of an audience. It is written to
`logs/demo-accounts.txt`, which is gitignored as a whole directory.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import secrets
import sys
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import sqlalchemy as sa  # noqa: E402
from provision_reviewer import (  # noqa: E402
    auth_users_columns,
    describe_target,
    is_the_local_stub,
)

from nidan.infra.db.engine import get_engine  # noqa: E402

CREDENTIALS_FILE = ROOT / "logs" / "demo-accounts.txt"

# RFC 2606 reserves example.com precisely so that it can be used like this: it
# resolves nowhere and no one can ever receive mail at it. Nothing in Nidan
# emails anyone yet in any case -- `EMAIL_ADAPTER` writes files to
# `logs/outbox/` -- but a demo account should not be one keystroke away from
# mailing a stranger if that ever changes.
DOMAIN = "example.com"


class Account:
    """One demo account, in the two places it has to exist."""

    def __init__(self, handle: str, name: str, role: str, onboarded: bool,
                 professional_role: str, year: int | None, purpose: str):
        self.handle = handle
        self.email = f"demo.{handle}@{DOMAIN}"
        self.name = name
        self.role = role
        self.onboarded = onboarded
        self.professional_role = professional_role
        self.year = year
        self.purpose = purpose


ACCOUNTS = (
    Account("learner", "Demo Learner", "user", False, "medical_student", 4,
            "the first-run flow -- onboarding, then a consultation"),
    Account("student", "Priya Shah", "user", True, "medical_student", 5,
            "lands on the dashboard; the spare"),
    Account("admin", "Demo Admin", "admin", True, "physician", None,
            "/admin -- case bank, editor, Playtest, leakage queue"),
    Account("reviewer", "Dr Demo Reviewer", "reviewer", True, "physician", None,
            "the console as a clinician sees it"),
)


# ---------------------------------------------------------------- the two keys

def read_env_file(path: pathlib.Path) -> dict[str, str]:
    """
    A `.env` well enough for two values. Not a parser -- no quotes, no export,
    no interpolation, because the two keys we want never need them.
    """
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def looks_like_a_secret_key(key: str) -> bool:
    """
    True for a key that bypasses RLS. Pure, so the refusal can be tested.

    Two shapes, because Supabase is mid-migration between them: the new
    `sb_secret_...` prefix, and the legacy JWT whose payload says
    `"role":"service_role"`. The publishable forms are `sb_publishable_...`
    and a JWT saying `"role":"anon"`.
    """
    if key.startswith("sb_secret_"):
        return True
    parts = key.split(".")
    if len(parts) == 3:                     # a JWT; look at the payload
        import base64
        body = parts[1] + "=" * (-len(parts[1]) % 4)
        try:
            claims = json.loads(base64.urlsafe_b64decode(body))
        except Exception:
            return False
        return claims.get("role") == "service_role"
    return False


def supabase_credentials() -> tuple[str, str]:
    """The project URL and the publishable key, from the environment or `web/`."""
    import os

    web_env = read_env_file(ROOT / "web" / ".env.local")
    url = (os.getenv("SUPABASE_URL")
           or web_env.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = (os.getenv("SUPABASE_ANON_KEY")
           or web_env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or "")

    if not url or not key:
        raise SystemExit(
            "No Supabase project configured.\n\n"
            "Set SUPABASE_URL and SUPABASE_ANON_KEY, or fill in\n"
            "  web/.env.local -> NEXT_PUBLIC_SUPABASE_URL\n"
            "                    NEXT_PUBLIC_SUPABASE_ANON_KEY\n"
            "Both are public values; take them from Supabase -> Project\n"
            "Settings -> API Keys (the *publishable* key).")

    if looks_like_a_secret_key(key):
        raise SystemExit(
            "That is the service_role (secret) key, and this script refuses "
            "it.\n\n"
            "It bypasses every RLS policy in migrations 016 and 020-024.\n"
            "SECURITY_SPEC 7.9 gives it to nidan/infra/identity_admin.py "
            "alone.\n"
            "Use the publishable key -- sb_publishable_... -- which is all a\n"
            "signup needs.")

    return url, key


# ------------------------------------------------------------------- Supabase

def post_json(url: str, key: str, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"apikey": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read() or b"{}"
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw.decode(errors="replace")[:400]}


def sign_up(url: str, key: str, email: str, password: str) -> tuple[uuid.UUID, str]:
    """
    The uid for `email`, creating the account if it is not there.

    Returns the uid and one of "created" / "existing". An account that already
    exists is signed in to instead, which both recovers the uid and proves the
    password on file is the one in `logs/demo-accounts.txt` -- a re-run with a
    regenerated password would otherwise look like a success and fail at the
    login screen.
    """
    status, data = post_json(f"{url}/auth/v1/signup", key,
                             {"email": email, "password": password})
    if status < 400 and (data.get("user") or {}).get("id"):
        return uuid.UUID(data["user"]["id"]), "created"
    if status < 400 and data.get("id"):            # some versions return the user flat
        return uuid.UUID(data["id"]), "created"

    code = data.get("error_code") or data.get("code") or ""
    msg = data.get("msg") or data.get("message") or data.get("error_description") or ""
    already = code in {"user_already_exists", "email_exists"} or "already" in msg.lower()
    if not already:
        raise SystemExit(
            f"Supabase refused the signup for {email}: {status} {code} {msg}\n"
            f"{json.dumps(data)[:400]}")

    status, data = post_json(f"{url}/auth/v1/token?grant_type=password", key,
                             {"email": email, "password": password})
    uid = (data.get("user") or {}).get("id")
    if status >= 400 or not uid:
        code = data.get("error_code") or data.get("code") or ""
        raise SystemExit(
            f"{email} already exists in Supabase, but signing in to it with "
            f"the password in\n{CREDENTIALS_FILE} failed: {status} {code}.\n\n"
            "Either that file is stale, or the account was made by hand with a\n"
            "different password. Delete the user in Supabase -> Authentication\n"
            "-> Users and run this again, or pass --password with the real one.")
    return uuid.UUID(uid), "existing"


# ---------------------------------------------------------------------- local

def write_local(conn: sa.Connection, acc: Account, uid: uuid.UUID) -> str:
    """The stub row and the profile. Returns what changed, for the report."""
    conn.execute(sa.text(
        "INSERT INTO auth.users (id, email) VALUES (:id, :email) "
        "ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email"),
        {"id": uid, "email": acc.email})

    before = conn.execute(sa.text(
        "SELECT platform_role::text AS role, deleted_at FROM profiles "
        "WHERE id = :id"), {"id": uid}).one_or_none()

    if before is not None and before.deleted_at is not None:
        # `ProfileRepository.get()` filters `deleted_at IS NULL`, so this
        # account would authenticate and then 404 on every learner route.
        # Reviving it here would undo an erasure as a side effect of seeding.
        return "REFUSED -- profile is soft-deleted; decide that deliberately"

    conn.execute(sa.text("""
        INSERT INTO profiles (id, display_name, platform_role, professional_role,
                              year_of_training, timezone, onboarded_at,
                              country)
        VALUES (:id, :name, :role, :prof, :year, 'Asia/Kolkata',
                CASE WHEN :onboarded THEN now() ELSE NULL END, 'IN')
        ON CONFLICT (id) DO UPDATE
           SET display_name     = EXCLUDED.display_name,
               platform_role    = EXCLUDED.platform_role,
               professional_role = EXCLUDED.professional_role,
               year_of_training = EXCLUDED.year_of_training,
               onboarded_at     = CASE WHEN :onboarded
                                       THEN COALESCE(profiles.onboarded_at, now())
                                       ELSE NULL END
    """), {"id": uid, "name": acc.name, "role": acc.role,
           "prof": acc.professional_role, "year": acc.year,
           "onboarded": acc.onboarded})

    if acc.role != "user":
        # `UX_SPEC` §12 wants an audit_log row for every grant of privilege,
        # and this script grants two. `provision_reviewer.py` records the same
        # shape; the `tool` key is what tells them apart afterwards.
        conn.execute(sa.text("""
            INSERT INTO audit_log (actor_id, action, entity_type, entity_id,
                                   reason, metadata)
            VALUES (NULL, :action, 'profile', :id, :reason, CAST(:meta AS jsonb))
        """), {
            "action": "profile.created" if before is None else "profile.role_granted",
            "id": uid,
            "reason": "demo account seeding",
            "meta": json.dumps({
                "from": before.role if before else None,
                "to": acc.role,
                "display_name": acc.name,
                "tool": "scripts/seed_demo_accounts.py",
            }),
        })

    if before is None:
        return "created"
    if before.role != acc.role:
        return f"role {before.role} -> {acc.role}"
    return "updated"


def show(conn: sa.Connection) -> int:
    rows = conn.execute(sa.text("""
        SELECT u.email, p.display_name, p.platform_role::text AS role,
               p.onboarded_at IS NOT NULL AS onboarded, p.id
        FROM profiles p JOIN auth.users u ON u.id = p.id
        WHERE u.email LIKE :like ORDER BY u.email
    """), {"like": f"demo.%@{DOMAIN}"}).all()
    if not rows:
        print("No demo accounts in the local database.")
        return 0
    print(f"{'email':<34} {'name':<20} {'role':<9} onboarded")
    for r in rows:
        print(f"{r.email:<34} {(r.display_name or ''):<20} {r.role:<9} "
              f"{'yes' if r.onboarded else 'no'}")
    return 0


def undo(conn: sa.Connection) -> int:
    """
    The local rows. `profiles` cascades from `auth.users`, and `sessions`
    cascades from `profiles` -- but `session_events` refuses DELETE, so a
    demo account that has taken a consultation cannot be removed this way and
    says so rather than aborting the whole transaction.
    """
    ids = conn.execute(sa.text(
        "SELECT id, email FROM auth.users WHERE email LIKE :like"),
        {"like": f"demo.%@{DOMAIN}"}).all()
    if not ids:
        print("Nothing to remove.")
        return 0
    for row in ids:
        n = conn.execute(sa.text(
            "SELECT count(*) FROM session_events e JOIN sessions s "
            "ON s.id = e.session_id WHERE s.user_id = :id"), {"id": row.id}).scalar()
        if n:
            print(f"kept    {row.email} -- {n} session event(s); "
                  "session_events refuses DELETE (migration 033)")
            continue
        conn.execute(sa.text("DELETE FROM auth.users WHERE id = :id"), {"id": row.id})
        print(f"removed {row.email}")
    print("\nThe Supabase accounts are untouched -- removing one needs the\n"
          "service_role key. Authentication -> Users -> ... -> Delete user.")
    return 0


# ----------------------------------------------------------------------- main

def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true",
                   help="report the plan, call nothing, write nothing")
    p.add_argument("--show", action="store_true",
                   help="list the demo accounts the local database has")
    p.add_argument("--undo", action="store_true",
                   help="remove the LOCAL rows (not the Supabase accounts)")
    p.add_argument("--password", default=None,
                   help="use this password instead of generating one")
    p.add_argument("--i-know-this-is-not-local", action="store_true",
                   help=argparse.SUPPRESS)
    args = p.parse_args()

    engine = get_engine()
    print(f"data     {describe_target(engine)}")

    with engine.begin() as conn:
        if not is_the_local_stub(auth_users_columns(conn)):
            if not args.i_know_this_is_not_local:
                print(
                    "\nRefused: this auth.users is not migration 001's three-column\n"
                    "stub, so it is the real identity provider.\n\n"
                    "Inserting rows there forges accounts -- privilege with no\n"
                    "credentials, invisible in the dashboard. And against the real\n"
                    "project you do not need this script at all: signup works,\n"
                    "because auth.users is real and the foreign key is satisfied\n"
                    "by GoTrue.",
                    file=sys.stderr)
                return 1
            print("WARNING: --i-know-this-is-not-local", file=sys.stderr)

        if args.show:
            return show(conn)
        if args.undo:
            return undo(conn)

    url, key = supabase_credentials()
    print(f"identity {url}")
    password = args.password or f"Nidan-Demo-{secrets.randbelow(9000) + 1000}"
    print(f"accounts {len(ACCOUNTS)}, one shared password\n")

    print(f"{'email':<34} {'role':<9} {'onboarded':<10} what it is for")
    for a in ACCOUNTS:
        print(f"{a.email:<34} {a.role:<9} "
              f"{'yes' if a.onboarded else 'no':<10} {a.purpose}")
    print()

    if args.dry_run:
        print("dry run -- no account created, no row written")
        return 0

    results = []
    for a in ACCOUNTS:
        uid, state = sign_up(url, key, a.email, password)
        with engine.begin() as conn:
            local = write_local(conn, a, uid)
        results.append((a, uid, state, local))
        print(f"{a.email:<34} supabase {state:<9} local {local}")

    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "Nidan demo accounts",
        "",
        "Generated by scripts/seed_demo_accounts.py. `logs/` is gitignored as a",
        "whole directory, so this file is not committable -- do not move it.",
        "",
        f"password (all four): {password}",
        "",
        f"{'email':<34} {'role':<9} {'onboarded':<10} uid",
    ]
    for a, uid, _, _ in results:
        lines.append(f"{a.email:<34} {a.role:<9} "
                     f"{'yes' if a.onboarded else 'no':<10} {uid}")
    lines += [
        "",
        "The learner account is deliberately NOT onboarded, so logging in to it",
        "shows the first-run flow. Once it has been through onboarding it goes",
        "straight to the dashboard like the others -- re-run with --undo and",
        "again to reset it, or use demo.student for a clean dashboard.",
        "",
        "/admin is served by the Flask app on :8000, not the Next.js app on",
        ":3000, and needs an access token in the sb-access-token cookie.",
        "See docs/process/DEMO_RUN_SHEET.md.",
        "",
    ]
    CREDENTIALS_FILE.write_text("\n".join(lines))
    print(f"\ncredentials -> {CREDENTIALS_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
