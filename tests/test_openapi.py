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


@pytest.fixture(scope="module")
def api() -> dict:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


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
            (method.lower(), str(rule).removeprefix("/v1"))
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
        """
        session = api["components"]["schemas"]["Session"]["properties"]
        forbidden = {
            "coverage", "coverage_pct", "topics_covered", "topics_missed",
            "questions_remaining", "readiness", "completeness", "score",
            "detected", "bias_flags", "required_topics",
        }
        leaked = forbidden & set(session)
        assert not leaked, f"assessment state exposed mid-consultation: {leaked}"

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
