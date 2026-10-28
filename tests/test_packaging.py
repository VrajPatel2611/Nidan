"""
Every template and static asset reaches an installed build.

This exists because of a bug that was invisible everywhere except production.
`pyproject.toml` declared `web/templates/*.html`, which does not recurse, so an
installed build shipped the four top-level templates and none of the twenty-one
under `admin/` — the entire console, plus the case editor's and Playtest's
JavaScript.

**Nothing caught it.** The 590-test suite passed, because `pip install -e .`
resolves templates from the source tree rather than from package data. So did
every local run. The failure appeared only in Docker, as a 500 on `/admin`
reading `TemplateNotFound: admin/dashboard.html` — which looks like a missing
template, not a missing *pattern*, and sends you to the wrong file.

The assertion is therefore about the declaration, not the file system: we check
that the globs in `pyproject.toml` actually match every asset, because that is
the thing that was wrong.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "nidan"

# Assets the app loads by name at runtime, so a missing one is a 500 rather
# than an import error anything earlier would have caught.
ASSET_DIRS = (
    ("web/templates", "*.html"),
    ("web/static", "*"),
)


def _declared_patterns() -> list[str]:
    """The package-data globs, as pyproject declares them."""
    with (ROOT / "pyproject.toml").open("rb") as f:
        config = tomllib.load(f)
    patterns = config["tool"]["setuptools"]["package-data"]["nidan"]
    assert patterns, "no package-data declared for nidan"
    return patterns


def _assets() -> list[Path]:
    """Every asset that must survive packaging, relative to `nidan/`."""
    found: list[Path] = []
    for subdir, glob in ASSET_DIRS:
        base = PACKAGE / subdir
        assert base.is_dir(), f"{base} is missing — has the layout changed?"
        found += [p.relative_to(PACKAGE) for p in base.rglob(glob) if p.is_file()]
    return sorted(found)


def _packaged() -> set[Path]:
    """
    What the declared patterns actually match, by the same mechanism setuptools uses.

    **Not `Path.match()`.** That was the first attempt, and it fails on exactly
    the case this file exists for: `match()` treats `**` as a single component,
    so `web/templates/**/*.html` appeared not to cover
    `web/templates/admin/playtest/index.html` even though setuptools packages it
    correctly. A test that re-implements the tool's matching will disagree with
    the tool, and the disagreement is indistinguishable from the bug.

    `Path.glob()` expands `**` recursively, as `glob(recursive=True)` does
    inside setuptools, so this asks the real question: given these patterns,
    which files are collected?
    """
    return {
        p.relative_to(PACKAGE)
        for pattern in _declared_patterns()
        for p in PACKAGE.glob(pattern)
        if p.is_file()
    }


def test_there_are_assets_to_check():
    """
    Guards the guard.

    Every other assertion here is 'no asset is unmatched', which passes
    vacuously if the discovery breaks. A renamed directory would otherwise
    turn this file green and silent at the same moment it stops testing
    anything.
    """
    assets = _assets()
    assert len(assets) >= 20, f"only found {len(assets)} assets; discovery looks broken"
    # The specific file whose absence caused the original 500.
    assert Path("web/templates/admin/dashboard.html") in assets


@pytest.mark.parametrize("asset", _assets(), ids=str)
def test_every_asset_is_matched_by_a_package_data_pattern(asset: Path):
    """
    An asset no pattern matches is absent from an installed build.

    Parametrised one-per-file on purpose: the failure names the exact asset
    that would go missing, rather than reporting that 'packaging is wrong'.
    """
    assert asset in _packaged(), (
        f"{asset} is matched by none of {_declared_patterns()}. It will be "
        f"missing from an installed build — and because `pip install -e .` "
        f"reads the source tree, the whole suite will still pass and the app "
        f"will still work locally. Add a recursive pattern."
    )


def test_nested_assets_need_a_recursive_pattern():
    """
    The regression itself, stated directly.

    A non-recursive `web/templates/*.html` must not be enough, because the
    console lives in a subdirectory. If this ever passes, the templates have
    been flattened and the recursive patterns are no longer load-bearing —
    which is worth knowing before someone 'tidies' them away.
    """
    nested = [a for a in _assets() if len(a.parts) > 3]
    assert nested, "expected assets in subdirectories, e.g. web/templates/admin/"
    assert not any(a.match("web/templates/*.html") for a in nested), (
        "a nested asset matched the non-recursive pattern; this test's premise "
        "no longer holds")
