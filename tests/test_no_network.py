"""
T-002 criterion 1 · no test makes a network call.

Two guards. The autouse `_no_real_llm` fixture in conftest makes a real call
fail; these tests prove that guard is actually wired to reality rather than
patching a path that no longer exists.
"""

import pytest

import nidan.api.routes as routes
import nidan.api.v1.consultation as consultation
import nidan.infra.feedback as infra_feedback
from nidan.infra.llm import gateway, provider
from tests.app_config import llm_source_paths


def test_the_guard_actually_blocks_a_real_client():
    """
    The autouse fixture is in force, so constructing a client must fail.

    T-031 moved the factory from `gateway._get_client` to the provider seam,
    and this test failed loudly on the rename — which is what it is for. The
    docstring above warns about "patching a path that no longer exists", and a
    guard written against the gateway's own symbol would have become one.
    """
    with pytest.raises(AssertionError, match="real LLM client"):
        provider.GroqProvider()._get_client()


def test_the_guard_blocks_a_call_through_the_gateway_itself():
    """
    Stronger than the one above, and the reason it is here: the guard matters
    only if it survives the whole path a real call takes. `call_llm` resolves
    the provider, hits the patched factory, finds the failure untransient and
    re-raises on the first attempt — so no retry loop sleeps either.
    """
    with pytest.raises(AssertionError, match="real LLM client"):
        gateway.call_llm([{"role": "user", "content": "hello"}], "You are a patient.")


def test_every_call_llm_import_site_is_patched_by_the_fake_llm_fixture(fake_llm):
    """
    `call_llm` is imported by name, so each importing module holds its own
    reference. conftest patches a hard-coded list of sites; this test fails if
    that list goes stale — a new module importing call_llm would otherwise
    silently reach the real gateway.
    """
    assert infra_feedback.call_llm is fake_llm
    assert routes.call_llm is fake_llm
    assert consultation.call_llm is fake_llm


def test_no_unpatched_module_imports_call_llm():
    """
    Catches the stale-list problem at its source: if a module starts importing
    call_llm and conftest is not updated, this names it.
    """
    import pathlib

    # Read from the same place conftest patches from. This set used to be
    # hard-coded here, which made the guard against a stale list hold a stale
    # list of its own: adding a site to conftest and not to this line produced
    # "imports call_llm but conftest does not patch it" about a module
    # conftest did patch.
    patched = llm_source_paths()
    root = pathlib.Path(__file__).resolve().parent.parent

    # .as_posix(), not str(): str() uses the OS separator, so on Windows this
    # yielded "nidan\\api\\routes.py" and matched nothing in `patched` — every
    # module looked unpatched and the test failed on Windows only. Caught by the
    # Tests (Windows) CI job on its first run.
    importers = {
        py.relative_to(root).as_posix()
        for py in (root / "nidan").rglob("*.py")
        if "import call_llm" in py.read_text(encoding="utf-8")
    }

    unpatched = sorted(importers - patched)
    assert not unpatched, (
        "These modules import call_llm but conftest's fake_llm fixture does not "
        f"patch them, so they would reach the real gateway: {unpatched}"
    )
