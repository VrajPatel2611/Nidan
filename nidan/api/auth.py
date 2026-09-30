"""
Authentication for the v1 API (BUILD_PLAN T-014).

Two decorators, and the mapping from a verification failure to the stable error
code a client branches on.

```python
@bp.get("/me")
@require_auth
def me():
    return jsonify(profile_of(current_user_id()))
```

**The codes are a contract.** `openapi.yaml` freezes them: "Once shipped a code
is never renamed or repurposed — clients branch on it." The distinction that
matters most is `token_expired` versus `unauthenticated` (`API_CONTRACT` §3.3):
the first tells the client to refresh and retry once, the second logs the user
out. Collapsing them means either a learner thrown out of a consultation by a
routine hourly expiry, or a client retrying forever against a token that will
never work.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from uuid import UUID

from flask import g, jsonify, request

from nidan.infra.auth.tokens import (
    AuthError,
    JWKSUnavailable,
    TokenExpired,
    TokenInvalid,
    TokenMissing,
    verify,
)
from nidan.infra.db.repositories import AdminUser, AuthenticatedUser, repo_scope

# Where the Supabase SDK puts the access token when the client stores it in a
# cookie (SECURITY_SPEC L2). Checked after the header, so a request may always
# override it explicitly.
ACCESS_TOKEN_COOKIE = "sb-access-token"


def error(code: str, message: str, status: int,
          details: dict | None = None):
    """
    One error envelope, shaped as `API_CONTRACT` §2.6 and openapi.yaml.

    `details` carries the machine-readable part of a refusal — `resets_at` on a
    monthly limit, the id of the session already in progress. A block with no
    date is a dead end, and a client cannot compute one.
    """
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def bearer_token() -> str:
    """
    The presented token, from the header or the cookie.

    `API_CONTRACT` §2.2 specifies `Authorization: Bearer`. `SECURITY_SPEC` L2
    specifies httpOnly cookies. Both are right: the Next.js server holds the
    cookie and forwards the header (`UX_SPEC` §6.1). Accepting either means the
    server-rendered prototype works without a separate code path.
    """
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    if header:
        # A header that is present but not Bearer is a mistake worth surfacing
        # rather than falling through to the cookie and reporting "no token".
        raise TokenInvalid("Authorization header is not a Bearer token")
    return request.cookies.get(ACCESS_TOKEN_COOKIE, "")


def _authenticate():
    """
    Verify the request's token and stash the result on `g`.

    Returns None on success, or a ready-to-return error response.
    """
    try:
        token = bearer_token()
        g.token = verify(token)
        return None
    except TokenMissing:
        return error("unauthenticated", "Sign in to continue.", 401)
    except TokenExpired:
        # Its own code, deliberately. See the module docstring.
        return error("token_expired", "Your session has expired.", 401)
    except TokenInvalid:
        # The reason is not echoed. "Wrong audience" and "bad signature" tell
        # someone probing exactly which part of the token to change next; the
        # detail belongs in our logs, not in the response.
        return error("unauthenticated", "Sign in to continue.", 401)
    except JWKSUnavailable:
        # NOT a 401. The credentials may be perfectly good — we cannot check
        # them. A 401 here would send every client into a refresh loop against
        # an outage, turning a key-server blip into a stampede.
        return error("service_unavailable",
                     "Sign-in is temporarily unavailable. Please try again.", 503)
    except AuthError:                              # pragma: no cover - exhaustive
        return error("unauthenticated", "Sign in to continue.", 401)


def current_user_id() -> UUID:
    """The authenticated user's id. Only valid inside a `@require_auth` route."""
    token = getattr(g, "token", None)
    if token is None:
        raise RuntimeError(
            "current_user_id() outside an authenticated route — the handler is "
            "missing @require_auth")
    return token.user_id


def current_actor() -> AuthenticatedUser:
    """The actor to open a repository scope with (`ADR-0016`)."""
    return AuthenticatedUser(current_user_id())


def require_auth(view: Callable) -> Callable:
    """A valid Supabase JWT, or 401."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        failure = _authenticate()
        if failure is not None:
            return failure
        return view(*args, **kwargs)
    return wrapper


def require_tier(tier: str) -> Callable:
    """
    A valid JWT *and* a subscription tier, or 403 `pro_required`.

    **The tier is read from the profile, not from the token.** A JWT is issued
    at sign-in and lives about an hour; a subscription can be cancelled,
    expire, or be upgraded well inside that window. Trusting the claim would
    give a cancelled subscriber an hour of paid access and make a new
    subscriber wait for one — and the second is the complaint that arrives
    within minutes of taking someone's money.

    The cost is one indexed read, inside a transaction the request opens
    anyway.
    """
    if tier not in ("free", "pro"):
        raise ValueError(f"unknown tier: {tier!r}")

    def decorator(view: Callable) -> Callable:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            failure = _authenticate()
            if failure is not None:
                return failure

            with repo_scope(current_actor()) as db:
                profile = db.profiles.get()

            if profile is None:
                # Authenticated, but no profile row: they have signed up with
                # Supabase and never called POST /me. Not a permission problem.
                return error("not_found",
                             "Complete your profile to continue.", 404)
            if tier == "pro" and profile["subscription_tier"] != "pro":
                return error("pro_required",
                             "This feature is part of Nidan Pro.", 403)
            return view(*args, **kwargs)
        return wrapper
    return decorator

# Privilege levels on `profiles.platform_role` (migration 022). Admin implies
# every reviewer permission; reviewer does not imply admin.
ADMIN_ROLES = ("admin",)
REVIEWER_ROLES = ("admin", "reviewer")


def _not_found():
    """
    The admin console's refusal.

    **404, never 403** (`UX_SPEC` §12.1, `API_CONTRACT` §2.7). A 403 says "this
    exists and you may not have it", which tells someone probing that there is
    an admin console to attack. A 404 says nothing at all.

    Deliberately identical to the response for a URL that does not exist, and
    deliberately identical for "not signed in" and "signed in without
    privilege" — a difference between those two is the same leak in a quieter
    form, because it confirms the console exists to anyone with any account.
    """
    return error("not_found", "Not found.", 404)


def require_role(*allowed: str) -> Callable:
    """
    A valid JWT and a sufficient `platform_role`, or 404.

    The role is read from the profile, not from the token — same reasoning as
    `require_tier`: a JWT is issued at sign-in and lives about an hour, so a
    revoked admin would keep their access for the rest of it. Revocation that
    does not take effect until the token expires is not revocation.
    """
    def decorator(view: Callable) -> Callable:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            # Note: no distinct branch for "no token". Every failure here
            # returns the same 404, including an expired one — the admin
            # console does not tell an anonymous visitor that it exists, and
            # that outweighs the refresh-and-retry convenience `token_expired`
            # buys on the learner-facing API.
            if _authenticate() is not None:
                return _not_found()

            with repo_scope(current_actor()) as db:
                profile = db.profiles.get()

            if profile is None or profile["platform_role"] not in allowed:
                return _not_found()

            # Stashed so `current_admin()` does not have to re-read the
            # profile, and — more to the point — so it cannot be called from a
            # route that never checked one. The privilege and the scope that
            # depends on it are then established by the same decorator.
            g.platform_role = profile["platform_role"]
            return view(*args, **kwargs)
        return wrapper
    return decorator


def current_admin() -> AdminUser:
    """
    The actor for a scope that writes clinical content. `@require_admin` only.

    `AdminUser` runs as `nidan_admin`, the role migration 023 grants INSERT and
    UPDATE on `cases` and `case_versions`. `current_actor()` deliberately keeps
    returning an ordinary `AuthenticatedUser` even for an administrator: the
    elevated role is for the console's own writes, and a route that only reads
    should not silently acquire the privilege to author content.

    So the choice is made per route, by which function it calls — not per
    person. An admin browsing the learner-facing app is `nidan_app` like
    everyone else.
    """
    role = getattr(g, "platform_role", None)
    if role not in ADMIN_ROLES:
        raise RuntimeError(
            "current_admin() outside an admin route — the handler is missing "
            "@require_admin, and without it nothing has verified the privilege "
            "this scope is about to run with")
    return AdminUser(current_user_id())


def require_admin(view: Callable) -> Callable:
    """Admin only. Everything else gets a 404."""
    return require_role(*ADMIN_ROLES)(view)


def require_reviewer(view: Callable) -> Callable:
    """
    Admins and clinical reviewers.

    Reviewers reach the console because T-023 has them opening a case version
    in Playtest to assess it. They are not admins: the case editor and the
    operational screens stay closed to them.
    """
    return require_role(*REVIEWER_ROLES)(view)
