"""
Configuration every test application is built with.

One module rather than a constant per test file. `tests/db/test_routes.py` had
the first one and T-030's `tests/db/test_v1_reads.py` invented a second, which
the secret scan then flagged — correctly, in the sense that an arbitrary
high-entropy string is indistinguishable from a credential, and a scanner that
tried to tell them apart would be the wrong kind of clever.

Allowlisting it would have been the wrong fix twice over. `.gitleaks.toml` is
an allowlist of values *deliberately* shaped like credentials — fixtures for
the redaction tests, a Stripe key from Stripe's own documentation — and this is
not one of those. More to the point, a second arbitrary signing key was
duplication before it was a finding.
"""

from __future__ import annotations

from typing import Final

# Every application these tests build signs its session cookies with this.
#
# It is passed as config rather than set as an environment variable, and that
# distinction is what CI caught: `settings` is a module-level singleton read at
# import, so `monkeypatch.setenv` after import changes nothing. Locally the key
# came from a developer's `.env` and the tests passed; on a runner with no
# `.env` each `create_app` fell back to `os.urandom(24)`, so the second
# application could not read the first one's cookie.
#
# The same fallback is a real hazard in production now that T-013 raised the
# worker count — gunicorn imports the app separately per worker — which is why
# `config.py` refuses to start a production environment without a key.
TEST_SECRET: Final = "t013-tests-fixed-secret"

# Every table that hangs off `sessions`, in an order TRUNCATE accepts.
#
# TRUNCATE refuses a table referenced by a foreign key unless every referring
# table is in the same statement, so this is a set rather than a preference —
# naming five of the six gets "cannot truncate a table referenced in a foreign
# key constraint", which reads like a permissions problem.
#
# TRUNCATE and not DELETE, because `session_events` carries migration 010's
# `session_events_append_only` trigger and refuses a DELETE by design.
# TRUNCATE bypasses row triggers, which is what a teardown wants and what
# application code must never be able to do.
#
# Here rather than inline in a fixture because two fixtures need it and a
# second copy would drift: the symptom is a teardown error in an unrelated
# test, which is a bad way to learn about a list.
SESSION_TABLES: Final = (
    "session_events", "session_results", "feedback_texts",
    "llm_calls", "leakage_flags", "sessions",
)

TRUNCATE_SESSION_TABLES: Final = "TRUNCATE " + ", ".join(SESSION_TABLES)


# Every module that does `from ... import call_llm`.
#
# `call_llm` is imported by name, so each importing module holds its own
# reference and patching `gateway.call_llm` alone changes none of them. The
# `fake_llm` fixture patches each site explicitly, and
# `tests/test_no_network.py` fails if a module starts importing `call_llm`
# without being added here.
#
# **That guard used to hold its own copy of this list**, which is the bug it
# exists to prevent, one level up: adding a site to conftest and not to the
# test produced "module imports call_llm but conftest does not patch it" about
# a module conftest *did* patch. Both now read this.
LLM_IMPORT_SITES: Final = (
    "nidan.infra.feedback",
    "nidan.api.routes",
    "nidan.api.v1.consultation",
)


def llm_patch_targets() -> tuple[str, ...]:
    """What `monkeypatch.setattr` wants: `module.call_llm`."""
    return tuple(f"{module}.call_llm" for module in LLM_IMPORT_SITES)


def llm_source_paths() -> frozenset[str]:
    """What a filesystem sweep sees: posix paths relative to the repo root."""
    return frozenset(module.replace(".", "/") + ".py"
                     for module in LLM_IMPORT_SITES)
