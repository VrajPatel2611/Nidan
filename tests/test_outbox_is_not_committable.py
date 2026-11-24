"""
The outbox must not be committable (T-038).

`nidan/infra/email/outbox.py` writes each message to
`EMAIL_OUTBOX_DIR`, and a data export's attachment is the learner's own
questions, the patient's replies and the feedback written about them — the
most sensitive bytes this project produces, assembled by design into one file.

**This test exists because the claim was wrong when it was first written.**
`config.py` said the directory was covered by `.gitignore`; `.gitignore` had
`*.log`, which covers `logs/api.log` and not `logs/outbox/<id>/
nidan-export.json`. A real pilot participant's export sat in the working tree,
untracked and committable, and nothing failed — it was found by checking.

Asserted through `git check-ignore` rather than by reading `.gitignore`,
because the question is what git does, not what the file says. A negated
pattern elsewhere, a `.gitignore` in a subdirectory or an entry in
`.git/info/exclude` all change the answer.
"""

from __future__ import annotations

import pathlib
import subprocess

from nidan.config import settings

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _ignored(path: str) -> bool:
    """True when git would refuse to add this path."""
    return subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=ROOT, capture_output=True,
    ).returncode == 0


def test_the_outbox_directory_is_ignored_by_git():
    outbox = settings.EMAIL_OUTBOX_DIR.rstrip("/")
    assert _ignored(f"{outbox}/anything"), (
        f"{outbox}/ is not gitignored, so a message written there can be "
        f"committed. An export attachment contains a learner's own questions.")


def test_every_file_the_outbox_writes_is_ignored():
    """
    The three filenames specifically, not just the directory.

    A pattern can cover a directory and still miss a path inside it — which is
    exactly the bug this file was written for, in the other direction.
    """
    outbox = settings.EMAIL_OUTBOX_DIR.rstrip("/")
    stem = f"{outbox}/20260101T000000Z-Your-Nidan-data-export-abcd1234"
    for name in ("message.json", "body.txt", "nidan-export.json"):
        assert _ignored(f"{stem}/{name}"), f"{name} is committable"


def test_the_default_outbox_is_not_somewhere_that_gets_committed():
    """
    The default must not be the repository root or a tracked directory.

    `EMAIL_OUTBOX_DIR` is configurable, so this pins the default rather than
    every possible value — a deployment that points it at a tracked path is
    making a choice; the default should not make it for them.
    """
    default = settings.EMAIL_OUTBOX_DIR
    assert default not in (".", "", "/"), "the outbox default is the repo root"
    assert not default.startswith(("nidan/", "tests/", "docs/", "web/", "migrations/")), (
        f"the outbox default {default!r} is inside a tracked source tree")
