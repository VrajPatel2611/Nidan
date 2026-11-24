"""
The Supabase admin client (T-038).

No network: `urllib.request.urlopen` is replaced. What is being tested is the
error policy and the key handling, and both are decided before any socket
opens.

**The key tests are the point of this file.** This module is the only place in
the codebase that uses `SUPABASE_SERVICE_ROLE_KEY`, which bypasses RLS
entirely — so every guarantee in `ADR-0016` is void for anything holding it.
If it leaks into an exception message, a log line or an `audit_log` row, it
leaks into somewhere that is kept.
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import patch
from uuid import uuid4

import pytest

from nidan.infra import identity_admin
from nidan.infra.identity_admin import (
    CredentialDeletionFailed,
    NotConfigured,
    delete_credential,
    fetch_email,
)

KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.SERVICE_ROLE_SECRET.signature"
URL = "https://abcdefgh.supabase.co"
USER = uuid4()


class _Response(io.BytesIO):
    """Enough of http.client.HTTPResponse for a context manager."""

    def __init__(self, body: bytes = b"", status: int = 200):
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _configured(**overrides):
    """Patch settings as the worker's environment would set them."""
    values = {"SUPABASE_URL": URL,
              "SUPABASE_SERVICE_ROLE_KEY": KEY, **overrides}
    return patch.multiple(identity_admin.settings, **values)


def _http(result):
    """`urlopen` returning a response, or raising."""
    side = (lambda *a, **k: (_ for _ in ()).throw(result)) \
        if isinstance(result, Exception) else (lambda *a, **k: result)
    return patch.object(identity_admin.urllib.request, "urlopen", side)


def _error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, code, "nope", {}, None)


# ── the key never leaks ─────────────────────────────────────────────────

@pytest.mark.parametrize("failure", [
    _error(500), _error(401), _error(403), _error(418),
    urllib.error.URLError("getaddrinfo failed"),
    TimeoutError(),
])
def test_the_service_role_key_is_in_no_error_message(failure):
    """
    Every failure path, not a sample of them.

    An exception message is logged, may be reported to Sentry, and on a
    `job.step_failed` row is written into `audit_log` — which refuses UPDATE
    and survives the erasure. A key in one would outlive the account it was
    used to delete.
    """
    with _configured(), _http(failure):
        with pytest.raises((CredentialDeletionFailed, NotConfigured)) as exc:
            delete_credential(USER)
    assert KEY not in str(exc.value)
    assert "SERVICE_ROLE_SECRET" not in str(exc.value)


def test_the_key_is_sent_as_both_bearer_and_apikey_and_not_in_the_url():
    """
    GoTrue wants both headers. The URL matters because a URL is what gets
    logged by proxies, written to access logs and included in error reports —
    `SECURITY_SPEC` and the privacy rules both say a secret never goes in a
    query string.
    """
    captured = {}

    def _capture(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        return _Response(b"", 200)

    with _configured(), patch.object(identity_admin.urllib.request,
                                     "urlopen", _capture):
        delete_credential(USER)

    assert KEY not in captured["url"]
    assert str(USER) in captured["url"]
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers["authorization"] == f"Bearer {KEY}"
    assert headers["apikey"] == KEY


def test_the_returned_value_carries_no_key():
    """`Deletion` goes into an audit row verbatim."""
    with _configured(), _http(_Response(b"", 200)):
        result = delete_credential(USER)
    assert KEY not in repr(result)


# ── configuration ───────────────────────────────────────────────────────

def test_an_absent_key_refuses_rather_than_succeeding():
    """
    The whole point of `NotConfigured`. A worker that recorded
    `erasure.credential_deleted` because there was no key to try would make
    S-20's "removed within 24 h" permanently and silently false.
    """
    with _configured(SUPABASE_SERVICE_ROLE_KEY=""):
        with pytest.raises(NotConfigured):
            delete_credential(USER)


def test_an_absent_project_url_refuses_too():
    with _configured(SUPABASE_URL=""):
        with pytest.raises(NotConfigured):
            delete_credential(USER)


def test_not_configured_is_not_a_deletion_failure():
    """
    Distinct types because the worker responds differently: a failed call is
    retried, an absent key cannot succeed on a retry and must stop being
    tried. `runner.py` maps the first to `StepFailed` and the second to
    `StepImpossible`.
    """
    assert not issubclass(NotConfigured, CredentialDeletionFailed)


def test_the_message_does_not_blame_the_erasure_when_it_was_an_export():
    """
    Both callers share `_admin`, and an earlier version described the
    erasure's half-done state in the shared message — so someone whose
    *export* had not been emailed was told their credential was still live.
    True about the wrong thing, in the error they would act on.
    """
    with _configured(SUPABASE_SERVICE_ROLE_KEY=""):
        with pytest.raises(NotConfigured) as exc:
            fetch_email(USER)
    assert "credential is not deleted" not in str(exc.value)


# ── idempotency: 404 is the goal state ──────────────────────────────────

def test_a_404_on_delete_is_success_not_failure():
    """
    T-038 criterion 4. "An external call that times out is indistinguishable
    from one that failed" — so a call that timed out after succeeding must
    complete on the next run. 404 means there is no such user, which is the
    state the call was trying to reach.
    """
    with _configured(), _http(_error(404)):
        result = delete_credential(USER)
    assert result.already_absent is True
    assert result.status == 404


def test_a_404_on_fetch_email_is_a_failure_not_success():
    """
    The opposite, and the asymmetry is deliberate: `allow_404` is passed only
    by the delete. A missing user when we need their address means there is no
    address, and treating that as success would skip the confirmation S-20
    promises.
    """
    with _configured(), _http(_error(404)):
        with pytest.raises(CredentialDeletionFailed):
            fetch_email(USER)


@pytest.mark.parametrize("code", [401, 403])
def test_an_auth_failure_says_retrying_will_not_help(code):
    with _configured(), _http(_error(code)):
        with pytest.raises(CredentialDeletionFailed) as exc:
            delete_credential(USER)
    assert "will not help" in str(exc.value)


def test_a_timeout_says_the_next_run_will_find_out():
    with _configured(), _http(TimeoutError()):
        with pytest.raises(CredentialDeletionFailed) as exc:
            delete_credential(USER)
    assert "next run" in str(exc.value)


# ── fetch_email ─────────────────────────────────────────────────────────

def test_fetch_email_returns_the_address():
    body = json.dumps({"id": str(USER), "email": "learner@example.test"})
    with _configured(), _http(_Response(body.encode(), 200)):
        assert fetch_email(USER) == "learner@example.test"


def test_a_user_with_no_email_is_a_failure_and_says_why():
    body = json.dumps({"id": str(USER), "email": None})
    with _configured(), _http(_Response(body.encode(), 200)):
        with pytest.raises(CredentialDeletionFailed) as exc:
            fetch_email(USER)
    assert "no address" in str(exc.value) or "no email" in str(exc.value)


def test_a_non_json_answer_is_a_failure_not_a_crash():
    """
    A Supabase project behind a captive portal or an error page answers HTML
    with a 200. `json.JSONDecodeError` escaping would be an unhandled
    exception in a worker rather than a recorded, retryable step.
    """
    with _configured(), _http(_Response(b"<html>maintenance</html>", 200)):
        with pytest.raises(CredentialDeletionFailed) as exc:
            fetch_email(USER)
    assert "not" in str(exc.value).lower()
