"""
The idempotency store (`API_CONTRACT` §2.8).

§2.8: "first request executes and the response is stored for 24 h. A repeat
with the same key and the same body replays the stored response. A repeat with
the same key and a **different** body returns `422 idempotency_key_reused`."

Required on `POST /sessions/{id}/diagnosis`, which is irreversible — a client
that retries a timed-out submission must not conclude a second consultation,
and must not be told its first attempt failed when it succeeded.

**The body is compared by hash, not stored.** A diagnosis is clinical free
text a learner typed; keeping a second copy of it under a client-chosen key,
in a table with a different retention rule from `session_events`, is a privacy
surface with no purpose. The hash answers the only question §2.8 asks.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa

from nidan.infra.db.repositories.base import Repository


def body_hash(body: Mapping[str, Any] | None) -> str:
    """
    A stable hash of the request body.

    Canonicalised with sorted keys, so a client that serialises its JSON in a
    different field order on the retry is not told its body changed — which
    would turn a correct retry into a 422.
    """
    canonical = json.dumps(body or {}, sort_keys=True, separators=(",", ":"),
                           default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyRepository(Repository):
    """
    Keys are scoped to the user as well as the endpoint.

    `key` is the primary key and a client chooses it, so without the user in
    the row one learner could claim a key another is about to use — and the
    second would replay a response belonging to the first. Writing `user_id`
    means a collision across users is visible rather than silently served.
    """

    def find(self, key: str, endpoint: str) -> Mapping[str, Any] | None:
        """
        The stored attempt for this key, or None. Expired rows are not
        returned: §2.8 gives the store a 24-hour life, and a key that outlived
        it is a new key.
        """
        return self._conn.execute(sa.text("""
            SELECT key, user_id, endpoint, request_hash, response, status_code
            FROM idempotency_keys
            WHERE key = :key AND endpoint = :endpoint AND expires_at > now()
        """), {"key": key, "endpoint": endpoint}).mappings().first()

    def remember(self, key: str, endpoint: str, request_hash: str, *,
                 response: Mapping[str, Any], status_code: int) -> None:
        """
        Store the outcome so a retry can replay it.

        `ON CONFLICT DO NOTHING` rather than an upsert. If a row already
        exists, another request with this key got there first and its
        response is the one to serve — overwriting would make which response a
        client sees depend on which request finished last.
        """
        self._conn.execute(sa.text("""
            INSERT INTO idempotency_keys
                (key, user_id, endpoint, request_hash, response, status_code)
            VALUES (:key, :uid, :endpoint, :hash, CAST(:response AS jsonb), :status)
            ON CONFLICT (key) DO NOTHING
        """), {"key": key, "uid": self._user_id(), "endpoint": endpoint,
               "hash": request_hash, "response": json.dumps(response),
               "status": status_code})
