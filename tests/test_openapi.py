"""
T-011 · openapi.yaml is valid, and honest about the contract.

This file is what the frontend generates its client from (sync point S-1), so
an error here costs Yogesh rework rather than costing us a red test. These
checks are cheap and the failure mode is expensive.

Two of them guard product guarantees rather than syntax: assessment state must
not be exposed during a consultation, and bias vocabulary must not appear in
any response. Those are CT-1, CT-2 and CT-5 in API_CONTRACT §11, and the schema
is where they are easiest to break by accident.
"""

from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml")

SPEC = pathlib.Path(__file__).resolve().parent.parent / "openapi.yaml"


class DuplicateKey(ValueError):
    """A mapping key given twice. YAML allows it; a contract cannot."""


class _StrictLoader(yaml.SafeLoader):
    """
    `safe_load`, except a repeated key raises instead of winning.

    **This file's docstring promised something `safe_load` does not deliver.**
    PyYAML keeps the LAST of a duplicated key and says nothing, so when T-030
    slice 5 added a second `description:` to `DELETE /me` without removing the
    first, every assertion here passed over a file that strict parsers reject —
    and the failure surfaced in the web app's type generator, on Yogesh's
    laptop, four days later. The one guard was `npm run check:api`, which means
    a backend mistake failed in the frontend's CI.
    """


def _no_duplicate_keys(loader, node, deep=False):
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateKey(
                f"{key!r} is given twice in the same mapping, at line "
                f"{key_node.start_mark.line + 1}. PyYAML keeps the last one "
                f"silently; openapi-typescript refuses the file.")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


@pytest.fixture(scope="module")
def api() -> dict:
    """
    The contract, parsed strictly.

    Every other test in this file runs against this, so they all now fail on a
    duplicated key rather than asserting over the last-one-wins result.
    """
    return yaml.load(SPEC.read_text(encoding="utf-8"), Loader=_StrictLoader)


def test_the_contract_has_no_duplicate_keys():
    """
    Named separately from the fixture so the failure says what is wrong.

    A fixture error reads as "every openapi test is broken"; this reads as
    "line 103 defines `description` twice", which is the sentence someone
    needs. Keep both.
    """
    yaml.load(SPEC.read_text(encoding="utf-8"), Loader=_StrictLoader)


def test_the_strict_loader_actually_rejects_a_duplicate():
    """
    The guard above is only worth having if it bites, and `safe_load` passing
    the same text is the whole point — that is what shipped the bug.
    """
    text = "paths:\n  /me:\n    delete:\n      description: first\n      description: second\n"

    assert yaml.safe_load(text)["paths"]["/me"]["delete"]["description"] == "second", (
        "safe_load should silently keep the last duplicate — if this fails, "
        "PyYAML changed and the strict loader may be redundant")

    with pytest.raises(DuplicateKey, match="description"):
        yaml.load(text, Loader=_StrictLoader)


def _as_openapi_path(rule: str) -> str:
    """
    A Flask rule as openapi.yaml spells it.

    Without this the comparison below silently never matched a parameterised
    operation: Flask says `/sessions/<uuid:session_id>` and the contract says
    `/sessions/{id}`, so every path with an id in it looked unimplemented and
    the test went on requiring a 501 it would never notice had become wrong.
    Found in T-030 slice 2b, when `GET /sessions/{id}` was implemented and
    this test stayed green.
    """
    import re

    return re.sub(r"<[^:>]+:([^>]+)>", "{id}", rule).removeprefix("/v1")


class TestStructure:
    def test_it_parses(self, api):
        assert api["openapi"].startswith("3.")

    def test_every_documented_endpoint_is_present(self, api):
        """
        Cross-checked against API_CONTRACT's own headings, so an endpoint added
        to the contract and forgotten here is caught rather than discovered by
        whoever generates the client.
        """
        import re

        contract = (SPEC.parent / "docs" / "spec" / "API_CONTRACT.md").read_text(
            encoding="utf-8")
        documented = {
            m.group(2) for m in re.finditer(
                r"^## `(GET|POST|PATCH|DELETE|PUT) (/v1[^`]*)`", contract, re.M)
        }
        # Normalise: the spec writes /v1/... , the file's servers carry the /v1.
        declared = {"/v1" + p for p in api["paths"]}
        missing = sorted(documented - declared)
        assert not missing, f"documented in API_CONTRACT but absent here: {missing}"

    def test_an_operation_declares_501_exactly_when_it_is_not_implemented(self, api):
        """
        The contract and the application must agree about what exists.

        T-011 wrote this as "every operation declares 501", which was true when
        none of them worked. T-014 implemented the first two, and the check is
        more useful stated as an equivalence: an operation that is implemented
        must NOT advertise 501, and one that is not implemented must. Either
        error misleads a generated client — the first makes a working endpoint
        look unavailable, the second makes a stub look ready.

        Implementation is read from the app's own routing table rather than a
        hand-kept list, so this cannot go stale the way the original did.

        **A route is not the same thing as an implementation.** T-030 gave
        every declared-but-unbuilt operation a handler that returns 501 with
        the error envelope, because `openapi.yaml` declares that response and
        nothing had ever produced it — an unbuilt path used to return Flask's
        HTML 404. Those stubs are routes, so "appears in the url_map" stopped
        meaning "implemented" the day they landed, and this test started
        reporting every stub as a contradiction. They are excluded by endpoint
        name, which is also what makes the equivalence stricter than before:
        an operation served by a stub must declare 501, and one served by a
        real handler must not.
        """
        from nidan.app import create_app

        app = create_app({"TESTING": True, "SECRET_KEY": "openapi-test"})
        implemented = {
            (method.lower(), _as_openapi_path(str(rule)))
            for rule in app.url_map.iter_rules()
            if str(rule).startswith("/v1")
            and "not_implemented" not in (rule.endpoint or "")
            for method in (rule.methods or set())
            if method not in ("HEAD", "OPTIONS")
        }

        wrong = []
        for path, item in api["paths"].items():
            for method, op in item.items():
                if method not in ("get", "post", "patch", "delete", "put"):
                    continue
                declares_501 = "501" in op.get("responses", {})
                is_implemented = (method, path) in implemented
                if is_implemented and declares_501:
                    wrong.append(f"{method.upper()} {path} is implemented but declares 501")
                if not is_implemented and not declares_501:
                    wrong.append(f"{method.upper()} {path} is a stub but declares no 501")

        assert not wrong, "openapi.yaml disagrees with the app:\n  " + "\n  ".join(wrong)

    def test_every_ref_resolves(self, api):
        """A dangling $ref generates a broken client, not an error here."""
        import re

        refs = set(re.findall(r"#/components/(\w+)/(\w+)", SPEC.read_text(encoding="utf-8")))
        for section, name in refs:
            assert name in api["components"].get(section, {}), \
                f"unresolved $ref: #/components/{section}/{name}"


class TestProductGuarantees:
    """The two rules from CLAUDE.md that are easiest to break in a schema."""

    def test_no_bias_vocabulary_in_field_names_or_values(self, api):
        """
        PRD P1 / CT-5. A field named `anchoring_score`, or an enum value
        `premature_closure`, puts the word in front of a learner through the
        generated client without anyone writing it into the UI.

        Scoped to NAMES and VALUES, not prose. A `description` that explains
        why the rule exists is developer documentation and is the right place
        for the vocabulary — stripping it would lose the reason and make the
        constraint look arbitrary to whoever reads the schema next.
        """
        banned = ("anchoring", "premature_closure", "premature closure",
                  "confirmation_bias", "confirmation bias")
        offenders: list[str] = []

        def walk(node, path=""):
            if isinstance(node, dict):
                for k, v in node.items():
                    # Skip prose; check the key itself and any enum values.
                    if k in ("description", "summary", "example"):
                        continue
                    if any(b in str(k).lower() for b in banned):
                        offenders.append(f"{path}.{k} (field name)")
                    if k == "enum":
                        for value in v:
                            if any(b in str(value).lower() for b in banned):
                                offenders.append(f"{path}.enum = {value!r}")
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    walk(item, f"{path}[{i}]")

        walk(api)
        assert not offenders, (
            "bias vocabulary in field names or values:\n  "
            + "\n  ".join(offenders)
            + "\nUser-facing headings are 'Diagnostic focus / History "
              "completeness / Evidence exploration'."
        )

    def test_the_session_schema_exposes_no_assessment_state(self, api):
        """
        PRD P2 / CT-1, CT-2. A coverage figure or readiness hint on the session
        response teaches the metric instead of the skill, and the client would
        happily render it.

        `questions_remaining` is in this set on purpose and stays: API-6
        settled it as permanently absent on 11 Nov 2026. `API_CONTRACT` §6 had
        argued for it, citing `UX_SPEC` S-10 — whose table of what is
        deliberately absent opens with "Question counter | U2". §6 has been
        corrected. Deleting the entry reopens a decision; it does not fix a
        test.
        """
        session = api["components"]["schemas"]["Session"]["properties"]
        forbidden = {
            "coverage", "coverage_pct", "topics_covered", "topics_missed",
            "questions_remaining", "readiness", "completeness", "score",
            "detected", "bias_flags", "required_topics",
        }
        leaked = forbidden & set(session)
        assert not leaked, f"assessment state exposed mid-consultation: {leaked}"

    def test_the_cap_stays_derivable_without_a_counter_field(self, api):
        """
        The other half of API-6, and the half a schema change could break
        silently.

        Omitting `questions_remaining` costs nothing only because a client can
        count its own questions out of what it is already sent: `transcript`
        entries carry a `type`, and "question" is one of its values. If that
        discriminator is ever dropped or renamed, the 40 has no second route to
        a client and the pressure to re-add the forbidden field comes straight
        back — with the argument that there is no alternative, which would by
        then be true.

        So this is not a test of `TranscriptEntry` for its own sake. It pins
        the premise the decision rests on.
        """
        entry = api["components"]["schemas"]["TranscriptEntry"]["properties"]
        assert "type" in entry, (
            "TranscriptEntry lost its `type` discriminator — a client can no "
            "longer tell a question from a reply, and API-6's reasoning "
            "(API_CONTRACT §13) no longer holds"
        )
        values = entry["type"].get("enum")
        assert values is not None, (
            "TranscriptEntry.type has no enum, so nothing says `question` is "
            "a value a client may rely on"
        )
        assert "question" in values, (
            f"`question` is not among TranscriptEntry.type: {values}. API-6 "
            f"assumes a client can count its own questions from the "
            f"transcript it already has"
        )

    def test_feedback_headings_are_the_neutral_ones(self, api):
        heading = (api["components"]["schemas"]["Feedback"]["properties"]
                   ["reasoning"]["items"]["properties"]["heading"]["enum"])
        assert heading == ["Diagnostic focus", "History completeness",
                           "Evidence exploration"]

    def test_feedback_carries_the_learners_own_evidence(self, api):
        """ADR-0004: every judgement is traceable to what the learner did."""
        reasoning = (api["components"]["schemas"]["Feedback"]["properties"]
                     ["reasoning"]["items"]["properties"])
        assert "evidence" in reasoning


class TestErrorCatalogue:
    def test_every_documented_error_code_is_declared(self, api):
        """
        Codes are a stable API. A client branching on `monthly_limit_reached`
        breaks if it is absent from the generated enum.
        """
        import re

        contract = (SPEC.parent / "docs" / "spec" / "API_CONTRACT.md").read_text(
            encoding="utf-8")
        section = contract.split("# 10. Error code catalogue")[1].split("# 11")[0]
        documented = set(re.findall(r"^\| `(\w+)` \|", section, re.M))
        declared = set(api["components"]["schemas"]["Error"]["properties"]
                       ["error"]["properties"]["code"]["enum"])
        missing = sorted(documented - declared)
        assert not missing, f"documented but not declared: {missing}"
