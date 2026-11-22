"""
Does `openapi.yaml` describe the bodies the handlers actually read?

Yogesh asked for this twice, after three contract drifts in three consecutive
tasks (`HANDOFF` V-10.1, V-11). Every one of them passed CI here and failed
only when a client was generated from the types:

- **T-034** · `DiagnosisCreate` declared `required: [diagnosis]`; the handler
  reads `body.get("text")`. A client built from the generated types got
  `diagnosis_empty` on every submission.
- **T-036** · the rating body declared `helpful`; `rate_feedback` reads
  `was_helpful`. It also declared a `comment` nothing read.
- **T-036** · the `Feedback` response schema described `diagnosis_verdict`,
  `correct_diagnosis`, `narrative` and a `generator` enum that migration 012
  does not allow, and carried no `summary`, `coverage` or scorecards.

The CT tests guard what must be **absent** from a response — that is their
whole purpose, and `questions_remaining` and `matched_topics` are the kind of
thing they catch. Nothing checked that the shape we *declare* is the shape we
*read*. So the contract could say anything at all about a request body and the
suite stayed green.

This walks the AST of the `/v1` route modules for the keys each handler reads
off the JSON body, and compares them with the schema the contract attaches to
that operation. It is static on purpose: no database, no app context, no
network, so it runs in milliseconds and cannot be skipped when Docker is
down — which is when a contract change is most likely to be made in a hurry.

It follows the idiom of `test_the_case_adapter_supplies_every_key_the_domain
_reads`, which walks the AST for the same reason: the alternative is noticing
in review.

**What it deliberately does not do.** It does not post example bodies to a
live app. That would catch more, needs the database, and duplicates the route
tests. If the response side ever drifts the way `Feedback` did, the fix is a
response-shape check in the route tests where a real response already exists —
not making this file heavier.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Final

import pytest
import yaml

V1 = pathlib.Path(__file__).resolve().parent.parent / "nidan" / "api" / "v1"
SPEC = pathlib.Path(__file__).resolve().parent.parent / "openapi.yaml"


@pytest.fixture(scope="module")
def api() -> dict:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


# ── Finding what a handler reads ─────────────────────────────────────
#
# The pattern throughout `/v1` is:
#
#     body = request.get_json(silent=True) or {}
#     text = str(body.get("text") or "").strip()
#
# so the keys are the string constants passed to `.get()` on a name that was
# assigned from `request.get_json(...)`. Subscripts (`body["text"]`) are read
# too, because a handler is free to use them.

_JSON_SOURCES: Final = ("get_json",)


def _body_names(tree: ast.AST) -> set[str]:
    """Local variable names assigned from `request.get_json(...)`."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        call = node.value
        # `request.get_json(silent=True) or {}` — unwrap the `or`.
        if isinstance(call, ast.BoolOp) and call.values:
            call = call.values[0]
        if (isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr in _JSON_SOURCES):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _string_constants(tree: ast.AST) -> dict[str, set[str]]:
    """
    Module-level names bound to a collection of string literals.

    `identity.py` validates with `_WRITABLE = frozenset({"display_name", …})`
    and then `{k: v for k, v in body.items() if k in _WRITABLE}`. No literal
    `body.get("display_name")` appears anywhere, so a walk that looks only for
    those sees a handler that reads nothing and reports every declared field
    as unread — six false positives on `PATCH /me` alone.

    A test with false positives gets switched off, so this resolves the
    constant instead. It errs towards counting a field as read, which makes
    the "declared but unread" check more lenient and never wrong in the
    direction that cries wolf.
    """
    out: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if (isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in ("frozenset", "set", "tuple", "list")
                and value.args):
            value = value.args[0]
        members: set[str] = set()
        if isinstance(value, (ast.Set, ast.Tuple, ast.List)):
            for element in value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    members.add(element.value)
        if not members:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out[target.id] = members
    return out


def _keys_read(tree: ast.AST, body_names: set[str],
               constants: dict[str, set[str]] | None = None) -> set[str]:
    keys: set[str] = set()
    constants = constants or {}

    # Any module-level string collection this function mentions by name. The
    # whitelist idiom above, and `set(body) - _WRITABLE` validation with it.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in constants:
            keys |= constants[node.id]
    for node in ast.walk(tree):
        # body.get("key")
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in body_names
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            keys.add(node.args[0].value)
        # body["key"]
        if (isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id in body_names
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            keys.add(node.slice.value)
        # "key" in body
        if isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.In):
            right = node.comparators[0]
            if (isinstance(right, ast.Name) and right.id in body_names
                    and isinstance(node.left, ast.Constant)
                    and isinstance(node.left.value, str)):
                keys.add(node.left.value)
    return keys


def _shape(path: str) -> str:
    """
    A path with its parameter NAMES removed.

    Flask spells the parameter `<uuid:session_id>` and `openapi.yaml` spells
    the same one `{id}`. Matching on the name finds nothing — which is how the
    first version of this file passed over the highest-volume endpoint in the
    API. Matching on position is what the two actually agree about.
    """
    out, i = [], 0
    while i < len(path):
        if path[i] in "<{":
            j = path.index(">" if path[i] == "<" else "}", i)
            out.append("{}")
            i = j + 1
        else:
            out.append(path[i])
            i += 1
    return "".join(out)


def _route_for(func: ast.FunctionDef) -> tuple[str, str] | None:
    """The `(method, path)` from a `@bp.post("/…")` decorator."""
    for dec in func.decorator_list:
        if not (isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr in ("get", "post", "patch", "put", "delete")
                and dec.args
                and isinstance(dec.args[0], ast.Constant)):
            continue
        rule = dec.args[0].value
        if not isinstance(rule, str):
            continue
        return dec.func.attr, _shape(rule)
    return None


def _schema_properties(api: dict, ref_or_schema: dict) -> tuple[set[str], set[str]]:
    """(declared properties, required properties), following one `$ref`."""
    schema = ref_or_schema
    ref = schema.get("$ref")
    if ref:
        name = ref.rsplit("/", 1)[-1]
        schema = api["components"]["schemas"][name]
    props = set((schema.get("properties") or {}).keys())
    required = set(schema.get("required") or [])
    return props, required


def _operations_with_bodies(api: dict) -> dict[tuple[str, str], dict]:
    out = {}
    for path, item in api["paths"].items():
        for method, op in item.items():
            if method not in ("get", "post", "patch", "put", "delete"):
                continue
            body = (op.get("requestBody") or {})
            schema = (((body.get("content") or {})
                       .get("application/json") or {}).get("schema"))
            if schema:
                out[(method, _shape(path))] = schema
    return out


def _handlers() -> dict[tuple[str, str], tuple[str, set[str]]]:
    """`(method, path)` → (module name, keys the handler reads)."""
    found: dict[tuple[str, str], tuple[str, set[str]]] = {}
    for py in sorted(V1.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        names = _body_names(tree)
        constants = _string_constants(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            route = _route_for(node)
            if route is None:
                continue
            # Body names are module-wide here; narrow to this function's own.
            local = _body_names(node) or names
            found[route] = (py.name, _keys_read(node, local, constants))
    return found


# ── The tests ────────────────────────────────────────────────────────

def test_the_ast_walk_finds_the_routes():
    """
    A guard on the guard. If `/v1` is restructured and this walk stops
    matching, every assertion below passes over an empty set and the file
    becomes decoration.
    """
    handlers = _handlers()
    assert len(handlers) >= 10, (
        f"the AST walk found only {len(handlers)} routes in {V1}; it has "
        f"probably stopped recognising the decorators")
    assert ("post", "/sessions/{}/questions") in handlers, (
        "the highest-volume endpoint was not found by the walk")


def test_every_declared_body_field_is_one_a_handler_reads(api):
    """
    The T-034 and T-036 drifts, in the direction that breaks a client.

    A field the contract declares and no handler reads is either a rename
    nobody propagated — `diagnosis` for `text`, `helpful` for `was_helpful` —
    or a feature that was specified and never built. Both mislead a client
    generated from the types, and the client is the thing that breaks.
    """
    handlers = _handlers()
    problems = []

    for (method, path), schema in _operations_with_bodies(api).items():
        entry = handlers.get((method, path))
        if entry is None:
            continue          # a 501 in contract.py, or a route not yet built
        module, read = entry
        if not read:
            continue          # handler takes a body it does not destructure
        declared, _ = _schema_properties(api, schema)
        unread = declared - read
        if unread:
            problems.append(
                f"{method.upper()} {path} ({module}): openapi.yaml declares "
                f"{sorted(unread)}, which the handler never reads")

    assert not problems, (
        "openapi.yaml describes request fields no handler reads:\n  "
        + "\n  ".join(problems)
        + "\n\nA client generated from these types sends a field that is "
          "ignored, or omits the one that is actually required. Change the "
          "contract and the code in the same commit, and regenerate "
          "web/src/api/schema.ts (CLAUDE.md)."
    )


def test_every_required_body_field_a_handler_reads_is_declared(api):
    """
    The same drift from the other side: a key the handler reads that the
    contract never mentions. A generated client has no way to send it, so the
    request fails validation for a reason the types cannot explain.
    """
    handlers = _handlers()
    problems = []

    for (method, path), schema in _operations_with_bodies(api).items():
        entry = handlers.get((method, path))
        if entry is None:
            continue
        module, read = entry
        declared, _ = _schema_properties(api, schema)
        undeclared = read - declared
        if undeclared:
            problems.append(
                f"{method.upper()} {path} ({module}): the handler reads "
                f"{sorted(undeclared)}, which openapi.yaml does not declare")

    assert not problems, (
        "handlers read request fields the contract does not declare:\n  "
        + "\n  ".join(problems)
        + "\n\nA client generated from openapi.yaml cannot send these."
    )
