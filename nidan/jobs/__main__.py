"""
`python -m nidan.jobs run` (BUILD_PLAN T-038).

Processes everything pending and exits. Idempotent, so running it twice is
harmless; see `runner.py` on why that is a property of the queue rather than
something this file arranges.

**Exit codes**, because the thing that schedules this is the only thing
watching it and `cron` reports a non-zero status:

    0   nothing pending, or everything attempted succeeded
    1   at least one step failed — the detail is in the log and in
        `audit_log` as a `job.step_failed` row
    2   bad usage

A step that has failed `MAX_ATTEMPTS` times is **skipped, not failed**, and
does not set a non-zero code: a permanently stuck job would otherwise make
every scheduled run report failure for ever, which is how a monitor gets
switched off. `--status` is how you find those, and `UX_SPEC` S-20's
criterion 5 — "the failure is visible to an admin" — is what it is for.
"""

from __future__ import annotations

import argparse
import logging
import sys

from nidan.config import settings
from nidan.infra.db.repositories import repo_scope
from nidan.infra.db.repositories.audit import MAX_ATTEMPTS, STEPS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m nidan.jobs",
        description="Run the account jobs worker (exports and erasures).")
    parser.add_argument("command", choices=("run", "status"),
                        help="'run' processes pending steps; 'status' lists "
                             "them without doing anything")
    parser.add_argument("--limit", type=int, default=100,
                        help="maximum requests to consider (default 100)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s")

    if args.command == "status":
        return _status(args.limit)

    # Imported here, not at module scope: `status` must work on a machine
    # where the email adapter is misconfigured, because finding that out is
    # exactly what someone runs `status` for.
    from nidan.jobs.runner import run

    print(f"email adapter : {settings.EMAIL_ADAPTER}"
          + ("" if settings.EMAIL_FROM else "   (EMAIL_FROM is not set)"))
    print(f"billing       : {settings.BILLING_PROVIDER}")
    print("supabase key  : "
          + ("set" if settings.SUPABASE_SERVICE_ROLE_KEY else
             "NOT SET — the credential-deletion step cannot run"))
    print()

    report = run(limit=args.limit)
    print(report.summary())
    for line in report.failed:
        print(f"  failed  {line}")
    for line in report.skipped:
        print(f"  stuck   {line}  (>= {MAX_ATTEMPTS} attempts, needs an admin)")
    return 0 if report.ok else 1


def _status(limit: int) -> int:
    """What is outstanding, without attempting any of it."""
    with repo_scope(_actor()) as db:
        jobs = db.audit.pending(limit=limit)
    if not jobs:
        print("Nothing pending.")
        return 0
    print(f"{len(jobs)} request(s) with outstanding steps:\n")
    for job in jobs:
        done = set(job["steps_done"])
        attempts = dict(job["attempts"] or {})
        print(f"  {job['action']}  {job['entity_id']}  "
              f"requested {job['created_at']:%Y-%m-%d %H:%M}Z")
        for step in STEPS[job["action"]]:
            n = attempts.get(step, 0)
            mark = ("done" if step in done
                    else "STUCK" if n >= MAX_ATTEMPTS
                    else "pending")
            print(f"      {mark:<8} {step}"
                  + (f"   ({n} failed attempt(s))" if n else ""))
        print()
    return 0


def _actor():
    from nidan.jobs.runner import ACTOR
    return ACTOR


if __name__ == "__main__":
    sys.exit(main())
