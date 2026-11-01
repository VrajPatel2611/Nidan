"""
The `/v1` blueprint object, alone in its own module.

Separate so the route modules can import it without importing each other:
`identity.py` and `sessions.py` both need `@bp.post`, and if `bp` lived in
`__init__.py` — which imports them — that would be a cycle.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint("v1", __name__)
