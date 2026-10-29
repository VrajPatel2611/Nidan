"""
`scripts/provision_reviewer.py` -- granting a clinician the reviewer role.

The script exists because the `psql` one-liner it replaces could do three
things silently: forge an `auth.users` row on real Supabase, change an
existing account's privilege, and leave no record of either. Those are the
three behaviours worth a test, and the first is worth one even though no test
here can reach a Supabase -- it is checked against the column list a real one
has, because the whole point is what the script does when it is NOT looking at
the local stub.
"""

from __future__ import annotations

import pathlib
import sys
import uuid

import pytest
import sqlalchemy as sa

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from scripts.provision_reviewer import is_the_local_stub, main  # noqa: E402

# A subset of what GoTrue's auth.users actually carries. Enough to be clearly
# not the three-column stub from migration 001.
REAL_SUPABASE_COLUMNS = {
    "id", "email", "created_at", "instance_id", "aud", "role",
    "encrypted_password", "email_confirmed_at", "invited_at",
    "confirmation_token", "recovery_token", "last_sign_in_at",
    "raw_app_meta_data", "raw_user_meta_data", "is_super_admin",
    "updated_at", "phone", "banned_until", "deleted_at",
}


def run(*argv: str) -> int:
    """The script as the operator runs it, minus the process boundary."""
    saved = sys.argv
    sys.argv = ["provision_reviewer.py", *argv]
    try:
        return main()
    except SystemExit as exc:            # argparse errors
        return int(exc.code or 0)
    finally:
        sys.argv = saved


@pytest.fixture
def uid() -> uuid.UUID:
    return uuid.uuid4()


def profile(admin: sa.Engine, uid: uuid.UUID):
    with admin.connect() as c:
        return c.execute(sa.text(
            "SELECT display_name, platform_role::text, professional_role::text "
            "FROM profiles WHERE id = :id"), {"id": uid}).one_or_none()


def audit_rows(admin: sa.Engine, uid: uuid.UUID) -> list:
    with admin.connect() as c:
        return list(c.execute(sa.text(
            "SELECT action, metadata FROM audit_log "
            "WHERE entity_type = 'profile' AND entity_id = :id ORDER BY id"),
            {"id": uid}))


# ── the guard that cannot be reached from a test container ───────────

def test_the_real_supabase_users_table_is_not_the_stub():
    """
    The refusal this protects is the serious one.

    Inserting into a real `auth.users` creates an account with reviewer
    privilege, no password and no dashboard entry -- indistinguishable from a
    legitimate one afterwards, and `DATA_MODEL` §4.1 says the table is
    Supabase's to write. No test here has a Supabase to point at, so the
    discrimination is tested against its column list instead.
    """
    assert not is_the_local_stub(REAL_SUPABASE_COLUMNS)


def test_the_migration_001_stub_is_the_stub():
    assert is_the_local_stub({"id", "email", "created_at"})


def test_a_missing_table_is_not_a_stub():
    """An empty column set means `auth.users` was not found, not that it is safe."""
    assert not is_the_local_stub(set())


# ── behaviour against the real schema ────────────────────────────────

def test_an_unknown_account_is_refused_rather_than_invented(app_db, uid, capsys):
    """
    Without an identity provider there is no account, and the script says so
    instead of producing a profile that can never sign in.
    """
    assert run("--uid", str(uid), "--name", "Dr Asha Nair") == 1
    assert profile(app_db, uid) is None
    assert "Authentication -> Users" in capsys.readouterr().err


def test_granting_the_role_writes_the_profile_and_the_audit_row(app_db, uid):
    assert run("--uid", str(uid), "--name", "Dr Asha Nair",
               "--create-auth-user", "--timezone", "Asia/Kolkata") == 0

    row = profile(app_db, uid)
    assert row.display_name == "Dr Asha Nair"
    assert row.platform_role == "reviewer"
    assert row.professional_role == "physician"

    (entry,) = audit_rows(app_db, uid)
    assert entry.action == "profile.created"
    assert entry.metadata["to"] == "reviewer"
    assert entry.metadata["from"] is None


def test_a_dry_run_writes_nothing(app_db, uid):
    assert run("--uid", str(uid), "--name", "Dr Asha Nair",
               "--create-auth-user", "--dry-run") == 0
    assert profile(app_db, uid) is None
    assert audit_rows(app_db, uid) == []


def test_running_it_twice_changes_nothing_and_logs_once(app_db, uid):
    """
    Onboarding is the kind of thing that gets re-run from shell history. A
    second audit row would make the log read as two separate grants.
    """
    run("--uid", str(uid), "--name", "Dr Asha Nair", "--create-auth-user")
    assert run("--uid", str(uid), "--name", "Dr Asha Nair") == 0
    assert len(audit_rows(app_db, uid)) == 1


def test_a_role_change_needs_force(app_db, uid, capsys):
    """
    The mistyped-uid case. `ON CONFLICT DO UPDATE SET platform_role` would
    promote or demote whoever that id belongs to, and report success.
    """
    run("--uid", str(uid), "--name", "Dr Asha Nair", "--create-auth-user")

    assert run("--uid", str(uid), "--name", "Dr Asha Nair", "--role", "admin") == 1
    assert profile(app_db, uid).platform_role == "reviewer"
    assert "--force" in capsys.readouterr().err


def test_force_changes_the_role_and_records_both_ends(app_db, uid):
    run("--uid", str(uid), "--name", "Dr Asha Nair", "--create-auth-user")

    assert run("--uid", str(uid), "--name", "Dr Asha Nair",
               "--role", "admin", "--force") == 0
    assert profile(app_db, uid).platform_role == "admin"

    last = audit_rows(app_db, uid)[-1]
    assert last.metadata["from"] == "reviewer"
    assert last.metadata["to"] == "admin"
    assert last.metadata["forced"] is True


def test_a_soft_deleted_profile_is_not_quietly_revived(app_db, uid, capsys):
    """
    `DATA_MODEL` §10.2 soft-deletes profiles. Re-granting a role would restore
    the account's sessions and history as a side effect of an onboarding step.
    """
    run("--uid", str(uid), "--name", "Dr Asha Nair", "--create-auth-user")
    with app_db.begin() as c:
        c.execute(sa.text("UPDATE profiles SET deleted_at = now() WHERE id = :id"),
                  {"id": uid})

    assert run("--uid", str(uid), "--name", "Dr Asha Nair") == 1
    assert "soft-deleted" in capsys.readouterr().err


def test_the_actor_is_recorded_when_given(app_db, uid):
    """
    `UX_SPEC` §12 wants an actor on every admin action. Bootstrap cannot always
    have one -- the first admin predates every profile -- so it is optional,
    and the script says so when it is missing.
    """
    admin_uid = uuid.uuid4()
    run("--uid", str(admin_uid), "--name", "Vraj", "--role", "admin",
        "--create-auth-user")

    assert run("--uid", str(uid), "--name", "Dr Asha Nair",
               "--create-auth-user", "--by", str(admin_uid)) == 0
    with app_db.connect() as c:
        actor = c.execute(sa.text(
            "SELECT actor_id FROM audit_log WHERE entity_id = :id"),
            {"id": uid}).scalar()
    assert actor == admin_uid


def test_a_malformed_uid_is_rejected_before_any_connection(uid, capsys):
    """No `app_db`: the check must happen before the engine is touched."""
    assert run("--uid", "not-a-uuid", "--name", "Dr Asha Nair") == 2
    assert "not a UUID" in capsys.readouterr().err
