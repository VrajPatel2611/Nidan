"""
T-004 criterion 2 · the build fails below 94%.

`validate_detectors.py` used to print its result and always exit 0, so wiring
it into CI would have run it and cheerfully passed at any accuracy. These tests
prove the gate exists, that it is set to the published figure, and that it
actually fails — a gate never observed failing is not known to work.

These run the full validation in a subprocess. They are NOT marked `slow` —
CI's test job runs `-m "not slow"`, and a gate whose own tests are excluded from
CI is not a gate.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "validate_detectors.py"

# What NOT to copy when these tests clone the repository into a tmpdir.
#
# One list, used by both tests, because it was duplicated and only one copy
# would have been updated.
#
# **`node_modules` is the load-bearing entry.** T-032 added `web/`, and from
# the moment anyone ran `npm ci` this copied 457 MB and ~100 000 files twice
# per test run — the full suite went from about 80 seconds to over 45 minutes,
# with the process at 0 % CPU and no output, which reads exactly like a hang.
# Nothing failed, so nothing said why. The validation gate runs
# `validate_detectors.py`, which imports `nidan.domain` and the pilot
# sessions; it has never needed a single JavaScript file.
#
# `web/src` and the rest of the web app are small and are still copied, so
# this excludes the build artefacts rather than the source.
_IGNORE = (
    "venv", ".venv", ".git", "__pycache__", "*.pyc",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", ".next", ".turbo",          # T-032's web app
    "report", "docs", "sessions", "*.egg-info",
    "htmlcov", ".coverage",
)


def _run(cwd=REPO):
    """
    Run validation in `cwd`, importing the copy of nidan that lives there.

    PYTHONPATH matters: nidan is installed editable, pointing at the real
    repository, so without it a subprocess in a copied tree would import the
    real detectors and the degraded copy would appear to pass.
    """
    import os

    # PYTHONIOENCODING and encoding="utf-8" are both needed on Windows: the
    # child prints tick and box-drawing characters that cp1252 cannot encode,
    # and `text=True` alone would decode the reply with the locale codec.
    env = dict(os.environ, PYTHONPATH=str(cwd), PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, str(cwd / "validate_detectors.py")],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=180, env=env,
    )


def test_the_repo_copy_excludes_the_javascript_tree():
    """
    A guard on `_IGNORE`, and the reason it exists is worth stating.

    T-032 added `web/`. From the first `npm ci`, the two tests below copied
    457 MB and ~100 000 files of `node_modules` into a tmpdir, twice per run.
    The full suite went from about 80 seconds to over 45 minutes, sitting at
    0 % CPU with no output — indistinguishable from a hang, and nothing failed,
    so nothing said why. It was found by `lsof`-ing the stuck process and
    seeing it copy `web/node_modules/tinyglobby/LICENSE`.

    This asserts the exclusion rather than the runtime, because a timing
    assertion on a laptop is flaky and this is the actual invariant: the
    detector gate needs `nidan/` and the pilot sessions, never a JavaScript
    dependency. If `node_modules` ever returns to the copy, the symptom is a
    suite that looks broken rather than one that fails.
    """
    import shutil

    ignore = shutil.ignore_patterns(*_IGNORE)
    # shutil hands the ignore callable a directory and its entries, and takes
    # back the names to skip. Ask it directly rather than copying anything.
    assert "node_modules" in ignore(str(REPO / "web"), ["src", "node_modules"]), (
        "the repo copy would include web/node_modules — see this test's "
        "docstring for what that costs")
    for unwanted in (".next", ".turbo", "venv", ".git"):
        assert unwanted in ignore(str(REPO), [unwanted, "nidan"]), unwanted

    # And the things the gate genuinely needs must NOT be excluded.
    kept = ignore(str(REPO), ["nidan", "validate_detectors.py", "pyproject.toml"])
    assert not kept, f"the copy would skip something the gate needs: {kept}"


def test_the_threshold_is_the_published_figure():
    """
    94% is what the paper reports. If this constant and the paper disagree, one
    of them is wrong — and it is not the paper's job to follow the code.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("validate_detectors", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.MINIMUM_ACCURACY == 0.94


def test_passes_on_the_current_detectors():
    r = _run()
    assert r.returncode == 0, f"validation failed unexpectedly:\n{r.stdout}\n{r.stderr}"
    assert "PASS" in r.stdout


def test_fails_when_a_detector_is_degraded(tmp_path):
    """
    The test that matters. A copy of the repository with anchoring rule A1
    broken must exit non-zero — otherwise CI would merge a change that
    invalidates the published claim.
    """
    import shutil

    work = tmp_path / "repo"
    shutil.copytree(REPO, work, ignore=shutil.ignore_patterns(*_IGNORE))

    # T-016 moved the thresholds out of bias.py and into data, so the
    # degradation is applied where the number now lives. That is a better
    # mutation point than the old one: it breaks the detector the same way a
    # bad calibration would, rather than the way a bad edit would.
    thresholds = work / "nidan" / "domain" / "assessment" / "thresholds.py"
    source = thresholds.read_text(encoding="utf-8")
    assert "anchoring_concentration=0.60" in source, (
        "the pilot anchoring threshold has moved — update this test")
    thresholds.write_text(
        source.replace("anchoring_concentration=0.60",
                       "anchoring_concentration=0.99"), encoding="utf-8")

    r = _run(cwd=work)
    assert r.returncode != 0, (
        "a degraded detector did NOT fail the build — the research claim is "
        f"unprotected:\n{r.stdout}"
    )
    assert "FAIL" in r.stderr
    assert "below the required 94%" in r.stderr


def test_the_failure_message_says_not_to_lower_the_threshold(tmp_path):
    """
    The obvious way to make a red build green is to lower the number. The
    message has to say so, because whoever hits this will be under time
    pressure and may not have read TEST_STRATEGY.
    """
    import shutil

    work = tmp_path / "repo"
    shutil.copytree(REPO, work, ignore=shutil.ignore_patterns(*_IGNORE))
    # Same degradation as the test above, applied where T-016 moved the
    # threshold to. This test silently stopped degrading anything when the
    # constant left bias.py — it passed on the unmutated copy, which would
    # have been a green build proving nothing.
    thresholds = work / "nidan" / "domain" / "assessment" / "thresholds.py"
    source = thresholds.read_text(encoding="utf-8")
    assert "anchoring_concentration=0.60" in source, (
        "the pilot anchoring threshold has moved — update this test")
    thresholds.write_text(
        source.replace("anchoring_concentration=0.60",
                       "anchoring_concentration=0.99"), encoding="utf-8")

    stderr = _run(cwd=work).stderr
    assert "Do not" in stderr and "lower the threshold" in stderr
