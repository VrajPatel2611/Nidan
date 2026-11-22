"""
Background work that is not a request (BUILD_PLAN T-038).

One entry point — `python -m nidan.jobs run` — which processes everything
pending and exits. See `runner.py` for why the queue is shaped the way it is,
and `COMMANDS.md` for how to schedule it.

**Not a thread inside the API.** The app runs on two gunicorn workers, so an
in-process scheduler would be two schedulers racing for the same jobs, and
nothing in `audit_log` can be claimed. It would also put the Supabase
`service_role` key — which bypasses RLS entirely — into the environment of the
process that serves public requests.
"""

from __future__ import annotations
