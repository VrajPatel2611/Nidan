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
    shutil.copytree(
        REPO, work,
        ignore=shutil.ignore_patterns("venv", ".git", "__pycache__", "*.pyc",
                                      ".pytest_cache", ".mypy_cache", "report",
                                      "docs", "sessions", "*.egg-info"),
    )

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
    shutil.copytree(
        REPO, work,
        ignore=shutil.ignore_patterns("venv", ".git", "__pycache__", "*.pyc",
                                      ".pytest_cache", ".mypy_cache", "report",
                                      "docs", "sessions", "*.egg-info"),
    )
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
