"""
The operations `openapi.yaml` declares but T-030 has not yet built.

`openapi.yaml` declares `501 NotImplemented` on every unbuilt operation and
says why: "the contract exists first so the frontend can be built against it
(sync point S-1)." `nidan/api/v1.py` repeated the claim in its own docstring —
"everything not implemented here still answers 501".

**No such handler existed.** An unbuilt v1 path returned Flask's default 404
HTML page: not a 501, not JSON, not the error envelope. So S-1 never worked,
and contract tests CT-6 and CT-7 failed on every declared-but-unbuilt route.
This module is that handler.

**Why a hand-maintained list rather than parsing the YAML.** `pyyaml` is a dev
dependency, not a runtime one, so the running application cannot read
`openapi.yaml`. Keeping the list here and checking it in CI is the same bargain
`nidan/api/errors.py` makes with the §10 catalogue: the code holds the data,
and a test fails if the spec and the code disagree.

**This list only shrinks.** Each T-030 slice deletes the lines it implements,
and `tests/test_api_contract.py` fails if an entry here is also a real route —
so a forgotten line cannot quietly shadow a working endpoint.
"""

from __future__ import annotations

from typing import Final

from flask import request

from nidan.api.errors import error
from nidan.api.v1.blueprint import bp

# (rule, methods) for every declared operation with no implementation yet.
# Flask converter syntax, matching the paths in openapi.yaml.
UNIMPLEMENTED: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    # `DELETE /me` is NOT unfinished work — it is blocked, and answering 501
    # is the honest response.
    #
    # §4 says it "executes §10.2 of DATA_MODEL", and §10.2's erasure does
    # `UPDATE session_events SET payload = jsonb_set(payload, '{text}',
    # '"[redacted]"')`. Migration 010 puts `forbid_mutation()` on that table
    # as BEFORE UPDATE OR DELETE, unconditionally — verified: even the table
    # owner gets "Table session_events is append-only".
    #
    # So the half of the erasure that redacts what the learner typed cannot
    # run. Returning 204 having only anonymised the profile would claim an
    # erasure that did not happen, which is worse than refusing: §10.2 itself
    # says a user "has a right to know what does not disappear".
    #
    # Logged as API-9. It needs a decision with a legal dimension, not a
    # workaround from a request handler.
    ("/me",                               ("DELETE",)),
    # Phase 4, T-041. Declared here so the 501 is the contract's 501 rather
    # than a 404 that reads as a typo in the client's URL.
    ("/billing/checkout",                  ("POST",)),
    ("/billing/portal",                    ("POST",)),
    ("/webhooks/stripe",                   ("POST",)),
)


def _not_implemented(**_kwargs):
    """
    The declared-but-unbuilt response.

    Deliberately distinguishable from a 404. A client that gets 404 looks for
    a typo in its own URL; a client that gets 501 knows the endpoint is coming
    and can build against the schema in the meantime. Conflating them is how
    a frontend team loses a day.
    """
    return error("not_implemented",
                 "This endpoint is not implemented yet.", 501)


def register_unimplemented() -> None:
    """
    Attach a 501 to every declared operation with no handler.

    Called from `__init__.py` AFTER the route modules are imported, so a real
    handler always wins: Flask raises on a duplicate endpoint name, and the
    test suite asserts no rule appears both here and as a live route.
    """
    for rule, methods in UNIMPLEMENTED:
        bp.add_url_rule(
            rule,
            endpoint=f"not_implemented {rule} {'/'.join(methods)}",
            view_func=_not_implemented,
            methods=list(methods),
        )


def register_error_handlers(app) -> None:
    """
    JSON 404s and 405s for `/v1`, registered on the **app**, not the blueprint.

    `@bp.errorhandler(404)` looks like the right thing and never fires. A 404
    for an unmatched URL is raised during routing, before Flask has decided
    which blueprint the request belongs to, so there is no blueprint whose
    handler could run — and the client gets Flask's HTML page, which a JSON
    client reports as a parse error somewhere unrelated. 405 is the same.

    Scoped by path prefix so the admin console and the server-rendered
    prototype keep their HTML error pages: `UX_SPEC` §12.1 wants an admin
    refusal to be an ordinary, unremarkable 404, and JSON would make it
    remarkable.
    """

    def _is_v1() -> bool:
        return request.path.startswith("/v1/") or request.path == "/v1"

    @app.errorhandler(404)
    def _not_found(e):
        if _is_v1():
            return error("not_found", "No such endpoint.", 404)
        return e

    @app.errorhandler(405)
    def _method_not_allowed(e):
        """
        A wrong method on a `/v1` path is 404, not 405.

        405 carries an `Allow` header listing what the path does accept, and
        `API_CONTRACT` §2.7 declines to confirm the existence of things the
        caller has not been granted. The envelope matters more than the
        distinction, and a client that sent the wrong verb has a bug either
        way.
        """
        if _is_v1():
            return error("not_found", "No such endpoint.", 404)
        return e
