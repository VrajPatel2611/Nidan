"""
The error envelope and the code catalogue (`API_CONTRACT` §2.6, §10).

**The catalogue is data, not prose.** §10 says a code "is never renamed or
repurposed once shipped", and the status that goes with it is equally fixed —
but until now both lived only in a Markdown table and a YAML enum, which is to
say nowhere the code could check. Two things had already drifted by the time
this module was written:

- `service_unavailable` was being returned by `require_auth` on a JWKS outage
  and appeared in neither the §10 table nor `openapi.yaml`
- `not_implemented` is declared on every unbuilt operation in `openapi.yaml`
  and was likewise absent from §10 — and the handler that would return it did
  not exist at all

Both are now here, and `tests/test_api_contract.py` fails if this mapping, the
§10 table and the `openapi.yaml` enum ever disagree. That is contract test CT-7
turned from an assertion about responses into an assertion about the source.

**This module lives in `nidan/api/`, not `nidan/api/v1/`.** The admin console
returns the same envelope (`UX_SPEC` §12), so the catalogue cannot belong to
the versioned API alone.
"""

from __future__ import annotations

from typing import Final

from flask import g, jsonify

# code -> HTTP status. `API_CONTRACT` §10, in the order the table lists them.
CATALOGUE: Final[dict[str, int]] = {
    # 401 — who are you
    "unauthenticated":        401,
    "token_expired":          401,
    # 403 — we know, and no
    "forbidden":              403,
    "pro_required":           403,
    "monthly_limit_reached":  403,
    # 404 — absent, or not yours (§2.7: never 403 for someone else's row)
    "not_found":              404,
    "feedback_not_ready":     404,
    "unknown_key":            404,
    # 409 — conflicts with the current state
    "session_already_active": 409,
    "session_concluded":      409,
    "session_not_concluded":  409,
    "trial_already_used":     409,
    "no_approving_review":    409,
    # 422 — well-formed, semantically wrong
    "validation_failed":      422,
    "question_too_long":      422,
    "diagnosis_empty":        422,
    "diagnosis_too_long":     422,
    "patient_data_detected":  422,
    "keyword_overlap":        422,
    "idempotency_key_reused": 422,
    "confirmation_required":  422,
    "invalid_timezone":       422,
    "consent_version_required": 422,
    "trial_expired":          422,
    # 429 — too much
    "question_limit_reached": 429,
    "rate_limited":           429,
    # 500 / 501 / 503 — us, not you
    "internal_error":         500,
    "not_implemented":        501,
    "service_unavailable":    503,
    "patient_unavailable":    503,
    "no_cases_available":     503,
}


class UncataloguedError(RuntimeError):
    """
    Raised when a handler invents a code, or contradicts the one it claims.

    Deliberately an exception rather than a silent correction. A response code
    is part of the published contract: a client branches on it (§2.6), and a
    client cannot branch on something we made up at the call site. CT-7 would
    catch it in CI, and this catches it one layer earlier — while someone is
    still looking at the handler that did it.
    """


def error(code: str, message: str, status: int | None = None,
          details: dict | None = None):
    """
    One error envelope, shaped as `API_CONTRACT` §2.6 and `openapi.yaml`.

    `status` is optional and derived from the catalogue. Passing it is a
    cross-check, not a choice: a value that disagrees with §10 raises, because
    `error("not_found", ..., 403)` is exactly the leak §2.7 forbids and it is
    invisible on inspection — both arguments read as plausible.

    `details` carries the machine-readable part of a refusal — `resets_at` on a
    monthly limit, the id of the session already in progress. A block with no
    date is a dead end, and a client cannot compute one.

    `request_id` is included on **5xx only**, and that line is not arbitrary.

    §2.6 describes it as "shown to users on a 500" and `openapi.yaml` leaves it
    out of `required`. Its job is to let someone quote an identifier back to
    support, which they do when something failed on our side. A 4xx is the
    caller's own doing, and the caller has its own context.

    Putting it on every error instead costs something specific: `UX_SPEC`
    §12.1 requires every admin-console refusal to be **byte-identical**, so
    that no difference between "no token", "expired token" and "signed in
    without privilege" is observable. A per-request id in the body makes any
    two refusals differ, and four tests in `tests/` assert that they do not.

    The id carries no information — `uuid4().hex[:16]`, random per request —
    so those tests are a proxy for the real property rather than the property
    itself. But the proxy is the thing that would notice if a real difference
    ever crept in, and weakening it to accommodate an unrelated change is how
    an invariant quietly stops being one. `X-Request-ID` is on every response
    regardless, so nothing is lost for debugging a 422.
    """
    expected = CATALOGUE.get(code)
    if expected is None:
        raise UncataloguedError(
            f"{code!r} is not in API_CONTRACT §10. Add it to CATALOGUE, to the "
            f"§10 table and to the openapi.yaml enum in the same commit, or "
            f"use an existing code.")
    if status is not None and status != expected:
        raise UncataloguedError(
            f"{code!r} is a {expected} in API_CONTRACT §10, but this call "
            f"passed {status}. The status for a code is fixed by the contract.")

    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    # Outside a request context — a CLI, a background job — there is no id to
    # quote, and inventing one would point at a log line that does not exist.
    request_id = getattr(g, "request_id", None)
    if expected >= 500 and request_id:
        body["error"]["request_id"] = request_id
    return jsonify(body), expected
