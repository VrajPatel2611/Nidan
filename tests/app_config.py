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
