"""
The v1 JSON API (`ADR-0006`, BUILD_PLAN T-030).

`openapi.yaml` is the contract and this package implements it. The package
layout follows `API_CONTRACT`'s own sections rather than inventing a second
taxonomy — identity, consultation, and the declared-but-unbuilt remainder —
so a reader can go from a section number to a file without a map.

    blueprint.py   the Blueprint object, alone, to keep imports acyclic
    errors         ../errors.py — the envelope and the §10 catalogue, shared
                   with the admin console
    identity.py    §4   · /me
    sessions.py    §6   · /sessions, /trial/sessions
    contract.py    the 501s openapi.yaml declares, and the JSON 404

The server-rendered blueprint in `api/routes.py` is the prototype and is
**not** replaced here. It reads cases from `cases.py` rather than from the
published bank, so it survives until T-034 gives the learner a real screen —
deleting it at T-030 would leave no working consultation at all for weeks.
"""

from __future__ import annotations

# Imported for their side effect: each module registers its routes on `bp`.
from nidan.api.v1 import (  # noqa: F401,E402  (route registration)
    contract,  # noqa: E402
    identity,
    sessions,
)
from nidan.api.v1.blueprint import bp

# After the real routes, so a live handler always wins the rule.
contract.register_unimplemented()

# Registered by `create_app`: the 404/405 envelope cannot live on the
# blueprint, because routing fails before a blueprint is chosen.
register_error_handlers = contract.register_error_handlers

__all__ = ["bp", "register_error_handlers"]
