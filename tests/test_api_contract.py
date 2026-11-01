"""
T-030 · the API contract, checked against the code (`API_CONTRACT` §2.6, §10, §11).

Contract tests CT-6 and CT-7 are specified as assertions about *responses* —
every error validates against the envelope, every code appears in the §10
catalogue. Checking them that way alone has a hole: it only covers the
responses a test happens to provoke. A code returned on a path nobody exercised
is exactly as undocumented and nothing fails.

So they are checked twice here, as the codebase does elsewhere: against the
source, where the catalogue, the §10 table and the `openapi.yaml` enum must
agree; and against live responses, where the envelope shape is asserted.

The source-level check found two real gaps the day it was written, which is
the argument for it. `service_unavailable` was in the enum and being returned
by `require_auth`, and was absent from the §10 table. `not_implemented` was in
neither, despite `openapi.yaml` declaring it on every unbuilt operation and two
docstrings claiming the handler existed. It did not.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from nidan.api.errors import CATALOGUE, UncataloguedError, error
from nidan.api.v1.contract import UNIMPLEMENTED

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT_MD = ROOT / "docs" / "spec" / "API_CONTRACT.md"
OPENAPI = ROOT / "openapi.yaml"


@pytest.fixture
def app():
    from nidan.app import create_app
    return create_app({"TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()


def _live_operations(app, *, real_only: bool = False) -> set[tuple[str, str]]:
    """Every (METHOD, path) the url_map serves under /v1."""
    return {
        (method, rule.rule.removeprefix("/v1"))
        for rule in app.url_map.iter_rules() if rule.rule.startswith("/v1")
        for method in (rule.methods - {"HEAD", "OPTIONS"})
        if not (real_only and "not_implemented" in (rule.endpoint or ""))
    }


def _spec() -> dict:
    with OPENAPI.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _enum_codes() -> set[str]:
    """The `code` enum from the Error schema in openapi.yaml."""
    schema = _spec()["components"]["schemas"]["Error"]
    return set(schema["properties"]["error"]["properties"]["code"]["enum"])


def _table_codes() -> dict[str, int]:
    """
    The §10 catalogue, parsed out of the Markdown table.

    Parsed rather than transcribed. A transcription is a fourth copy, and the
    whole point of this file is that copies drift.
    """
    text = CONTRACT_MD.read_text(encoding="utf-8")
    section = text.split("# 10. Error code catalogue", 1)[1].split("\n# ", 1)[0]
    rows = re.findall(r"^\|\s*`([a-z_]+)`\s*\|\s*(\d{3})\s*\|", section, re.M)
    return {code: int(status) for code, status in rows}


def _declared_operations() -> set[tuple[str, str]]:
    """
    Every (METHOD, path) openapi.yaml declares, with Flask's converter syntax
    substituted for OpenAPI's, so it can be compared with the url_map.
    """
    ops = set()
    for path, item in _spec()["paths"].items():
        rule = path.replace("{id}", "<uuid:session_id>")
        for method in item:
            if method.lower() in {"get", "post", "patch", "delete", "put"}:
                ops.add((method.upper(), rule))
    return ops


# ── the three copies must agree ──────────────────────────────────────

def test_the_catalogue_matches_the_api_contract_table():
    table = _table_codes()
    assert table, "parsed no rows out of API_CONTRACT §10 — has the table changed shape?"
    assert CATALOGUE == table, (
        "nidan/api/errors.py and API_CONTRACT §10 disagree.\n"
        f"  only in code:  {sorted(set(CATALOGUE) - set(table))}\n"
        f"  only in §10:   {sorted(set(table) - set(CATALOGUE))}\n"
        f"  status differs: "
        f"{sorted(c for c in set(CATALOGUE) & set(table) if CATALOGUE[c] != table[c])}")


def test_the_catalogue_matches_the_openapi_enum():
    enum = _enum_codes()
    assert set(CATALOGUE) == enum, (
        "nidan/api/errors.py and openapi.yaml disagree. A client generated "
        "from the schema cannot branch on a code the schema does not list.\n"
        f"  only in code:    {sorted(set(CATALOGUE) - enum)}\n"
        f"  only in openapi: {sorted(enum - set(CATALOGUE))}")


# ── CT-7, at the source rather than in a response ────────────────────

def test_error_refuses_a_code_that_is_not_in_the_catalogue():
    """
    CT-7's guarantee, one layer earlier than CT-7 can reach it.

    A code invented at a call site is undocumented whether or not a test
    happens to provoke that path.
    """
    with pytest.raises(UncataloguedError, match="not in API_CONTRACT"):
        error("made_up_code", "nope")


def test_error_refuses_a_status_that_contradicts_the_catalogue():
    """
    `error("not_found", ..., 403)` is the §2.7 leak, and it is invisible on
    inspection — both arguments read as plausible.
    """
    with pytest.raises(UncataloguedError, match="fixed by the contract"):
        error("not_found", "nope", 403)


def test_every_error_call_site_uses_a_catalogued_code():
    """
    Static sweep of the whole package, so an un-exercised path cannot smuggle
    one in. The runtime check above only fires if the line actually runs.
    """
    import ast
    offenders = []
    for py in (ROOT / "nidan").rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "error" and node.args
                    and isinstance(node.args[0], ast.Constant)):
                code = node.args[0].value
                if code not in CATALOGUE:
                    offenders.append(
                        f"{py.relative_to(ROOT)}:{node.lineno} -> {code!r}")
    assert not offenders, (
        "error() called with a code absent from API_CONTRACT §10:\n  "
        + "\n  ".join(offenders))


# ── every declared operation answers something ───────────────────────

def test_every_declared_operation_is_routed_or_returns_501(app):
    """
    Sync point S-1, finally true.

    `openapi.yaml` declares `501 NotImplemented` on every unbuilt operation and
    says the contract exists first so the frontend can build against it. Until
    T-030 nothing implemented that: an unbuilt path returned Flask's HTML 404.
    """
    missing = _declared_operations() - _live_operations(app)
    assert not missing, (
        "declared in openapi.yaml but neither implemented nor listed in "
        f"nidan/api/v1/contract.py UNIMPLEMENTED: {sorted(missing)}")


def test_no_unimplemented_entry_shadows_a_real_route(app):
    """
    The 501 list only shrinks. A line left behind after a slice implements it
    would be registered after the real handler and could mask working code, so
    it fails here instead.
    """
    live = _live_operations(app, real_only=True)
    stale = [(m, rule) for rule, methods in UNIMPLEMENTED for m in methods
             if (m, rule) in live]
    assert not stale, (
        f"implemented, but still listed as UNIMPLEMENTED: {sorted(stale)}. "
        f"Delete the line.")


# ── CT-6, against live responses ─────────────────────────────────────

def test_an_unbuilt_endpoint_returns_the_envelope_not_html(client):
    r = client.get("/v1/progress")
    assert r.status_code == 501
    assert r.is_json, "a 501 returned HTML; API_CONTRACT §2.6 wants the envelope"
    assert r.get_json()["error"]["code"] == "not_implemented"


def test_an_unknown_v1_path_is_a_json_404(client):
    """
    §2.6: "every 4xx and 5xx returns the same shape. No endpoint invents its
    own" — including the ones no endpoint owns.
    """
    r = client.get("/v1/no-such-thing")
    assert r.status_code == 404
    assert r.is_json
    assert r.get_json()["error"]["code"] == "not_found"


def test_the_wrong_method_does_not_advertise_the_right_one(client):
    """
    405 lists the methods a path accepts. §2.7 declines to confirm the
    existence of things the caller has not been granted.
    """
    r = client.delete("/v1/progress")
    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "not_found"


def test_a_5xx_carries_a_request_id(client):
    """
    §2.6 lists `request_id`; `UX_SPEC` S-21 shows it to the user on a 500. It
    was specified from the start and never populated — `app.py` generated one
    per request and put it only in a response header, so a user quoting what
    they saw had nothing to quote.
    """
    r = client.get("/v1/progress")               # 501
    body = r.get_json()["error"]
    assert body.get("request_id"), "no request_id in the envelope"
    assert body["request_id"] == r.headers["X-Request-ID"], (
        "the body and the header disagree, so one of them points at the wrong "
        "log line")


def test_a_4xx_does_not_carry_a_request_id(client):
    """
    The other half of that decision, and the reason for it.

    `UX_SPEC` §12.1 requires every admin-console refusal to be byte-identical,
    so that "no token", "expired token" and "signed in without privilege" are
    indistinguishable. A per-request id in the body makes any two refusals
    differ. The id is random and carries nothing, so the four tests asserting
    byte-identity are a proxy for the property rather than the property — but
    they are what would notice a real difference creeping in, and §2.6 ties
    `request_id` to the 500 case anyway.

    `X-Request-ID` is still on the response, so a developer debugging a 422
    has not lost it.
    """
    r = client.get("/v1/no-such-thing")          # 404
    assert "request_id" not in r.get_json()["error"]
    assert r.headers["X-Request-ID"], "the header should carry it regardless"


def test_the_envelope_has_no_fields_the_schema_does_not_declare(client):
    declared = set(_spec()["components"]["schemas"]["Error"]
                   ["properties"]["error"]["properties"])
    r = client.get("/v1/progress")
    extra = set(r.get_json()["error"]) - declared
    assert not extra, f"undeclared field(s) in the error envelope: {sorted(extra)}"
